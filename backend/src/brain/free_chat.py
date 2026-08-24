import os
import requests
from typing import Optional
from src.specialists.memory.models import User, Business

_API_URL = "https://api.openai.com/v1/responses"
_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")

_CHAT_SYSTEM = """את מיה — מנהלת סושיאל מדיה ישראלית שעובדת עם {brand_name} דרך וואטסאפ.

פרטי העסק:
מה עושים: {what_you_do}
סגנון כתיבה: {writing_style}
מטרות עסקיות: {goals}

כללים לשיחה:
- עברית ישראלית ישירה — לא תרגום, לא פורמלי
- פנייה תמיד בלשון יחיד נקבה: "את", "תרצי", "תשלחי", "שלחי" — לא "אתם", "תרצו", "שלחו"
- לעולם אל תתווכחי עם המשתמשת — אם ביקשה לפרסם קרוסלה/פוסט/ריל, עשי זאת בלי להסביר למה זה לא יעבוד
- עד 3 משפטים בתשובה — ממוקדת ועניינית
- תמיד חשבי על המטרה העסקית מאחורי הבקשה
- כשמציעה רעיון תוכן: ציני מה לשלוח (📸/🎬/✍️) ולמה (מטרה)
- כשהמשתמשת רוצה לפרסם: "שלחי לי [תמונה/סרטון] ונמשיך"
- אל תציגי תפריט ממוספר — שיחה טבעית
- אל תסבירי מה את עושה — פשוט עשי
- אסור: "איזה כיף", "יאאא", "וואו", "מדהים", "💜💜💜", "חמודה" וכל ביטוי ריק אחר
- תשובה עניינית = מקצועיות. סגנון חם = בחירת מילים, לא אמוג'ים מיותרים"""

_PLAN_SYSTEM = """את מיה — מנהלת סושיאל מדיה ישראלית מקצועית.

פרטי העסק:
עסק: {brand_name}
מה עושים: {what_you_do}
סגנון כתיבה: {writing_style}
מטרות עסקיות: {goals}

בני תוכנית תוכן ל-7 ימים שמכוונת למטרות העסק.

פורמט לכל יום:
יום X — [פוסט / סטורי / ריל / מנוחה]
📸/🎬/✍️ מה לשלוח — תיאור קצר
💬 כיתוב / נושא — משפט אחד
🎯 מטרה — (reach / ליד / engagement / אמון)

כללים:
- יום אחד מנוחה (ד׳ או שבת)
- שלב סוגי תוכן — לא כל יום פוסט
- כל נושא חייב לנבוע מהמטרות העסקיות
- עברית ישראלית קצרה ומעשית
- פנייה למשתמשת בלשון יחיד נקבה בלבד: "את", "תרצי", "שלחי" — לא "אתם", "תרצו"
- סיימי בשורת עידוד קצרה"""


def handle_free_chat(user: User, business: Optional[Business], message: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "מיה כאן 💜 שלחי תמונה/סרטון לפרסום, או שאלי אותי כל שאלה."

    system = _CHAT_SYSTEM.format(
        brand_name=_val(business, "brand_name", "העסק"),
        what_you_do=_val(business, "what_you_do", ""),
        writing_style=_val(business, "writing_style", "חמים ואישי"),
        goals=_val(business, "goals", "לא הוגדרו עדיין"),
    )

    try:
        return _call_openai(api_key, system, message, max_tokens=350)
    except Exception as e:
        print(f"[FREE_CHAT ERROR] {repr(e)}")
        return "מיה כאן 💜 תני לי רגע ונסי שוב."


def handle_weekly_plan(user: User, business: Optional[Business]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "מצטערת, לא יכולה לייצר תוכנית כרגע. נסי שוב בעוד רגע."

    system = _PLAN_SYSTEM.format(
        brand_name=_val(business, "brand_name", "העסק"),
        what_you_do=_val(business, "what_you_do", ""),
        writing_style=_val(business, "writing_style", "חמים ואישי"),
        goals=_val(business, "goals", "לא הוגדרו עדיין"),
    )

    try:
        plan = _call_openai(api_key, system, "בני תוכנית תוכן שבועית.", max_tokens=900)
        brand = _val(business, "brand_name", "העסק")
        return f"📅 תוכנית תוכן שבועית — {brand}\n\n{plan}"
    except Exception as e:
        print(f"[WEEKLY_PLAN ERROR] {repr(e)}")
        return "מצטערת, לא הצלחתי לייצר תוכנית כרגע. נסי שוב בעוד רגע."


def _call_openai(api_key: str, system: str, message: str, max_tokens: int = 350) -> str:
    res = requests.post(
        _API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        json={
            "model": _MODEL,
            "instructions": system,
            "input": message,
            "max_output_tokens": max_tokens,
            "store": False,
        },
        timeout=25,
    )
    data = res.json()
    print(f"[FREE_CHAT] OpenAI status={res.status_code} request_id={res.headers.get('x-request-id', '')}")
    if res.status_code != 200:
        raise RuntimeError(f"OpenAI API error: {data}")
    return _extract_output_text(data)


def _extract_output_text(data: dict) -> str:
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"].strip()
    raise RuntimeError("OpenAI response did not contain output text")


def describe_image_accessibility(image_b64: str, mime_type: str, extra_note: str = None) -> str:
    """Describe an image in Hebrew for a blind user using GPT vision."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "לא הצלחתי לתאר את התמונה."

    # Strip codec suffix for safety
    base_mime = mime_type.split(";")[0].strip()

    system = (
        "תארי את התמונה בעברית ישראלית ברורה ופשוטה, "
        "עבור משתמש עיוור שרוצה לדעת מה בתמונה לפני שמפרסם אותה. "
        "ציוני: מה רואים, אנשים (תיאור כללי), צבעים עיקריים, מיקום, אווירה. "
        "3-4 משפטים קצרים. אל תזכירי שאת AI."
    )
    if extra_note:
        system += f"\n\nהמשתמשת ביקשה להוסיף/לשנות: {extra_note}. שלבי את זה בתיאור."

    try:
        res = requests.post(
            _API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            json={
                "model": _MODEL,
                "instructions": system,
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "תארי לי את התמונה."},
                        {
                            "type": "input_image",
                            "image_url": f"data:{base_mime};base64,{image_b64}",
                        },
                    ],
                }],
                "max_output_tokens": 300,
                "store": False,
            },
            timeout=25,
        )
        data = res.json()
        print(f"[VISION] status={res.status_code}")
        if res.status_code != 200:
            print(f"[VISION] error: {data}")
            return "לא הצלחתי לתאר את התמונה."
        return _extract_output_text(data)
    except Exception as e:
        print(f"[VISION ERROR] {repr(e)}")
        return "לא הצלחתי לתאר את התמונה."


def _val(business: Optional[Business], field: str, default: str) -> str:
    if not business:
        return default
    return getattr(business, field, None) or default
