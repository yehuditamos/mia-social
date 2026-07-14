from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow, get_business
from src.db.repositories.social_account import SocialAccountRepository
from src.brain.workflow_engine import NOTEBOOK_RESET

_APPROVE = {"כן", "yes", "אוקיי", "אוקי", "יופי", "מעולה", "✅", "אישור", "מאשרת", "מאשר", "פרסמי", "פרסם"}
_CANCEL = {"לא", "בטל", "ביטול", "בטלי", "❌", "no", "cancel"}

_STYLE_MAP = {
    "1": "plain", "רגיל": "plain", "כמות שהיא": "plain", "ללא שינוי": "plain", "בלי שינוי": "plain",
    "2": "caption", "כיתוב": "caption", "טקסט": "caption", "עם טקסט": "caption",
    "3": "design", "עיצוב": "design", "מסגרת": "design", "פילטר": "design",
    "4": "full", "הכל": "full", "מלא": "full", "עם הכל": "full",
}

_FILTER_MAP = {
    "1": "warm", "חמים": "warm", "חם": "warm",
    "2": "cool", "קריר": "cool", "קר": "cool",
    "3": "bw", "שחור לבן": "bw", "שחור-לבן": "bw", "bw": "bw",
    "4": "vintage", "וינטאג": "vintage", "וינטג'": "vintage", "vintage": "vintage",
    "5": "none", "ללא": "none", "בלי": "none", "רגיל": "none",
}

_STYLE_MENU = (
    "בחרי סגנון לסטורי:\n\n"
    "1️⃣ פרסמי כמות שהיא\n"
    "2️⃣ הוסיפי כיתוב\n"
    "3️⃣ עיצוב מותגי (מסגרת + פילטר)\n"
    "✨ 4 — הכל: כיתוב + עיצוב מלא"
)

_FILTER_MENU = (
    "בחרי פילטר:\n\n"
    "🌅 1 — חמים\n"
    "❄️ 2 — קריר\n"
    "⚫ 3 — שחור-לבן\n"
    "🎞️ 4 — וינטאג'\n"
    "✅ 5 — ללא פילטר"
)


def start_story_flow(user: User, business: Business, media_id: str, language: str) -> str:
    from src.whatsapp.media import download_media
    from src.db.storage import upload_image

    media_url = None
    media_kind = "image"
    media_b64_stored = None
    mime_type_stored = None
    try:
        media_b64_stored, mime_type_stored = download_media(media_id)
        media_url = upload_image(media_b64_stored, mime_type_stored, media_id)
        media_kind = "video" if mime_type_stored.startswith("video/") else "image"
        print(f"[STORY] uploaded kind={media_kind} url={media_url}")
    except Exception as e:
        print(f"[STORY FAIL step=media_setup] {repr(e)}")

    if not media_url:
        clear_conversation_flow(user.id)
        return "מצטערת, לא הצלחתי לשמור את הקובץ. שלחי מחדש 🙏"

    if media_kind == "video":
        update_conversation_flow(user.id, "story_creation", {
            "step": "awaiting_approval",
            "media_url": media_url,
            "media_kind": "video",
        })
        return "ראיתי את הסרטון 🎬\nלפרסם כסטורי באינסטגרם?\n\n✅ כן\n❌ ביטול"

    # Describe image for accessibility before asking for style
    description = ""
    if media_b64_stored and mime_type_stored:
        try:
            from src.brain.free_chat import describe_image_accessibility
            description = describe_image_accessibility(media_b64_stored, mime_type_stored)
        except Exception as e:
            print(f"[STORY] vision error: {repr(e)}")

    update_conversation_flow(user.id, "story_creation", {
        "step": "awaiting_style",
        "media_url": media_url,
        "media_kind": "image",
    })

    desc_line = f"\n🖼 מיה רואה: {description}\n" if description else ""
    return (
        f"קיבלתי! 🤩 יאללה בואי נעשה סטורי 🎉"
        f"{desc_line}\n\n"
        f"{_STYLE_MENU}"
    )


