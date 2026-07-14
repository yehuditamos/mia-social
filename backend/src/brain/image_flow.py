from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow, get_business
from src.specialists.publishing.caption_generator import generate_caption_for_image
from src.specialists.publishing.instagram import publish_image_to_instagram
from src.specialists.publishing.facebook import publish_text_post
from src.db.repositories.social_account import SocialAccountRepository
from src.brain.workflow_engine import NOTEBOOK_RESET

_GOALS = {
    "1": "להביא מתאמנות חדשות",
    "2": "לחזק את המותג",
    "3": "ליצור מעורבות",
    "4": "להודיע על משהו",
    "5": "למכור שירות",
    "6": "השראה",
}

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר", "לפרסם"}
_CANCEL = {"לא", "בטל", "ביטול", "בטלי", "❌", "no", "cancel"}
_EDIT = {"ערכי", "שנה", "שני", "ערוך", "✏️", "edit", "שינוי"}

_CAPTION_MODE_MSG = (
    "1️⃣ כתבי עבורי — תבחרי מטרה ומיה תכתוב\n"
    "2️⃣ אני אכתוב לבד — כתבי כיתוב ומיה תגהה"
)
_ASK_OWN_CAPTION = "כתבי את הכיתוב שלך לתמונה ✍️\n\nמיה תגהה ותציין שיפורים לפני פרסום."
_PROOFREAD_OPTIONS = "✅ אשרי את כל התיקונים | ✏️ ערכי בעצמי | 🔄 חזרי לטקסט המקורי"


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
        "step": "awaiting_caption",
        "image_analysis": analysis,
        "image_url": image_url,
    })
    return "קיבלתי את התמונה.\n\nכתבי כיתוב לפוסט, או שלחי *כתבי* ואני אכין."


