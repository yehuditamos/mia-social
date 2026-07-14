import os
import re
import requests
from src.specialists.memory.models import User, Business
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow
from src.brain.workflow_engine import (
    classify_intent, is_pure_command, is_valid_hook, is_valid_cta, active_task_reminder
)

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"


def handle_carousel_flow(user, state, business, message: str, language: str = "he") -> str:
    msg = message.strip()
    data = state.flow_data or {}
    step = data.get("step", "awaiting_mode")

    if step == "awaiting_mode":
        return _handle_mode(user, data, msg)
    if step == "awaiting_topic":
        return _handle_topic(user, data, business, msg)
    if step == "awaiting_own_text":
        return _handle_own_text(user, data, msg)
    if step == "awaiting_proofread_approval":
        return _handle_proofread_approval(user, data, business, msg)
    if step == "awaiting_hook":
        return _handle_hook(user, data, business, msg)
    if step == "awaiting_cta":
        return _handle_cta(user, data, business, msg)
    if step == "awaiting_color":
        return _handle_color(user, data, msg)
    if step == "awaiting_structure_approval":
        return _handle_structure_approval(user, data, business, msg)
    if step == "awaiting_slide_edit":
        return _handle_slide_edit(user, data, msg)

    clear_conversation_flow(user.id)
    return "נתחיל מחדש? כתבי *פוסט* 💜"


# ─── Step handlers ─────────────────────────────────────────────────────────────

def _handle_mode(user, data: dict, msg: str) -> str:
    intent = classify_intent(msg, "awaiting_mode")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "בסדר. מה תרצי לעשות?"

    if msg in {"1", "1️⃣"} or ("כתבי" in msg and "לבד" not in msg and "בעצמ" not in msg):
        update_conversation_flow(user.id, "carousel_creation", {"step": "awaiting_topic"})
        return "מה הנושא לפוסט?"

    if msg in {"2", "2️⃣"} or intent == "self_write" or "לבד" in msg or "בעצמ" in msg:
        update_conversation_flow(user.id, "carousel_creation", {"step": "awaiting_own_text"})
        return "כתבי את הטקסט שלך (מיה תגהה לפני פרסום):"

    # Long message at mode step → treat as the user writing their own text
    if len(msg.split()) >= 6:
        return _handle_own_text(user, data, msg)

    return "📋 יצירת קרוסלה לאינסטגרם\n\n1️⃣ כתבי עבורי — ציוני נושא ומיה תכתוב\n2️⃣ אני אכתוב לבד — מיה תגהה"


def _handle_topic(user, data: dict, business, msg: str) -> str:
    intent = classify_intent(msg, "awaiting_topic")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if intent == "self_write":
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_own_text"})
        return "כתבי את הטקסט שלך:"

    if len(msg) < 3:
        return "ספרי עוד קצת — מה הנושא?"

    brand   = _bval(business, "brand_name",    "העסק")
    what_do = _bval(business, "what_you_do",   "")
    style   = _bval(business, "writing_style", "חמים ואישי")

    body = _generate_body(msg, brand, what_do, style)
    if not body:
        return "לא הצלחתי לייצר תוכן — נסי שוב."

    hooks = _generate_hook_suggestions(msg, body, brand)
    if not hooks:
        hooks = [f"כל מה שצריך לדעת על {msg}",
                 f"הסוד שרוב האנשים לא יודעים על {msg}"]

    update_conversation_flow(user.id, "carousel_creation", {
        "step": "awaiting_hook",
        "topic": msg,
        "body_text": body,
        "hook_suggestions": hooks,
    })
    return (
        "הטקסט מוכן.\n\n"
        "בחרי כותרת לדף הראשון (מושך תשומת לב):\n\n"
        f"{_format_list(hooks)}\n\n"
        "או כתבי כותרת משלך:"
    )


