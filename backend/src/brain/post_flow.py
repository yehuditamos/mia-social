from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow
from src.specialists.publishing.caption_generator import generate_caption
from src.specialists.publishing.facebook import publish_text_post
from src.db.repositories.social_account import SocialAccountRepository
from src.brain.workflow_engine import NOTEBOOK_RESET

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר", "לפרסם"}
_CANCEL = {"לא", "בטל", "ביטול", "בטלי", "❌", "no", "cancel"}
_EDIT = {"ערכי", "שנה", "שני", "ערוך", "✏️", "edit", "שינוי"}
_EXIT_KEYWORDS = {"סטורי", "ריל", "תפריט", "מניו", "menu", "story", "reel"}

_MODE_MSG = "בואי ניצור פוסט! 📝\n\n1️⃣ כתבי עבורי — תאריי נושא ומיה תכתוב\n2️⃣ אני אכתוב לבד — מיה תגהה לפני פרסום"
_ASK_OWN_TEXT = "כתבי את הטקסט שלך ✍️\n\nמיה תגהה ותציין שיפורים לפני פרסום."
_PROOFREAD_OPTIONS = "✅ אשרי את כל התיקונים | ✏️ ערכי בעצמי | 🔄 חזרי לטקסט המקורי"


def handle_post_flow(user: User, state: ConversationState, business: Business,
                     message: str, language: str) -> str:
    flow_step = (state.flow_data or {}).get("step", "awaiting_mode")

    if flow_step == "awaiting_mode":
        return _handle_mode(user, business, message, language)
    if flow_step == "awaiting_topic":
        return _handle_topic(user, business, message, language)
    if flow_step == "awaiting_own_text":
        return _handle_own_text(user, message, language)
    if flow_step == "awaiting_proofread_approval":
        return _handle_proofread_approval(user, state, business, message, language)
    if flow_step == "awaiting_approval":
        return _handle_approval(user, state, business, message, language)
    if flow_step == "awaiting_edit":
        return _handle_edit(user, state, business, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_mode(user: User, business: Business, message: str, language: str) -> str:
    msg = message.strip().lower()
    words = set(msg.split())

    if words & _EXIT_KEYWORDS:
        clear_conversation_flow(user.id)
        return get_string("main_menu", language=language, name=user.name or "")

    if msg in {"1", "1️⃣", "כתבי עבורי", "כתוב עבורי", "מיה תכתוב"}:
        update_conversation_flow(user.id, "post_creation", {"step": "awaiting_topic"})
        return get_string("post_ask_topic", language=language)

    if msg in {"2", "2️⃣", "אני אכתוב", "אני אכתוב לבד", "לבד", "אני"}:
        update_conversation_flow(user.id, "post_creation", {"step": "awaiting_own_text"})
        return _ASK_OWN_TEXT

    # Long message in mode step → treat as user writing their own text
    if len(message.split()) > 5:
        return _handle_own_text(user, message, language)

    return _MODE_MSG


def _handle_topic(user: User, business: Business, topic: str, language: str) -> str:
    if set(topic.strip().lower().split()) & _EXIT_KEYWORDS:
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
        return get_string("post_caption_error", language=language)

    update_conversation_flow(user.id, "post_creation", {
        "step": "awaiting_approval",
        "topic": topic,
        "caption": caption,
    })
    return get_string("post_preview", language=language, caption=caption)


def _handle_own_text(user: User, message: str, language: str) -> str:
    from src.brain.text_editor import proofread_text, proofread_preview

    original = message.strip()
    corrected = proofread_text(original)
    preview = proofread_preview(original, corrected)

    update_conversation_flow(user.id, "post_creation", {
        "step": "awaiting_proofread_approval",
        "original_text": original,
        "corrected_text": corrected,
        "caption": corrected,
    })
    return preview


def _handle_proofread_approval(user: User, state: ConversationState, business: Business,
                                message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}
    original = flow_data.get("original_text", "")
    corrected = flow_data.get("corrected_text", "")

    if msg in _CANCEL:
        clear_conversation_flow(user.id)
        return get_string("post_cancelled", language=language)

    # Approve corrections
    if any(w in msg for w in {"אשרי", "אשר", "✅", "אישור", "כן", "לפרסם", "תיקונים", "yes"}):
        update_conversation_flow(user.id, "post_creation", {
            **flow_data,
            "step": "awaiting_approval",
            "caption": corrected,
        })
        return get_string("post_preview", language=language, caption=corrected)

    # Revert to original
    if any(w in msg for w in {"חזרי", "חזור", "מקור", "🔄", "מקורי", "בחזרה", "original"}):
        update_conversation_flow(user.id, "post_creation", {
            **flow_data,
            "step": "awaiting_approval",
            "caption": original,
        })
        return get_string("post_preview", language=language, caption=original)

    # Edit manually — also catches "תתקני", "שפרי" etc.
    if any(w in msg for w in {"ערכי", "ערוך", "✏️", "edit", "שינוי", "שני", "שנה",
                               "תתקני", "תקני", "שפרי", "לתקן", "לערוך"}):
        update_conversation_flow(user.id, "post_creation", {
            **flow_data,
            "step": "awaiting_edit",
            "caption": corrected,
        })
        return get_string("post_ask_edit", language=language)

    # User rewrote text directly — use it as new caption
    if len(message.strip()) > 20:
        new_caption = message.strip()
        update_conversation_flow(user.id, "post_creation", {
            **flow_data,
            "step": "awaiting_approval",
            "caption": new_caption,
        })
        return get_string("post_preview", language=language, caption=new_caption)

    return _PROOFREAD_OPTIONS


def _handle_approval(user: User, state: ConversationState, business: Business,
                     message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    if msg in _CANCEL:
        clear_conversation_flow(user.id)
        return get_string("post_cancelled", language=language)

    if msg in _EDIT:
        update_conversation_flow(user.id, "post_creation", {**flow_data, "step": "awaiting_edit"})
        return get_string("post_ask_edit", language=language)

    if any(word in msg for word in _APPROVE):
        return _publish(user, flow_data, language)

    return get_string("post_approval_unclear", language=language)


def _handle_edit(user: User, state: ConversationState, business: Business,
                 message: str, language: str) -> str:
    flow_data = state.flow_data or {}

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


def _publish(user: User, flow_data: dict, language: str) -> str:
    caption = flow_data.get("caption", "")

    from src.specialists.memory.engine import get_business
    business = get_business(user.id)
    if not business:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    business_id = business.id
    accounts = SocialAccountRepository().get_by_business(business_id, platform="facebook")
    print(f"[PUBLISH] business_id={business_id} facebook_accounts={len(accounts)}")

    if not accounts:
        ig_accounts = SocialAccountRepository().get_by_business(business_id, platform="instagram")
        print(f"[PUBLISH] instagram_accounts={len(ig_accounts)}")
        clear_conversation_flow(user.id)
        if ig_accounts:
            return (
                "⚠️ לא נמצא דף פייסבוק מחובר.\n\n"
                "לפרסום פוסט טקסט נדרש דף פייסבוק עסקי — לא רק חשבון אינסטגרם.\n\n"
                "שלחי 'חברי חשבונות' ובדקי שנבחר דף פייסבוק בתהליך ההתחברות."
            )
        return get_string("post_no_accounts", language=language)

    account = accounts[0]
    page_id = account.get("page_id")
    metadata = account.get("metadata") or {}
    page_access_token = metadata.get("page_access_token")
    user_token = account.get("access_token")

    print(f"[PUBLISH] page_id={page_id} has_page_token={bool(page_access_token)} has_user_token={bool(user_token)}")

    if not page_id:
        clear_conversation_flow(user.id)
        return "⚠️ מזהה הדף חסר.\n\nנסי לחבר מחדש: שלחי 'חברי חשבונות'."

    token_to_use = page_access_token or user_token
    if not token_to_use:
        clear_conversation_flow(user.id)
        return "⚠️ טוקן הגישה חסר.\n\nנסי לחבר מחדש: שלחי 'חברי חשבונות'."

    try:
        post_url = publish_text_post(page_id, token_to_use, caption)
    except Exception as e:
        error_str = str(e)
        print(f"[PUBLISH ERROR] {error_str}")
        return _friendly_meta_error(error_str) + "\n\n💾 הפוסט נשמר — שלחי *כן* לנסות שוב."

    clear_conversation_flow(user.id)
    return get_string("post_published", language=language, post_url=post_url) + NOTEBOOK_RESET


def _friendly_meta_error(error_str: str) -> str:
    err = error_str.lower()
    if "190" in error_str or ("token" in err and ("expire" in err or "invalid" in err)):
        return (
            "⚠️ הטוקן פג תוקף.\n\n"
            "חברי מחדש: שלחי 'חברי חשבונות'."
        )
    if "200" in error_str or "permission" in err or "pages_manage_posts" in err:
        return (
            "⚠️ חסרות הרשאות פרסום לפייסבוק.\n\n"
            "נדרש: pages_manage_posts, pages_read_engagement\n\n"
            "שלחי 'חברי חשבונות' ואשרי שוב את כל ההרשאות."
        )
    if "803" in error_str or "does not exist" in err:
        return "⚠️ הדף לא נמצא.\n\nייתכן שהדף הוסר. שלחי 'חברי חשבונות'."
    return f"⚠️ שגיאה מ-Meta:\n\n{error_str[:300]}\n\nנסי שוב או שלחי 'חברי חשבונות'."


_EDIT_INSTRUCTION_VERBS = {
    "תוסיפי", "תוסיף", "הוסיפי", "הוסיף", "תקצרי", "תקצר", "קצרי", "קצר",
    "שני", "שנה", "תשני", "תשנה", "הסירי", "הסיר", "מחקי", "מחק",
    "הפכי", "הפוך", "תכתבי", "תכתוב", "כתבי", "כתוב", "עשי", "עשה",
    "תגרמי", "תדאגי", "תני", "תשמיטי", "תשמיט", "תחזקי",
    "תהפכי", "תעצימי", "תוציאי", "תכניסי",
}


def _is_edit_instruction(msg: str) -> bool:
    words = msg.strip().split()
    if not words:
        return False
    if words[0] in _EDIT_INSTRUCTION_VERBS:
        return True
    if len(words) <= 5:
        return True
    return False
