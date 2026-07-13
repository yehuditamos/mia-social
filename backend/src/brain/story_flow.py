from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow, get_business
from src.db.repositories.social_account import SocialAccountRepository

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר", "פרסמי", "פרסם"}
_CANCEL = {"לא", "בטל", "ביטול", "בטלי", "❌", "no", "cancel"}


def start_story_flow(user: User, business: Business, media_id: str, language: str) -> str:
    from src.whatsapp.media import download_media
    from src.db.storage import upload_image

    media_url = None
    media_kind = "image"
    try:
        media_b64, mime_type = download_media(media_id)
        media_url = upload_image(media_b64, mime_type, media_id)
        media_kind = "video" if mime_type.startswith("video/") else "image"
        print(f"[STORY] media_url={media_url} kind={media_kind}")
    except Exception as e:
        print(f"[STORY FAIL step=media_setup] {repr(e)}")

    if not media_url:
        clear_conversation_flow(user.id)
        return "מצטערת, לא הצלחתי לשמור את הקובץ. אפשר לנסות שוב? שלחי מחדש 🙏"

    emoji = "🎬" if media_kind == "video" else "📸"
    update_conversation_flow(user.id, "story_creation", {
        "step": "awaiting_approval",
        "media_url": media_url,
        "media_kind": media_kind,
    })
    return f"ראיתי {emoji}\nלפרסם כסטורי באינסטגרם?\n\n✅ כן\n❌ ביטול"


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

    media_url = flow_data.get("media_url")
    media_kind = flow_data.get("media_kind", "image")

    if not media_url:
        clear_conversation_flow(user.id)
        return "מצטערת, הקובץ לא זמין. שלחי מחדש."

    business = get_business(user.id)
    if not business:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    all_accounts = SocialAccountRepository().get_by_business(business.id)
    ig_accounts = [a for a in all_accounts if a.get("platform") == "instagram"]

    print(f"[STORY PUBLISH] media_url={media_url} kind={media_kind} ig_accounts={len(ig_accounts)}")

    if not ig_accounts:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    ig = ig_accounts[0]
    try:
        publish_story_to_instagram(
            ig.get("platform_account_id"),
            media_url,
            ig.get("access_token"),
            media_kind=media_kind,
        )
        clear_conversation_flow(user.id)
        emoji = "🎬" if media_kind == "video" else "📸"
        return f"✅ הסטורי פורסם בהצלחה! {emoji}"
    except Exception as e:
        print(f"[STORY PUBLISH ERROR] {repr(e)}")
        clear_conversation_flow(user.id)
        return "אופס, לא הצלחתי לפרסם את הסטורי. בדקי שהחשבון מחובר ונסי שוב."