def _handle_own_text(user, data: dict, msg: str) -> str:
    intent = classify_intent(msg, "awaiting_own_text")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if len(msg) < 5:
        return "כתבי את הטקסט שלך (אפשר כמה משפטים):"

    from src.brain.text_editor import proofread_text, proofread_preview
    corrected = proofread_text(msg)
    preview   = proofread_preview(msg, corrected)

    update_conversation_flow(user.id, "carousel_creation", {
        **data,
        "step":           "awaiting_proofread_approval",
        "original_text":  msg,
        "corrected_text": corrected,
    })
    return preview


def _handle_proofread_approval(user, data: dict, business, msg: str) -> str:
    from src.brain.text_editor import proofread_preview
    original  = data.get("original_text",  "")
    corrected = data.get("corrected_text", "")

    intent = classify_intent(msg, "awaiting_proofread_approval")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if "✅" in msg or msg in {"1", "כן", "אשרי"} or intent == "approve":
        body = corrected
    elif "🔄" in msg or "מקורי" in msg or "חזרי" in msg:
        body = original
    elif "✏️" in msg or intent == "edit":
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_own_text"})
        return "כתבי את הגרסה המעודכנת:"
    elif len(msg) > 25:
        # User rewrote the text directly — use it as the new body
        body = msg
    else:
        return proofread_preview(original, corrected)

    brand = _bval(business, "brand_name", "העסק")
    topic = data.get("topic", body[:40])
    hooks = _generate_hook_suggestions(topic, body, brand)
    if not hooks:
        hooks = ["כותרת שמושכת עניין"]

    update_conversation_flow(user.id, "carousel_creation", {
        **data,
        "step":             "awaiting_hook",
        "body_text":        body,
        "hook_suggestions": hooks,
    })
    return (
        "הגהה הושלמה.\n\n"
        "בחרי כותרת לדף הראשון:\n\n"
        f"{_format_list(hooks)}\n\n"
        "או כתבי כותרת משלך:"
    )


def _handle_hook(user, data: dict, business, msg: str) -> str:
    suggestions = data.get("hook_suggestions", [])
    intent = classify_intent(msg, "awaiting_hook")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if intent == "back":
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_topic"})
        return "מה הנושא החדש?"

    if intent == "regenerate":
        topic = data.get("topic", "")
        body  = data.get("body_text", "")
        brand = _bval(business, "brand_name", "העסק")
        new_hooks = _generate_hook_suggestions(topic, body, brand) or suggestions
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_hook", "hook_suggestions": new_hooks
        })
        return f"כותרות חדשות:\n\n{_format_list(new_hooks)}\n\nבחרי מספר או כתבי כותרת משלך:"

    if intent == "self_write":
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_own_text"})
        return "כתבי את הטקסט שלך:"

    # Numeric pick
    pick = _pick_from_list(msg, suggestions)
    if pick:
        hook = pick
    elif len(msg) > 70:
        # Long text at hook step → treat as new body text, regenerate hooks
        body  = msg
        topic = data.get("topic", "")
        brand = _bval(business, "brand_name", "העסק")
        new_hooks = _generate_hook_suggestions(topic, body, brand) or suggestions
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_hook", "body_text": body, "hook_suggestions": new_hooks
        })
        return f"עדכנתי את הטקסט.\n\nבחרי כותרת לדף הראשון:\n\n{_format_list(new_hooks)}\n\nאו כתבי כותרת משלך:"
    elif is_valid_hook(msg):
        hook = msg
    else:
        # Pure command or invalid input — stay in step
        return (
            f"{active_task_reminder('carousel_creation', 'awaiting_hook')}\n\n"
            f"{_format_list(suggestions)}"
        )

    # Hook chosen — move to CTA
    brand   = _bval(business, "brand_name",  "העסק")
    what_do = _bval(business, "what_you_do", "")
    ctas = _generate_cta_suggestions(brand, what_do)
    if not ctas:
        ctas = ["שמרי את הפוסט הזה 📌", "שתפי עם חברה", "כתבי לי בפרטי"]

    update_conversation_flow(user.id, "carousel_creation", {
        **data, "step": "awaiting_cta", "hook": hook, "cta_suggestions": ctas
    })
    return (
        f"כותרת: {hook}\n\n"
        "בחרי הנעה לפעולה לדף האחרון:\n\n"
        f"{_format_list(ctas)}\n\n"
        "או כתבי משלך:"
    )


