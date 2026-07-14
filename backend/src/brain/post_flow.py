from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow
from src.specialists.publishing.caption_generator import generate_caption
from src.specialists.publishing.facebook import publish_text_post
from src.db.repositories.social_account import SocialAccountRepository

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר"}
_CANCEL = {"לא", "בטל", "ביטול", "בטלי", "❌", "no", "cancel"}
_EDIT = {"ערכי", "שנה", "שני", "ערוך", "✏️", "edit", "שינוי"}
_EXIT_KEYWORDS = {"סטורי", "ריל", "תפריט", "חזרי", "חזור", "מניו", "menu", "story", "reel", "ביטול", "בטלי"}


def handle_post_flow(user: User, state: ConversationState, business: Business,
                     message: str, language: str) -> str:
    flow_step = (state.flow_data or {}).get("step", "awaiting_topic")

    if flow_step == "awaiting_topic":
        return _handle_topic(user, business, message, language)

    if flow_step == "awaiting_approval":
        return _handle_approval(user, state, business, message, language)

    if flow_step == "awaiting_edit":
        return _handle_edit(user, state, business, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_topic(user: User, business: Business, topic: str, language: str) -> str:
    words = set(topic.strip().lower().split())
    if words & _EXIT_KEYWORDS:
        clear_conversation_flow(user.id)
        return get_string("main_menu", language=language, name=user.name or "")

    try:
        caption = generate_caption(
            brand_name=business.brand_name,
            what_you_do=business.what_you_do,
            writing_style=business.writing_style,
            writing_language=business.writing_language,
            topic=topic,
        )
    except Exception as e:
        print("CAPTION ERROR:", repr(e))
        clear_conversation_flow(user.id)
        return get_string("post_caption_error", language=language)

    update_conversation_flow(user.id, "post_creation", {
        "step": "awaiting_approval",
        "topic": topic,
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
        update_conversation_flow(user.id, "post_creation", {
            **flow_data,
            "step": "awaiting_edit",
        })
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
            caption = generate_caption(
                brand_name=business.brand_name,
                what_you_do=business.what_you_do,
                writing_style=business.writing_style,
                writing_language=business.writing_language,
                topic=flow_data.get("topic", ""),
                edit_note=message,
            )
        except Exception as e:
            print("CAPTION ERROR:", repr(e))
            clear_conversation_flow(user.id)
            return get_string("post_caption_error", language=language)

    update_conversation_flow(user.id, "post_creation", {
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
    # Starts with an instruction verb
    if words[0] in _EDIT_INSTRUCTION_VERBS:
        return True
    # Very short message — likely an instruction (e.g., "קצר יותר", "הוסיפי אמוג'י")
    if len(words) <= 5:
        return True
    return False


def _publish(user: User, flow_data: dict, language: str) -> str:
    caption = flow_data.get("caption", "")
    business_id = None

    from src.specialists.memory.engine import get_business
    business = get_business(user.id)
    if business:
        business_id = business.id

    if not business_id:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    accounts = SocialAccountRepository().get_by_business(business_id, platform="facebook")
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
