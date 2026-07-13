from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow, get_business
from src.db.repositories.social_account import SocialAccountRepository

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר", "פרסמי", "פרסם"}
_CANCEL = {"לא", "בטל", "ביטול", "בטלי", "❌", "no", "cancel"}


def start_story_flow(user: User, business: Business, image_id: str, language: str) -> str:
    from src.whatsapp.media import download_media
    from src.db.storage import upload_image

    image_url = None
    try:
        image_b64, mime_type = download_media(image_id)
        image_url = upload_image(image_b64, mime_type, image_id)
        print(f"[STORY] image_url={image_url}")
    except Exception as e:
        print(f"[STORY FAIL step=image_setup] {repr(e)}")

    if not image_url:
        clear_conversation_flow(user.id)
        return "מצטערת, לא הצלחתי לשמור את התמונה. אפשר לנסות שוב? שלחי את התמונה מחדש 🙏"

    update_conversation_flow(user.id, "story_creation", {
        "step": "awaiting_approval",
        "image_url": image_url,
    })
    return "ראיתי את התמונה 📸\nלפרסם אותה כסטורי באינסטגרם?\n\n✅ כן\n❌ ביטול"


def handle_story_flow(user: User, state: ConversationState, business: Business,
                      message: str, language: str) -> str:
    flow_step = (state.flow_data or {}).get("step", "awaiting_image")

    if flow_step == "awaiting_image":
        return get_string("story_need_image", language=language)
    if flow_step == "awaiting_approval":
        return _handle_approval(user, state, business, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_approval(user: User, state: ConversationState, business: Business,
                     message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    if msg in _CANCEL:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלתי את הסטורי 🙂\nמתי תרצי ליצור סטורי חדש?"

    if any(word in msg for word in _APPROVE) or msg in _APPROVE:
        return _publish(user, flow_data, language)

    return "לא הבנתי 😊\nכתבי:\n✅ כן — לפרסם\n❌ ביטול"


def _publish(user: User, flow_data: dict, language: str) -> str:
    from src.specialists.publishing.instagram import publish_story_to_instagram

    image_url = flow_data.get("image_url")
    if not image_url:
        clear_conversation_flow(user.id)
        return "מצטערת, התמונה לא זמינה. שלחי תמונה חדשה."

    business = get_business(user.id)
    if not business:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    all_accounts = SocialAccountRepository().get_by_business(business.id)
    ig_accounts = [a for a in all_accounts if a.get("platform") == "instagram"]

    print(f"[STORY PUBLISH] image_url={image_url} ig_accounts count={len(ig_accounts)}")

    if not ig_accounts:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    ig = ig_accounts[0]
    try:
        publish_story_to_instagram(
            ig.get("platform_account_id"),
            image_url,
            ig.get("access_token"),
        )
        clear_conversation_flow(user.id)
        return "✅ הסטורי פורסם בהצלחה! 📸"
    except Exception as e:
        print(f"[STORY PUBLISH ERROR] {repr(e)}")
        clear_conversation_flow(user.id)
        return "אופס, לא הצלחתי לפרסם את הסטורי. בדקי שהחשבון מחובר ונסי שוב."
