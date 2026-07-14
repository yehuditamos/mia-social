import os
import requests as _req
from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow, get_business
from src.db.repositories.social_account import SocialAccountRepository
from src.brain.workflow_engine import NOTEBOOK_RESET

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר", "פרסמי", "פרסם"}
_CANCEL  = {"בטל", "ביטול", "בטלי", "❌", "cancel", "עצרי", "הפסיקי"}
_SKIP    = {"דלגי", "דלג", "בלי", "ללא", "skip"}

# Words that signal "please suggest a caption for me"
_SUGGEST_WORDS = {"תציעי", "תכתבי", "כתבי", "הצעי", "תרשמי", "תציג", "הציגי", "suggest", "תמלאי"}

# Content-type redirect keywords — user changed their mind mid-flow
_OTHER_CONTENT = {"קרוסלה", "carousel", "פוסט", "post", "סטורי", "story", "סטוריז"}


def start_reel_flow(user: User, business: Business, video_id: str, language: str) -> str:
    from src.whatsapp.media import download_media
    from src.db.storage import upload_image

    media_url = None
    try:
        media_b64, mime_type = download_media(video_id)
        if not mime_type.startswith("video/"):
            clear_conversation_flow(user.id)
            return "ריל צריך להיות סרטון 🎬\nשלחי סרטון ואנסה שוב."
        media_url = upload_image(media_b64, mime_type, video_id)
        print(f"[REEL] uploaded url={media_url}")
    except Exception as e:
        print(f"[REEL FAIL upload] {repr(e)}")

    if not media_url:
        clear_conversation_flow(user.id)
        return "מצטערת, לא הצלחתי לשמור את הסרטון. שלחי מחדש 🙏"

    update_conversation_flow(user.id, "reel_creation", {
        "step": "awaiting_caption",
        "video_url": media_url,
    })
    return (
        "ראיתי את הסרטון 🎬\n\n"
        "תרצי להוסיף כיתוב לריל?\n"
        "✍️ כתבי את הכיתוב\n"
        "⏭️ דלגי — לפרסם בלי כיתוב"
    )


def handle_reel_flow(user: User, state: ConversationState, business: Business,
                     message: str, language: str) -> str:
    step = (state.flow_data or {}).get("step", "awaiting_video")
    msg  = message.strip()
    ml   = msg.lower()

    # ── Global cancel — works at every step ───────────────────────────────────
    if ml in _CANCEL or set(ml.split()) & _CANCEL:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלנו." + NOTEBOOK_RESET

    if step == "awaiting_video":
        # Redirect: user changed their mind and wants a different content type
        if set(ml.split()) & _OTHER_CONTENT:
            clear_conversation_flow(user.id)
            from src.brain.main_menu import handle_post_onboarding
            biz = get_business(user.id)
            return handle_post_onboarding(user, biz, message)

        # Attention-getter ("מיה" alone)
        if ml in {"מיה", "מיה?", "היי", "hey"}:
            return (
                "כאן! 🎬\n\n"
                "אנחנו באמצע יצירת ריל. מה תרצי?\n\n"
                "📹 שלחי סרטון — להמשיך\n"
                "❌ ביטול — לסגור"
            )

        return "שלחי סרטון לריל 🎬"

    if step == "awaiting_caption":
        return _handle_caption(user, state, message, business)
    if step == "awaiting_approval":
        return _handle_approval(user, state, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_caption(user: User, state: ConversationState, message: str,
                    business: Business = None) -> str:
    flow_data = state.flow_data or {}
    msg = message.strip()
    ml  = msg.lower()

    if ml in _SKIP:
        caption = None
    elif any(w in ml.split() for w in _SUGGEST_WORDS):
        # User asked Mia to suggest a caption — generate one with Claude
        caption = _generate_caption(msg, business) or "יום עבודה מוצלח עם הצוות 💪"
    else:
        caption = msg

    caption_preview = f"📝 כיתוב: \"{caption}\"" if caption else "📝 ללא כיתוב"
    update_conversation_flow(user.id, "reel_creation", {
        **flow_data,
        "step":    "awaiting_approval",
        "caption": caption,
    })
    return (
        f"הנה פרטי הריל:\n\n"
        f"🎬 סרטון מוכן\n"
        f"{caption_preview}\n\n"
        f"לפרסם?\n✅ כן\n❌ ביטול"
    )


def _generate_caption(context: str, business: Business = None) -> str:
    """Ask Claude to write a short Reel caption based on user's description."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    brand   = _bval(business, "brand_name",    "העסק") if business else "העסק"
    what_do = _bval(business, "what_you_do",   "") if business else ""
    style   = _bval(business, "writing_style", "חמים ואישי") if business else "חמים ואישי"

    system = (
        f"מנהלת סושיאל לעסק {brand} ({what_do}). סגנון: {style}.\n"
        "כתבי כיתוב קצר לריל אינסטגרם — עד 120 תווים, אמוג'י אחד מתאים בסוף."
    )
    try:
        res = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 100,
                "system":     system,
                "messages":   [{"role": "user", "content": context}],
            },
            timeout=15,
        )
        data = res.json()
        if res.status_code == 200 and "content" in data:
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[REEL_CAPTION] Claude error: {repr(e)}")
    return ""


def _bval(obj, field: str, default: str) -> str:
    if not obj:
        return default
    return getattr(obj, field, None) or default


def _handle_approval(user: User, state: ConversationState,
                     message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    if msg in _CANCEL:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלתי את הריל 🙂"

    if any(word in msg for word in _APPROVE) or msg in _APPROVE:
        return _publish(user, flow_data, language)

    return "לא הבנתי 😊\n✅ כן — לפרסם\n❌ ביטול"


def _publish(user: User, flow_data: dict, language: str) -> str:
    from src.specialists.publishing.instagram import publish_reel_to_instagram

    video_url = flow_data.get("video_url")
    caption = flow_data.get("caption") or ""

    if not video_url:
        clear_conversation_flow(user.id)
        return "מצטערת, הסרטון לא זמין. שלחי מחדש."

    business = get_business(user.id)
    if not business:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    ig_accounts = [
        a for a in SocialAccountRepository().get_by_business(business.id)
        if a.get("platform") == "instagram"
    ]
    if not ig_accounts:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    ig = ig_accounts[0]

    try:
        publish_reel_to_instagram(
            ig.get("platform_account_id"),
            video_url,
            caption,
            ig.get("access_token"),
        )
        clear_conversation_flow(user.id)
        return "✅ הריל פורסם בהצלחה! 🎬" + NOTEBOOK_RESET
    except Exception as e:
        print(f"[REEL PUBLISH ERROR] {repr(e)}")
        return _friendly_reel_error(str(e)) + "\n\n💾 הריל נשמר — שלחי *כן* לנסות שוב."


def _friendly_reel_error(error_str: str) -> str:
    err = error_str.lower()
    if "190" in error_str or ("token" in err and ("expire" in err or "invalid" in err)):
        return "⚠️ הטוקן פג תוקף.\n\nשלחי 'חברי חשבונות' לחיבור מחדש."
    if "200" in error_str or "permission" in err:
        return "⚠️ חסרות הרשאות פרסום.\n\nשלחי 'חברי חשבונות' ואשרי שוב."
    if "video" in err or "media" in err or "container" in err:
        return "⚠️ שגיאה בעיבוד הסרטון.\n\nייתכן שהפורמט לא נתמך. נסי סרטון .mp4."
    return f"⚠️ הפרסום נכשל:\n\n{error_str[:200]}"