def _handle_cta(user, data: dict, business, msg: str) -> str:
    suggestions = data.get("cta_suggestions", [])
    intent = classify_intent(msg, "awaiting_cta")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if intent == "back":
        hooks = data.get("hook_suggestions", [])
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_hook"})
        return f"חזרנו לבחירת כותרת:\n\n{_format_list(hooks)}\n\nאו כתבי כותרת משלך:"

    if intent == "regenerate":
        brand   = _bval(business, "brand_name",  "העסק")
        what_do = _bval(business, "what_you_do", "")
        new_ctas = _generate_cta_suggestions(brand, what_do) or suggestions
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_cta", "cta_suggestions": new_ctas
        })
        return f"הנעות חדשות:\n\n{_format_list(new_ctas)}\n\nבחרי מספר או כתבי משלך:"

    pick = _pick_from_list(msg, suggestions)
    if pick:
        cta = pick
    elif is_valid_cta(msg):
        cta = msg
    else:
        return (
            f"{active_task_reminder('carousel_creation', 'awaiting_cta')}\n\n"
            f"{_format_list(suggestions)}"
        )

    update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_color", "cta": cta})
    return f"הנעה לפעולה: {cta}\n\nצבע רקע לקרוסלה:\n\n⬛ שחור — טקסט לבן\n⬜ לבן — טקסט שחור"


def _handle_color(user, data: dict, msg: str) -> str:
    intent = classify_intent(msg, "awaiting_color")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if intent == "back":
        ctas = data.get("cta_suggestions", [])
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_cta"})
        return f"חזרנו לבחירת הנעה לפעולה:\n\n{_format_list(ctas)}"

    if any(w in msg for w in {"שחור", "⬛", "black", "dark", "כהה", "1"}):
        color = "black"
    elif any(w in msg for w in {"לבן", "⬜", "white", "light", "בהיר", "2"}):
        color = "white"
    else:
        return "שחור ⬛ או לבן ⬜?"

    body_text  = data.get("body_text", "")
    hook       = data.get("hook", "")
    cta        = data.get("cta", "")
    body_slides = _split_body_into_slides(body_text)
    if not body_slides:
        body_slides = [body_text] if body_text else []

    all_slides = [hook] + body_slides + [cta]
    preview    = _format_structure_preview(all_slides)

    update_conversation_flow(user.id, "carousel_creation", {
        **data, "step": "awaiting_structure_approval", "color": color, "slides": all_slides
    })
    return (
        f"מבנה הקרוסלה ({len(all_slides)} דפים):\n\n"
        f"{preview}\n\n"
        "✅ לפרסם\n"
        "✏️ ערכי דף [מספר]\n"
        "💾 שמרי כטיוטה"
    )


def _handle_structure_approval(user, data: dict, business, msg: str) -> str:
    slides = data.get("slides", [])
    intent = classify_intent(msg, "awaiting_structure_approval")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if "✅" in msg or msg in {"כן", "לפרסם", "פרסמי", "אשרי"} or intent == "approve":
        return _publish(user, business, slides, data.get("color", "black"))

    if "💾" in msg or "טיוטה" in msg:
        return _save_draft(user)

    match = re.search(r"(\d+)", msg)
    if match and any(w in msg for w in {"ערכי", "דף", "שנה", "ערוך", "תשני"}):
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(slides):
            update_conversation_flow(user.id, "carousel_creation", {
                **data, "step": "awaiting_slide_edit", "slide_edit_index": idx
            })
            return f"דף {idx + 1} כרגע:\n\n{slides[idx]}\n\nכתבי את הגרסה החדשה:"
        return f"לא נמצא דף {idx + 1} — יש {len(slides)} דפים בסך הכל."

    preview = _format_structure_preview(slides)
    return (
        f"מבנה הקרוסלה ({len(slides)} דפים):\n\n"
        f"{preview}\n\n"
        "✅ לפרסם\n"
        "✏️ ערכי דף [מספר]\n"
        "💾 שמרי כטיוטה"
    )


