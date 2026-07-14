import os
import re
import requests
from src.specialists.memory.models import User, Business
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"

_CANCEL_WORDS = {"ביטול", "בטל", "בטלי", "❌", "cancel", "חזרה", "תפריט"}


def handle_carousel_flow(user, state, business, message: str, language: str = "he") -> str:
    msg = message.strip()
    if msg.lower() in _CANCEL_WORDS:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלתי 💜 מה תרצי לעשות?"

    data = state.flow_data or {}
    step = data.get("step", "awaiting_mode")

    if step == "awaiting_mode":
        return _handle_mode(user, state, business, msg)
    if step == "awaiting_topic":
        return _handle_topic(user, state, business, msg)
    if step == "awaiting_own_text":
        return _handle_own_text(user, state, business, msg)
    if step == "awaiting_proofread_approval":
        return _handle_proofread_approval(user, state, business, msg)
    if step == "awaiting_hook":
        return _handle_hook(user, state, business, msg)
    if step == "awaiting_cta":
        return _handle_cta(user, state, business, msg)
    if step == "awaiting_color":
        return _handle_color(user, state, business, msg)
    if step == "awaiting_structure_approval":
        return _handle_structure_approval(user, state, business, msg)
    if step == "awaiting_slide_edit":
        return _handle_slide_edit(user, state, business, msg)

    clear_conversation_flow(user.id)
    return "נתחיל מחדש? כתבי *פוסט* 💜"


def _handle_mode(user, state, business, msg: str) -> str:
    if msg in {"1", "1️⃣"} or ("כתבי" in msg and "לבד" not in msg):
        update_conversation_flow(user.id, "carousel_creation", {"step": "awaiting_topic"})
        return "מה הנושא לפוסט? כמה מילים ומיה תכתוב 💡"
    if msg in {"2", "2️⃣"} or "לבד" in msg or "בעצמ" in msg or ("אני" in msg and "אכתוב" in msg):
        update_conversation_flow(user.id, "carousel_creation", {"step": "awaiting_own_text"})
        return "כתבי את הטקסט שלך — לא צריך מושלם, מיה תגהה ✏️"
    return "בואי ניצור פוסט לאינסטגרם! 📝\n\n1️⃣ כתבי עבורי — תאריי נושא ומיה תכתוב\n2️⃣ אני אכתוב לבד — מיה תגהה"


def _handle_topic(user, state, business, msg: str) -> str:
    if len(msg) < 3:
        return "ספרי לי עוד קצת על הנושא 😊"

    brand = _bval(business, "brand_name", "העסק")
    what_do = _bval(business, "what_you_do", "")
    style = _bval(business, "writing_style", "חמים ואישי")

    body = _generate_body(msg, brand, what_do, style)
    if not body:
        return "אופס, לא הצלחתי לייצר תוכן. נסי שוב 💜"

    hooks = _generate_hook_suggestions(msg, body, brand)
    if not hooks:
        hooks = [f"כל מה שצריך לדעת על {msg}", f"הסוד שאנשים לא יודעים על {msg}"]

    update_conversation_flow(user.id, "carousel_creation", {
        "step": "awaiting_hook",
        "topic": msg,
        "body_text": body,
        "hook_suggestions": hooks,
    })
    return (
        "מה תרצי שיופיע בדף הראשון — כדי למשוך תשומת לב? 👆\n\n"
        f"{_format_list(hooks)}\n\n"
        "בחרי מספר או כתבי כותרת משלך:"
    )


def _handle_own_text(user, state, business, msg: str) -> str:
    if len(msg) < 5:
        return "כתבי את הטקסט שלך — אפשר כמה משפטים ✏️"

    from src.brain.text_editor import proofread_text, proofread_preview
    corrected = proofread_text(msg)
    preview = proofread_preview(msg, corrected)

    update_conversation_flow(user.id, "carousel_creation", {
        "step": "awaiting_proofread_approval",
        "original_text": msg,
        "corrected_text": corrected,
    })
    return preview


def _handle_proofread_approval(user, state, business, msg: str) -> str:
    from src.brain.text_editor import proofread_preview
    data = state.flow_data or {}
    original = data.get("original_text", "")
    corrected = data.get("corrected_text", "")

    if "✅" in msg or msg in {"1", "כן", "אשרי"}:
        body = corrected
    elif "🔄" in msg or "מקורי" in msg or "חזרי" in msg:
        body = original
    elif "✏️" in msg or "ערכי" in msg:
        update_conversation_flow(user.id, "carousel_creation", {
            "step": "awaiting_own_text",
            "topic": data.get("topic", ""),
        })
        return "כתבי את הגרסה המעודכנת:"
    else:
        return proofread_preview(original, corrected)

    brand = _bval(business, "brand_name", "העסק")
    topic = data.get("topic", body[:40])
    hooks = _generate_hook_suggestions(topic, body, brand)
    if not hooks:
        hooks = ["כותרת שמושכת עניין"]

    update_conversation_flow(user.id, "carousel_creation", {
        "step": "awaiting_hook",
        "topic": topic,
        "body_text": body,
        "hook_suggestions": hooks,
    })
    return (
        "מה תרצי שיופיע בדף הראשון — כדי למשוך תשומת לב? 👆\n\n"
        f"{_format_list(hooks)}\n\n"
        "בחרי מספר או כתבי כותרת משלך:"
    )