def handle_image_flow(user: User, state: ConversationState, business: Business,
                      message: str, language: str) -> str:
    flow_step = (state.flow_data or {}).get("step", "awaiting_caption")

    # New streamlined step
    if flow_step == "awaiting_caption":
        return _handle_caption(user, state, business, message, language)

    # Active steps
    if flow_step == "awaiting_proofread_approval":
        return _handle_proofread_approval(user, state, business, message, language)
    if flow_step == "awaiting_approval":
        return _handle_approval(user, state, business, message, language)
    if flow_step == "awaiting_edit":
        return _handle_edit(user, state, business, message, language)

    # Backward compat: old steps route to new handler
    if flow_step in ("awaiting_caption_mode", "awaiting_own_caption"):
        return _handle_caption(user, state, business, message, language)
    if flow_step == "awaiting_goal":
        return _handle_goal(user, state, business, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_caption(user: User, state: ConversationState, business: Business,
                    message: str, language: str) -> str:
    """
    Unified caption step. Internal checks:
    1. User sends actual text → proofread + show preview (no mode question)
    2. User says 'כתבי' → auto-generate caption (no goal question)
    3. Anything ambiguous → re-ask clearly

    Eliminates: awaiting_caption_mode, awaiting_goal (two questions removed)
    """
    flow_data = state.flow_data or {}
    msg       = message.strip()
    msg_lower = msg.lower()

    _GENERATE_TRIGGERS = {
        "כתבי", "תכתבי", "כתוב", "תכתוב",
        "1", "1️⃣", "כתבי עבורי", "את כתבי", "מה תכתבי",
        "תייצרי", "תמציאי", "תחשבי",
    }

    if msg_lower in _GENERATE_TRIGGERS or any(t in msg_lower for t in {"כתבי עבורי", "את תכתבי"}):
        return _auto_generate_caption(user, flow_data, business, language)

    # 2+ words = treat as own caption text
    if len(msg.split()) >= 2:
        return _handle_own_caption(user, state, msg, language)

    # Single word that's not a known trigger — ask clearly
    return "כתבי כיתוב לפוסט, או שלחי *כתבי* ואני אכין."


def _auto_generate_caption(user: User, flow_data: dict, business: Business,
                            language: str) -> str:
    """Generate caption automatically without asking for goal."""
    analysis = flow_data.get("image_analysis")
    try:
        caption = generate_caption_for_image(
            brand_name=    getattr(business, "brand_name",    "העסק") or "העסק",
            what_you_do=   getattr(business, "what_you_do",   "") or "",
            writing_style= getattr(business, "writing_style", "חמים ואישי") or "חמים ואישי",
            writing_language=getattr(business, "writing_language", "he") or "he",
            image_analysis=analysis,
            goal="general",
        )
    except Exception as e:
        print(f"[IMAGE_FLOW] auto-caption error: {repr(e)}")
        return "לא הצלחתי לייצר כיתוב — נסי לכתוב בעצמך."

    update_conversation_flow(user.id, "image_post", {
        **flow_data,
        "step":    "awaiting_approval",
        "caption": caption,
    })
    return get_string("post_preview", language=language, caption=caption)


def _handle_caption_mode(user: User, state: ConversationState, business: Business,
                          message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    if msg in {"1", "1️⃣", "כתבי עבורי", "כתוב עבורי", "מיה תכתוב"}:
        update_conversation_flow(user.id, "image_post", {**flow_data, "step": "awaiting_goal"})
        return get_string("image_received_ask_goal", language=language)

    if msg in {"2", "2️⃣", "אני אכתוב", "אני אכתוב לבד", "לבד", "אני"}:
        update_conversation_flow(user.id, "image_post", {**flow_data, "step": "awaiting_own_caption"})
        return _ASK_OWN_CAPTION

    # Long message → user already wrote their caption
    if len(message.split()) > 4:
        return _handle_own_caption(user, state, message, language)

    return f"ראיתי את התמונה 💜\n\n{_CAPTION_MODE_MSG}"


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


def _handle_own_caption(user: User, state: ConversationState, message: str, language: str) -> str:
    from src.brain.text_editor import proofread_text, proofread_preview

    flow_data = (state.flow_data or {}) if hasattr(state, "flow_data") else {}
    original = message.strip()
    corrected = proofread_text(original)
    preview = proofread_preview(original, corrected)

    update_conversation_flow(user.id, "image_post", {
        **flow_data,
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

    if any(w in msg for w in {"אשרי", "אשר", "✅", "אישור", "כן", "לפרסם", "תיקונים", "yes"}):
        update_conversation_flow(user.id, "image_post", {
            **flow_data,
            "step": "awaiting_approval",
            "caption": corrected,
        })
        return get_string("post_preview", language=language, caption=corrected)

    if any(w in msg for w in {"חזרי", "חזור", "מקור", "🔄", "מקורי", "בחזרה"}):
        update_conversation_flow(user.id, "image_post", {
            **flow_data,
            "step": "awaiting_approval",
            "caption": original,
        })
        return get_string("post_preview", language=language, caption=original)

    if any(w in msg for w in {"ערכי", "ערוך", "✏️", "edit", "שינוי", "שני", "שנה",
                               "תתקני", "תקני", "שפרי", "לתקן", "לערוך"}):
        update_conversation_flow(user.id, "image_post", {
            **flow_data,
            "step": "awaiting_edit",
            "caption": corrected,
        })
        return get_string("post_ask_edit", language=language)

    # User rewrote caption directly
    if len(message.strip()) > 20:
        new_caption = message.strip()
        update_conversation_flow(user.id, "image_post", {
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
        update_conversation_flow(user.id, "image_post", {**flow_data, "step": "awaiting_edit"})
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

    try:
        post_url = publish_image_to_instagram(ig_user_id, image_url, caption, access_token)
        clear_conversation_flow(user.id)
        return get_string("post_published", language=language, post_url=post_url) + NOTEBOOK_RESET
    except Exception as e:
        error_str = str(e)
        print(f"[IG PUBLISH ERROR] {error_str}")
        return _friendly_ig_error(error_str) + "\n\n💾 הפוסט נשמר — שלחי *כן* לנסות שוב."


def _friendly_ig_error(error_str: str) -> str:
    err = error_str.lower()
    if "190" in error_str or ("token" in err and ("expire" in err or "invalid" in err)):
        return "⚠️ הטוקן פג תוקף.\n\nשלחי 'חברי חשבונות' לחיבור מחדש."
    if "200" in error_str or "permission" in err or "instagram_content_publish" in err:
        return (
            "⚠️ חסרה הרשאת instagram_content_publish.\n\n"
            "שלחי 'חברי חשבונות' ואשרי שוב את כל ההרשאות."
        )
    if "container" in err or "media" in err:
        return f"⚠️ שגיאה בהעלאת המדיה:\n\n{error_str[:250]}"
    return f"⚠️ שגיאה מ-Meta:\n\n{error_str[:300]}\n\nנסי שוב."


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
