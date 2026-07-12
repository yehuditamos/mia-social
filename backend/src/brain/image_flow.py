from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow, get_business
from src.specialists.publishing.caption_generator import generate_caption_for_image
from src.specialists.publishing.facebook import publish_text_post
from src.db.repositories.social_account import SocialAccountRepository

_GOALS = {
    "1": "להביא מתאמנות חדשות",
    "2": "לחזק את המותג",
    "3": "ליצור מעורבות",
    "4": "להודיע על משהו",
    "5": "למכור שירות",
    "6": "השראה",
}

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר"}
_CANCEL = {"לא", "בטל", "ביטול", "בטלי", "❌", "no", "cancel"}
_EDIT = {"ערכי", "שנה", "שני", "ערוך", "✏️", "edit", "שינוי"}


def start_image_flow(user: User, business: Business, image_id: str, language: str) -> str:
    from src.whatsapp.media import download_media
    from src.specialists.publishing.vision import analyze_image

    analysis = None
    try:
        image_b64, mime_type = download_media(image_id)
        analysis = analyze_image(image_b64, mime_type)
        print("IMAGE ANALYSIS:", analysis[:100])
    except Exception as e:
        print("IMAGE ANALYSIS ERROR:", repr(e))

    update_conversation_flow(user.id, "image_post", {
        "step": "awaiting_goal",
        "image_analysis": analysis,
    })
    return get_string("image_received_ask_goal", language=language)


def handle_image_flow(user: User, state: ConversationState, business: Business,
                      message: str, language: str) -> str:
    flow_step = (state.flow_data or {}).get("step", "awaiting_goal")

    if flow_step == "awaiting_goal":
        return _handle_goal(user, state, business, message, language)
    if flow_step == "awaiting_approval":
        return _handle_approval(user, state, business, message, language)
    if flow_step == "awaiting_edit":
        return _handle_edit(user, state, business, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_goal(user: User, state: ConversationState, business: Business,
                 message: str, language: str) -> str:
    flow_data = state.flow_data or {}
    msg = message.strip()

    goal = _GOALS.get(msg)
    if not goal:
        for v in _GOALS.values():
            if msg in v or v in msg:
                goal = v
                break
    if not goal:
        goal = msg

    analysis = flow_data.get("image_analysis")

    try:
        caption = generate_caption_for_image(
            brand_name=business.brand_name,
            what_you_do=business.what_you_do,
            writing_style=business.writing_style,
            writing_language=business.writing_language,
            image_analysis=analysis,
            goal=goal,
        )
    except Exception as e:
        print("CAPTION ERROR:", repr(e))
        clear_conversation_flow(user.id)
        return get_string("post_caption_error", language=language)

    update_conversation_flow(user.id, "image_post", {
        **flow_data,
        "step": "awaiting_approval",
        "goal": goal,
        "caption": caption,
    })
    return get_string("post_preview", language=language, caption=caption)


def _handle_approval(user: User, state: ConversationState, business: Business,
                     message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    if msg in _CANCEL:
        clear_conversation_flow(user.id)
        return get_string("post_cancelled", language=language)

    if msg in _EDIT:
        update_conversation_flow(user.id, "image_post", {**flow_data, "step": "awaiting_edit"})
        return get_string("post_ask_edit", language=language)

    if any(word in msg for word in _APPROVE):
        return _publish(user, flow_data, language)

    return get_string("post_approval_unclear", language=language)


def _handle_edit(user: User, state: ConversationState, business: Business,
                 message: str, language: str) -> str:
    flow_data = state.flow_data or {}

    try:
        caption = generate_caption_for_image(
            brand_name=business.brand_name,
            what_you_do=business.what_you_do,
            writing_style=business.writing_style,
            writing_language=business.writing_language,
            image_analysis=flow_data.get("image_analysis"),
            goal=flow_data.get("goal", ""),
            edit_note=message,
        )
    except Exception as e:
        print("CAPTION ERROR:", repr(e))
        clear_conversation_flow(user.id)
        return get_string("post_caption_error", language=language)

    update_conversation_flow(user.id, "image_post", {
        **flow_data,
        "step": "awaiting_approval",
        "caption": caption,
    })
    return get_string("post_preview", language=language, caption=caption)


def _publish(user: User, flow_data: dict, language: str) -> str:
    caption = flow_data.get("caption", "")
    business = get_business(user.id)
    if not business:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    accounts = SocialAccountRepository().get_by_business(business.id, platform="facebook")
    if not accounts:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    account = accounts[0]
    page_id = account.get("page_id")
    page_access_token = (account.get("metadata") or {}).get("page_access_token")

    if not page_id or not page_access_token:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    try:
        post_url = publish_text_post(page_id, page_access_token, caption)
    except Exception as e:
        print("PUBLISH ERROR:", repr(e))
        clear_conversation_flow(user.id)
        return get_string("post_publish_error", language=language)

    clear_conversation_flow(user.id)
    return get_string("post_published", language=language, post_url=post_url)