def _handle_hook(user, state, business, msg: str) -> str:
    data = state.flow_data or {}
    suggestions = data.get("hook_suggestions", [])

    hook = _pick_from_list(msg, suggestions) or msg
    if not hook:
        return "בחרי כותרת לדף הראשון:"

    brand = _bval(business, "brand_name", "העסק")
    what_do = _bval(business, "what_you_do", "")
    ctas = _generate_cta_suggestions(brand, what_do)
    if not ctas:
        ctas = ["שמרי את הפוסט הזה 📌", "שתפי עם מי שצריכה לשמוע 💌", "כתבי לי בפרטי ואשמח לעזור"]

    new_data = {**data, "step": "awaiting_cta", "hook": hook, "cta_suggestions": ctas}
    update_conversation_flow(user.id, "carousel_creation", new_data)
    return (
        "מה תרצי שיופיע בדף האחרון — הנעה לפעולה? ✨\n\n"
        f"{_format_list(ctas)}\n\n"
        "בחרי מספר או כתבי משלך:"
    )


def _handle_cta(user, state, business, msg: str) -> str:
    data = state.flow_data or {}
    suggestions = data.get("cta_suggestions", [])

    cta = _pick_from_list(msg, suggestions) or msg
    if not cta:
        return "בחרי הנעה לפעולה לדף האחרון:"

    new_data = {**data, "step": "awaiting_color", "cta": cta}
    update_conversation_flow(user.id, "carousel_creation", new_data)
    return "איזה רקע לקרוסלה?\n\n⬛ שחור — טקסט לבן\n⬜ לבן — טקסט שחור"


def _handle_color(user, state, business, msg: str) -> str:
    data = state.flow_data or {}

    if any(w in msg for w in {"שחור", "⬛", "black", "dark", "1"}):
        color = "black"
    elif any(w in msg for w in {"לבן", "⬜", "white", "light", "2"}):
        color = "white"
    else:
        return "שחור ⬛ או לבן ⬜?"

    body_text = data.get("body_text", "")
    hook = data.get("hook", "")
    cta = data.get("cta", "")

    body_slides = _split_body_into_slides(body_text)
    if not body_slides:
        body_slides = [body_text] if body_text else []

    all_slides = [hook] + body_slides + [cta]
    preview = _format_structure_preview(all_slides)

    new_data = {**data, "step": "awaiting_structure_approval", "color": color, "slides": all_slides}
    update_conversation_flow(user.id, "carousel_creation", new_data)
    return (
        f"הנה המבנה של הקרוסלה ({len(all_slides)} דפים):\n\n"
        f"{preview}\n\n"
        "✅ לפרסם כך\n"
        "✏️ ערכי דף [מספר]\n"
        "💾 שמרי כטיוטה"
    )


def _handle_structure_approval(user, state, business, msg: str) -> str:
    data = state.flow_data or {}
    slides = data.get("slides", [])

    if "✅" in msg or msg in {"כן", "לפרסם", "פרסמי", "אשרי"}:
        return _publish(user, business, slides, data.get("color", "black"))

    if "💾" in msg or "טיוטה" in msg:
        return _save_draft(user, slides)

    match = re.search(r"(\d+)", msg)
    if match and any(w in msg for w in {"ערכי", "דף", "שנה", "ערוך", "תשני"}):
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(slides):
            new_data = {**data, "step": "awaiting_slide_edit", "slide_edit_index": idx}
            update_conversation_flow(user.id, "carousel_creation", new_data)
            return f"📝 דף {idx + 1} כרגע:\n\n{slides[idx]}\n\nכתבי את הגרסה החדשה:"
        return f"לא נמצא דף {idx + 1}. יש {len(slides)} דפים."

    preview = _format_structure_preview(slides)
    return (
        f"הנה המבנה ({len(slides)} דפים):\n\n"
        f"{preview}\n\n"
        "✅ לפרסם כך\n"
        "✏️ ערכי דף [מספר]\n"
        "💾 שמרי כטיוטה"
    )


def _handle_slide_edit(user, state, business, msg: str) -> str:
    data = state.flow_data or {}
    slides = list(data.get("slides", []))
    idx = data.get("slide_edit_index", 0)

    if not msg:
        return "כתבי את הטקסט החדש לדף:"

    if 0 <= idx < len(slides):
        slides[idx] = msg

    new_data = {**data, "step": "awaiting_structure_approval", "slides": slides}
    update_conversation_flow(user.id, "carousel_creation", new_data)

    preview = _format_structure_preview(slides)
    return (
        f"✅ דף {idx + 1} עודכן!\n\n{preview}\n\n"
        "✅ לפרסם כך\n"
        "✏️ ערכי דף [מספר]\n"
        "💾 שמרי כטיוטה"
    )