def handle_story_flow(user: User, state: ConversationState, business: Business,
                      message: str, language: str) -> str:
    step = (state.flow_data or {}).get("step", "awaiting_image")

    if step == "awaiting_image":
        return get_string("story_need_image", language=language)
    if step == "awaiting_style":
        return _handle_style(user, state, business, message, language)
    if step == "awaiting_caption":
        return _handle_caption(user, state, business, message, language)
    if step == "awaiting_filter":
        return _handle_filter(user, state, business, message, language)
    if step == "awaiting_approval":
        return _handle_approval(user, state, business, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_style(user: User, state: ConversationState, business: Business,
                  message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    if msg in _CANCEL:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלתי את הסטורי 🙂"

    style = _STYLE_MAP.get(msg)
    if not style:
        for key, val in _STYLE_MAP.items():
            if key in msg:
                style = val
                break
    if not style:
        return f"לא הבנתי 😊\n\n{_STYLE_MENU}"

    if style == "plain":
        update_conversation_flow(user.id, "story_creation", {
            **flow_data, "step": "awaiting_approval", "style": "plain",
        })
        return "לפרסם את הסטורי?\n\n✅ כן\n❌ ביטול"

    if style == "caption":
        update_conversation_flow(user.id, "story_creation", {
            **flow_data, "step": "awaiting_caption", "style": "caption",
        })
        return "מה הכיתוב? ✍️\nשלחי את הטקסט שתרצי על הסטורי."

    if style == "design":
        update_conversation_flow(user.id, "story_creation", {
            **flow_data, "step": "awaiting_filter", "style": "design",
        })
        return _FILTER_MENU

    if style == "full":
        update_conversation_flow(user.id, "story_creation", {
            **flow_data, "step": "awaiting_caption", "style": "full",
        })
        return "מה הכיתוב? ✍️\nשלחי את הטקסט שתרצי על הסטורי."

    return _STYLE_MENU


def _handle_caption(user: User, state: ConversationState, business: Business,
                    message: str, language: str) -> str:
    flow_data = state.flow_data or {}
    caption = message.strip()
    style = flow_data.get("style", "caption")

    if caption.lower() in _CANCEL:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלתי את הסטורי 🙂"

    if style == "full":
        update_conversation_flow(user.id, "story_creation", {
            **flow_data, "step": "awaiting_filter", "caption": caption,
        })
        return _FILTER_MENU

    # style == "caption": apply text only then preview
    edited_url = _apply_and_upload(
        image_url=flow_data.get("media_url"),
        caption=caption,
        filter_name=None,
        brand_frame=False,
        brand_name=None,
    )
    update_conversation_flow(user.id, "story_creation", {
        **flow_data,
        "step": "awaiting_approval",
        "caption": caption,
        "edited_url": edited_url,
    })
    preview = f"__send_image__:{edited_url}" if edited_url else ""
    approval = "הנה הסטורי שלך 👆\nלפרסם?\n\n✅ כן\n❌ ביטול"
    return f"{preview}\n||||\n{approval}" if preview else approval


def _handle_filter(user: User, state: ConversationState, business: Business,
                   message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    filter_name = _FILTER_MAP.get(msg)
    if not filter_name:
        for key, val in _FILTER_MAP.items():
            if key in msg:
                filter_name = val
                break
    if not filter_name:
        return f"לא הבנתי 😊\n\n{_FILTER_MENU}"

    style = flow_data.get("style", "design")
    caption = flow_data.get("caption") if style == "full" else None
    brand_name = None
    try:
        biz = get_business(user.id)
        brand_name = biz.brand_name if biz else None
    except Exception:
        pass

    edited_url = _apply_and_upload(
        image_url=flow_data.get("media_url"),
        caption=caption,
        filter_name=filter_name,
        brand_frame=True,
        brand_name=brand_name,
    )
    update_conversation_flow(user.id, "story_creation", {
        **flow_data,
        "step": "awaiting_approval",
        "filter": filter_name,
        "edited_url": edited_url,
    })
    preview = f"__send_image__:{edited_url}" if edited_url else ""
    approval = "הנה הסטורי שלך 👆\nלפרסם?\n\n✅ כן\n❌ ביטול"
    return f"{preview}\n||||\n{approval}" if preview else approval


def _handle_approval(user: User, state: ConversationState, business: Business,
                     message: str, language: str) -> str:
    msg = message.strip().lower()
    flow_data = state.flow_data or {}

    if msg in _CANCEL:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלתי את הסטורי 🙂"

    if any(word in msg for word in _APPROVE) or msg in _APPROVE:
        return _publish(user, flow_data, language)

    return "לא הבנתי 😊\nכתבי:\n✅ כן — לפרסם\n❌ ביטול"


def _friendly_story_error(error_str: str) -> str:
    err = error_str.lower()
    if "190" in error_str or ("token" in err and ("expire" in err or "invalid" in err)):
        return "⚠️ הטוקן פג תוקף.\n\nשלחי 'חברי חשבונות' לחיבור מחדש."
    if "200" in error_str or "permission" in err:
        return "⚠️ חסרות הרשאות פרסום.\n\nשלחי 'חברי חשבונות' ואשרי שוב את כל ההרשאות."
    if "media" in err or "video" in err:
        return f"⚠️ שגיאה בעיבוד המדיה:\n\n{error_str[:200]}"
    return f"⚠️ לא הצלחתי לפרסם את הסטורי:\n\n{error_str[:200]}"


def _apply_and_upload(image_url, caption, filter_name, brand_frame, brand_name):
    if not image_url:
        return None
    try:
        from src.specialists.media.overlay import compose_story, upload_composed
        image_bytes = compose_story(
            image_url=image_url,
            caption=caption,
            filter_name=filter_name,
            brand_frame=brand_frame,
            brand_name=brand_name,
        )
        url = upload_composed(image_bytes)
        print(f"[STORY EDIT] uploaded edited image: {url}")
        return url
    except Exception as e:
        print(f"[STORY EDIT FAIL] {repr(e)}")
        return image_url  # fallback to original


def _publish(user: User, flow_data: dict, language: str) -> str:
    from src.specialists.publishing.instagram import publish_story_to_instagram

    publish_url = flow_data.get("edited_url") or flow_data.get("media_url")
    media_kind = flow_data.get("media_kind", "image")

    if not publish_url:
        clear_conversation_flow(user.id)
        return "מצטערת, הקובץ לא זמין. שלחי מחדש."

    business = get_business(user.id)
    if not business:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    all_accounts = SocialAccountRepository().get_by_business(business.id)
    ig_accounts = [a for a in all_accounts if a.get("platform") == "instagram"]

    if not ig_accounts:
        clear_conversation_flow(user.id)
        return get_string("post_no_accounts", language=language)

    ig = ig_accounts[0]

    try:
        publish_story_to_instagram(
            ig.get("platform_account_id"),
            publish_url,
            ig.get("access_token"),
            media_kind=media_kind,
        )
        clear_conversation_flow(user.id)
        emoji = "🎬" if media_kind == "video" else "📸"
        return f"✅ הסטורי פורסם בהצלחה! {emoji}" + NOTEBOOK_RESET
    except Exception as e:
        print(f"[STORY PUBLISH ERROR] {repr(e)}")
        return _friendly_story_error(str(e)) + "\n\n💾 הסטורי נשמר — שלחי *כן* לנסות שוב."
