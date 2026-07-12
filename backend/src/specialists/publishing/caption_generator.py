import os
import requests


_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"


def generate_caption(brand_name: str, what_you_do: str, writing_style: str,
                     writing_language: str, topic: str, edit_note: str = None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    lang_instruction = "Write in Hebrew." if writing_language and "עברית" in writing_language else "Write in English."
    if writing_language and "שתי" in writing_language:
        lang_instruction = "Write in Hebrew."

    style_map = {
        "1": "warm and personal",
        "חמים": "warm and personal",
        "2": "professional",
        "מקצועיים": "professional",
        "3": "a mix of warm and professional",
        "שילוב": "a mix of warm and professional",
    }
    style = next((v for k, v in style_map.items() if k in (writing_style or "")), "warm and professional")

    system = f"""אתה קופירייטר ישראלי מנוסה המתמחה בסושיאל מדיה.

העסק: {brand_name or 'עסק'}
תיאור: {what_you_do or 'עוזר ללקוחות'}
טון: {style}

כללי כתיבה מחייבים:

1. כתבי עברית ישראלית טבעית ושוטפת בלבד — כפי שכותבת קופירייטרית ישראלית מנוסה.
   אסור לתרגם מאנגלית. כל משפט חייב להישמע כאילו נכתב במקור בעברית.

2. דקדוק מושלם — התאמת מין, מספר, נטיית פעלים, ניקוד משפטים.
   לפני שליחה — בצעי בדיקת הגהה מלאה.

3. פנייה בלשון נקבה תמיד:
   ✓ את, שלך, יכולה, בואי, תרגישי
   ✗ אתה, שלך (זכר), יכול

4. שפת שיווק ישראלית עכשווית — חמה, אמיתית, אנושית.
   ✗ לא רובוטי. לא ספרותי. לא טקסטבוק.

5. אסור להמציא מילים בעברית. אם ביטוי נשמע מאולץ — תנסחי מחדש.

6. מבנה רגשי לכל פוסט:
   • פתיחה חזקה שמושכת תשומת לב
   • חיבור רגשי
   • תועלת ברורה
   • קריאה לפעולה טבעית

7. אמוג'י — עד 1-2 לפסקה, בצורה טבעית.

8. האשטאגים — עד 5 בלבד, רק כאלה שישראלים משתמשים בהם באמת.

לפני כל תגובה שאלי את עצמך: "האם קופירייטרית ישראלית מנוסה הייתה מפרסמת את זה ללא עריכה?"
אם התשובה לא — תשכתבי. חזרי על זה עד שהתשובה כן.

החזירי את הקפטשן בלבד — ללא הסברים, ללא כותרות, ללא מטא-טקסט."""

    user_msg = f"Write a caption about: {topic}"
    if edit_note:
        user_msg += f"\n\nPrevious caption needs this change: {edit_note}"

    payload = {
        "model": _MODEL,
        "max_tokens": 512,
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