def _publish(user, business, slides: list, color: str) -> str:
    from src.db.repositories.social_account import SocialAccountRepository
    from src.specialists.publishing.instagram import publish_carousel_to_instagram
    from src.brain.carousel_image import generate_slide_and_upload

    clear_conversation_flow(user.id)

    if not business:
        return "לא נמצא עסק מחובר."

    ig_accounts = SocialAccountRepository().get_by_business(business.id, platform="instagram")
    if not ig_accounts:
        return "אין חשבון אינסטגרם מחובר 📸\nחברי חשבון ונסי שוב."

    ig = ig_accounts[0]
    ig_user_id = ig.get("platform_account_id")
    access_token = ig.get("access_token")

    if not ig_user_id or not access_token:
        return "נתוני החשבון חסרים. בדקי שהחשבון מחובר כראוי 🔐"

    try:
        total = len(slides)
        slide_urls = []
        for i, text in enumerate(slides):
            url = generate_slide_and_upload(text, color, slide_num=i + 1, total=total)
            slide_urls.append(url)
            print(f"[CAROUSEL_FLOW] slide {i + 1}/{total} → {url}")

        caption = slides[0] if slides else ""
        post_url = publish_carousel_to_instagram(ig_user_id, slide_urls, caption, access_token)
        icon = "⬛" if color == "black" else "⬜"
        return f"✅ הקרוסלה פורסמה! {icon}\n\n{post_url}\n\n{total} דפים"
    except Exception as e:
        err = str(e)
        print(f"[CAROUSEL_FLOW] publish error: {repr(e)}")
        if "190" in err or "expired" in err.lower():
            return "פג תוקף החיבור לאינסטגרם. חזרי להגדרות וחברי מחדש 🔁"
        if "200" in err or "permission" in err.lower():
            return "אין הרשאות פרסום. בדקי שהחשבון מחובר בצורה נכונה 🔐"
        return f"אופס, לא הצלחתי לפרסם. נסי שוב 💜\n\n({err[:80]})"


def _save_draft(user, slides: list) -> str:
    clear_conversation_flow(user.id)
    return "💾 שמרתי את הקרוסלה כטיוטה!\n\nכשתרצי לפרסם כתבי *פוסט* 💜"


def _format_structure_preview(slides: list) -> str:
    total = len(slides)
    out = []
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
    idx = mapping.get(msg)
    if idx is not None and idx < len(items):
        return items[idx]
    return None


def _bval(business, field: str, default: str) -> str:
    if not business:
        return default
    return getattr(business, field, None) or default


def _call_claude(system: str, user_msg: str, max_tokens: int = 250) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        res = requests.post(
            _API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": _MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user_msg}],
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
        f"את מיה, מנהלת סושיאל לעסק: {brand} ({what_do}). סגנון: {style}.\n"
        "כתבי תוכן לפוסט קרוסלה: 3-4 נקודות קצרות (עד 15 מילים כל אחת), "
        "בלי כותרת ובלי הנעה לפעולה. כל נקודה בשורה נפרדת. עברית ישראלית."
    )
    return _call_claude(system, f"נושא: {topic}", max_tokens=220)


def _generate_hook_suggestions(topic: str, body: str, brand: str) -> list:
    system = (
        "כתבי 3 כותרות פתיחה מושכות לפוסט קרוסלה (עד 8 מילים כל אחת). "
        "גרמי לאנשים לעצור ולהמשיך לקרוא. "
        "כל כותרת בשורה נפרדת, ללא מספור ובלי מקפים."
    )
    raw = _call_claude(system, f"נושא: {topic}\nתוכן: {body[:180]}", max_tokens=130)
    if not raw:
        return []
    return _clean_list(raw)[:5]


def _generate_cta_suggestions(brand: str, what_do: str) -> list:
    system = (
        "כתבי 3 הנעות לפעולה קצרות לפוסט אינסטגרם (עד 8 מילים כל אחת). "
        "מגוון — שמרי, שתפי, כתבי בתגובות, שלחי הודעה. "
        "כל הנעה בשורה נפרדת, ללא מספור ובלי מקפים."
    )
    raw = _call_claude(system, f"עסק: {brand} — {what_do}", max_tokens=100)
    if not raw:
        return []
    return _clean_list(raw)[:5]


def _split_body_into_slides(body_text: str) -> list:
    if not body_text:
        return []
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    if len(lines) >= 2:
        return [l.lstrip("-•*0123456789. ") for l in lines[:4]]
    system = (
        "קיבלת תוכן לפוסט קרוסלה. חלק ל-2-4 שקופיות, "
        "כל שקופית עד 15 מילים, רעיון אחד. "
        "כל שקופית בשורה נפרדת, ללא מספור."
    )
    raw = _call_claude(system, body_text, max_tokens=220)
    if not raw:
        return [body_text]
    slides = _clean_list(raw)
    return slides[:4] if slides else [body_text]


def _clean_list(raw: str) -> list:
    lines = [l.strip().lstrip("-•*123456789️⃣. ") for l in raw.split("\n") if l.strip()]
    return [l for l in lines if l]