def _handle_slide_edit(user, data: dict, msg: str) -> str:
    intent = classify_intent(msg, "awaiting_slide_edit")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if intent == "back":
        slides  = data.get("slides", [])
        preview = _format_structure_preview(slides)
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_structure_approval"
        })
        return (
            f"חזרנו למבנה הקרוסלה:\n\n{preview}\n\n"
            "✅ לפרסם  |  ✏️ ערכי דף [מספר]  |  💾 טיוטה"
        )

    if not msg:
        return "כתבי את הטקסט החדש לדף:"

    slides = list(data.get("slides", []))
    idx    = data.get("slide_edit_index", 0)
    if 0 <= idx < len(slides):
        slides[idx] = msg

    update_conversation_flow(user.id, "carousel_creation", {
        **data, "step": "awaiting_structure_approval", "slides": slides
    })
    preview = _format_structure_preview(slides)
    return (
        f"דף {idx + 1} עודכן.\n\n{preview}\n\n"
        "✅ לפרסם  |  ✏️ ערכי דף [מספר]  |  💾 טיוטה"
    )


# ─── Publishing ────────────────────────────────────────────────────────────────

def _publish(user, business, slides: list, color: str) -> str:
    from src.db.repositories.social_account import SocialAccountRepository
    from src.specialists.publishing.instagram import publish_carousel_to_instagram
    from src.brain.carousel_image import generate_slide_and_upload

    clear_conversation_flow(user.id)

    if not business:
        return "לא נמצא עסק מחובר."

    ig_accounts = SocialAccountRepository().get_by_business(business.id, platform="instagram")
    if not ig_accounts:
        return "אין חשבון אינסטגרם מחובר.\nחברי חשבון ונסי שוב."

    ig = ig_accounts[0]
    ig_user_id   = ig.get("platform_account_id")
    access_token = ig.get("access_token")

    if not ig_user_id or not access_token:
        return "נתוני החשבון חסרים — חברי מחדש."

    try:
        total     = len(slides)
        slide_urls = []
        for i, text in enumerate(slides):
            url = generate_slide_and_upload(text, color, slide_num=i + 1, total=total)
            slide_urls.append(url)
            print(f"[CAROUSEL] slide {i + 1}/{total} → {url}")

        caption  = slides[0] if slides else ""
        post_url = publish_carousel_to_instagram(ig_user_id, slide_urls, caption, access_token)
        icon     = "⬛" if color == "black" else "⬜"
        return f"✅ הקרוסלה פורסמה {icon}\n\n{post_url}\n\n{total} דפים"
    except Exception as e:
        err = str(e)
        print(f"[CAROUSEL_FLOW] publish error: {repr(e)}")
        if "190" in err or "expired" in err.lower():
            return "פג תוקף החיבור לאינסטגרם — חברי מחדש."
        if "200" in err or "permission" in err.lower():
            return "חסרות הרשאות פרסום — בדקי שהחשבון מחובר כראוי."
        return f"לא הצלחתי לפרסם — נסי שוב.\n\n({err[:80]})"


def _save_draft(user) -> str:
    clear_conversation_flow(user.id)
    return "הקרוסלה נשמרה. כשתרצי לפרסם, כתבי *פוסט*."


# ─── Claude API helpers ────────────────────────────────────────────────────────

