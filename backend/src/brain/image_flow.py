from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow, get_business
from src.specialists.publishing.caption_generator import generate_caption_for_image
from src.specialists.publishing.instagram import publish_image_to_instagram
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
    from src.db.storage import upload_image

    image_url = None
    analysis = None
    try:
        image_b64, mime_type = download_media(image_id)
        image_url = upload_image(image_b64, mime_type, image_id)
        analysis = analyze_image(image_b64, mime_type)
        print(f"[IG STEP 4] image_url stored in flow_data: {image_url}")
    except Exception as e:
        print(f"[IG FAIL step=image_setup] {repr(e)}")

    if not image_url:
        clear_conversation_flow(user.id)
        return "מצטערת, לא הצלחתי לשמור את התמונה. אפשר לנסות שוב? שלחי את התמונה מחדש 🙏"

    update_conversation_flow(user.id, "image_post", {
        "step": "awaiting_goal",
        "image_analysis": analysis,
        "image_url": image_url,
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

    # If the user wrote their own text (not an instruction) — use it directly
    if not _is_edit_instruction(message):
        caption = message.strip()
    else:
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


_EDIT_INSTRUCTION_VERBS = {
    "תוסיפי", "תוסיף", "הוסיפי", "הוסיף", "תקצרי", "תקצר", "קצרי", "קצר",
    "שני", "שנה", "תשני", "תשנה", "הסירי", "הסיר", "מחקי", "מחק",
    "הפכי", "הפוך", "תכתבי", "תכתוב", "כתבי", "כתוב", "עשי", "עשה",
    "תגרמי", "תדאגי", "תני", "תני", "תשמיטי", "תשמיט", "תחזקי",
    "תהפכי", "תעצימי", "תוציאי", "תכניסי",
}


def _is_edit_instruction(msg: str) -> bool:
    """True if the message is an edit instruction to Claude, not the user's own replacement text."""
    words = msg.strip().split()
    if not words:
        return False
    if words[0] in _EDIT_INSTRUCTION_VERBS:
        return True
    if len(words) <= 5:
        return True
    return False


def _publish(user: User, flow_data: dict, language: str) -> str:
    caption = flow_data.get("caption", "")
    image_url = flow_data.get("image_url")

    if not image_url:
        print("[IG PUBLISH ABORT] image_url is missing from flow_data")
        clear_conversation_flow(user.id)
        return "מצטערת, התמונה לא זמינה לפרסום. שלחי תמונה חדשה כדי לנסות שוב."

    business = get_business(user.id)
    if not business:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    all_accounts = SocialAccountRepository().get_by_business(business.id)
    ig_accounts = [a for a in all_accounts if a.get("platform") == "instagram"]

    print(f"[IG PUBLISH] image_url={image_url}")
    print(f"[IG PUBLISH] ig_accounts count={len(ig_accounts)}")

    if not ig_accounts:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    ig = ig_accounts[0]
    ig_user_id = ig.get("platform_account_id")
    access_token = ig.get("access_token")
    print(f"[IG PUBLISH] ig_user_id={ig_user_id} token_present={bool(access_token)}")

    # Clear flow BEFORE polling — prevents duplicate webhooks from re-triggering publish
    clear_conversation_flow(user.id)

    try:
        post_url = publish_image_to_instagram(ig_user_id, image_url, caption, access_token)
        return get_string("post_published", language=language, post_url=post_url)
    except Exception as e:
        print(f"[IG PUBLISH ERROR] {repr(e)}")
        return get_string("post_publish_error", language=language)
