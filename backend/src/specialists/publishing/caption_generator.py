import os
import requests

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"

_BASE_SYSTEM = """את מיה — מנהלת סושיאל ישראלית בכירה.

עסק: {brand_name}
תיאור: {what_you_do}
טון: {style}
קהל יעד: {audience}

עברית בלבד. חשבי בעברית, כתבי בעברית. אל תתרגמי מאנגלית.

אורך: עד 5 שורות. עד 50 מילים. כל מילה מיותרת — מחקי.
מבנה: הוק חד ← הקשר קצר ← קריאה לפעולה. שלושה שלבים, ולא יותר.

כללים:
- עברית כמו שישראלית כותבת לחברה בוואטסאפ, לא כמו מאמר.
- משפט אחד = רעיון אחד. לא שני רעיונות באותו משפט.
- דקדוק: זכר/נקבה, יחיד/רבים — חייב להיות מדויק.
- אמוג'י: עד 2, רק אם מוסיפים, לא כסיום שגרתי.
- אין "כי", אין "בגלל", אין "כאשר" — שפה דיבורית, לא כתיבת עיתון.
- אין ביטויים חלולים: "ביחד נצליח", "הדרך שלך מתחילה כאן", "כי אתם שווים".

החזירי רק את הטקסט. ללא כותרות, ללא הסברים."""

_VISUAL_FIRST_ADDITION = """

ויז'ואל פירסט:
התמונה היא הנכס הראשי. הקפטשן אומר רק את 20% שהתמונה לא יכולה לומר לבד.

ניתוח התמונה: {image_analysis}
מטרת הפוסט: {goal}

חוקים:
- אל תתארי מה שנראה בתמונה — הקהל כבר רואה את זה.
- הקפטשן חייב להוסיף מה שהתמונה לא יכולה לומר: רגש עמוק יותר, הקשר, משמעות.
- בחרי מטרה אחת ובנו את כל הקפטשן סביבה.
- הקריאה לפעולה חייבת לנבוע באופן טבעי מהטון הרגשי של התמונה.

התמונה והקפטשן יחד = סיפור שלם אחד."""


def _resolve_style(writing_style: str) -> str:
    style_map = {
        "1": "חמים ואישי",
        "חמים": "חמים ואישי",
        "2": "מקצועי",
        "מקצועיים": "מקצועי",
        "3": "שילוב של חמים ומקצועי",
        "שילוב": "שילוב של חמים ומקצועי",
    }
    return next((v for k, v in style_map.items() if k in (writing_style or "")), "שילוב של חמים ומקצועי")


def _resolve_audience(what_you_do: str) -> str:
    desc = (what_you_do or "").lower()
    if any(w in desc for w in ["נשים", "אמהות", "בנות", "אישה"]):
        return "נשים. כתבי בלשון נקבה — את, שלך, בואי, תרגישי. פני ישירות לאחת."
    if any(w in desc for w in ["גברים", "בחורים", "אנשים"]):
        return "גברים. כתבי בלשון זכר — אתה, שלך, בוא, תרגיש. פנה ישירות לאחד."
    return "קהל רחב. כתבי בלשון ניטרלית ומכילה."


def generate_caption(brand_name: str, what_you_do: str, writing_style: str,
                     writing_language: str, topic: str, edit_note: str = None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    system = _BASE_SYSTEM.format(
        brand_name=brand_name or "עסק",
        what_you_do=what_you_do or "עוזר ללקוחות",
        style=_resolve_style(writing_style),
        audience=_resolve_audience(what_you_do),
    )

    user_msg = f"כתבי פוסט על: {topic}"
    if edit_note:
        user_msg += f"\n\nהפוסט הקודם צריך שינוי: {edit_note}"

    return _call_api(api_key, system, user_msg)


def generate_caption_for_image(brand_name: str, what_you_do: str, writing_style: str,
                               writing_language: str, image_analysis: str,
                               goal: str, edit_note: str = None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    system = _BASE_SYSTEM.format(
        brand_name=brand_name or "עסק",
        what_you_do=what_you_do or "עוזר ללקוחות",
        style=_resolve_style(writing_style),
        audience=_resolve_audience(what_you_do),
    ) + _VISUAL_FIRST_ADDITION.format(
        image_analysis=image_analysis or "אין ניתוח תמונה זמין.",
        goal=goal,
    )

    user_msg = "כתבי קפטשן לתמונה הזו."
    if edit_note:
        user_msg += f"\n\nהפוסט הקודם צריך שינוי: {edit_note}"

    return _call_api(api_key, system, user_msg)


def _call_api(api_key: str, system: str, user_msg: str) -> str:
    payload = {
        "model": _MODEL,
        "max_tokens": 250,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
    }

    res = requests.post(
        _API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    data = res.json()
    print("CAPTION_GEN status:", res.status_code)

    if res.status_code != 200 or "content" not in data:
        raise RuntimeError(f"Caption generation failed: {data}")

    return data["content"][0]["text"].strip()