def _call_claude(system: str, user_msg: str, max_tokens: int = 250) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        res = requests.post(
            _API_URL,
            headers={
                "x-api-key":            api_key,
                "anthropic-version":    "2023-06-01",
                "content-type":         "application/json",
            },
            json={
                "model":      _MODEL,
                "max_tokens": max_tokens,
                "system":     system,
                "messages":   [{"role": "user", "content": user_msg}],
            },
            timeout=20,
        )
        data = res.json()
        if res.status_code != 200 or "content" not in data:
            print(f"[CAROUSEL_FLOW] Claude error: {data}")
            return ""
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[CAROUSEL_FLOW] Claude request error: {repr(e)}")
        return ""


def _generate_body(topic: str, brand: str, what_do: str, style: str) -> str:
    system = (
        f"את מנהלת סושיאל לעסק {brand} ({what_do}). סגנון: {style}.\n"
        "כתבי תוכן לקרוסלה: 3-4 נקודות, כל אחת עד 15 מילים, בלי כותרת ובלי הנעה לפעולה.\n"
        "כל נקודה בשורה נפרדת. עברית ישראלית."
    )
    return _call_claude(system, f"נושא: {topic}", max_tokens=220)


def _generate_hook_suggestions(topic: str, body: str, brand: str) -> list:
    system = (
        "כתבי 3 כותרות פתיחה מושכות לקרוסלה (עד 8 מילים כל אחת). "
        "כל כותרת בשורה נפרדת, בלי מספור, בלי מקפים."
    )
    raw = _call_claude(system, f"נושא: {topic}\nתוכן: {body[:180]}", max_tokens=130)
    return _clean_list(raw)[:5]


def _generate_cta_suggestions(brand: str, what_do: str) -> list:
    system = (
        "כתבי 3 הנעות לפעולה קצרות לפוסט אינסטגרם (עד 8 מילים כל אחת). "
        "מגוון סוגים: שמרי, שתפי, כתבי תגובה, שלחי הודעה. "
        "כל הנעה בשורה נפרדת, בלי מספור."
    )
    raw = _call_claude(system, f"עסק: {brand} — {what_do}", max_tokens=100)
    return _clean_list(raw)[:5]


def _split_body_into_slides(body_text: str) -> list:
    if not body_text:
        return []
    # Try to split by existing line breaks first
    lines = [l.strip().lstrip("-•*0123456789. ") for l in body_text.split("\n") if l.strip()]
    if len(lines) >= 2:
        return lines[:4]
    # Ask Claude to split
    system = (
        "חלק את הטקסט הזה ל-2-4 שקופיות לקרוסלה. "
        "כל שקופית עד 15 מילים, רעיון אחד. "
        "כל שקופית בשורה נפרדת, בלי מספור."
    )
    raw = _call_claude(system, body_text, max_tokens=220)
    slides = _clean_list(raw)
    return slides[:4] if slides else [body_text]


# ─── Display helpers ───────────────────────────────────────────────────────────

def _format_structure_preview(slides: list) -> str:
    total = len(slides)
    out   = []
    for i, text in enumerate(slides):
        if i == 0:
            label = "דף 1 — כותרת"
        elif i == total - 1:
            label = f"דף {total} — הנעה לפעולה"
        else:
            label = f"דף {i + 1}"
        preview = text if len(text) <= 55 else text[:52] + "..."
        out.append(f"📄 {label}:\n{preview}")
    return "\n\n".join(out)


def _format_list(items: list) -> str:
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    return "\n".join(f"{emojis[i]} {item}" for i, item in enumerate(items[:5]))


def _pick_from_list(msg: str, items: list):
    mapping = {"1": 0, "2": 1, "3": 2, "4": 3, "5": 4,
               "1️⃣": 0, "2️⃣": 1, "3️⃣": 2, "4️⃣": 3, "5️⃣": 4}
    idx = mapping.get(msg.strip())
    if idx is not None and idx < len(items):
        return items[idx]
    return None


def _clean_list(raw: str) -> list:
    lines = [l.strip().lstrip("-•*123456789️⃣. ") for l in raw.split("\n") if l.strip()]
    return [l for l in lines if l]


def _bval(business, field: str, default: str) -> str:
    if not business:
        return default
    return getattr(business, field, None) or default
