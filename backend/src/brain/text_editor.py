import os
import requests

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"

_PROOFREAD_SYSTEM = """אתה עורך תוכן ישראלי מקצועי. תגיה את הטקסט — תיקון בלבד, ללא שכתוב.

מה לתקן:
✓ שגיאות כתיב
✓ פיסוק (נקודות, פסיקים, שאלות, קריאות)
✓ רווחים כפולים, רווח לפני נקודה
✓ ירידות שורה לא הגיוניות
✓ ניסוחים לא ברורים — מינימלי בלבד

מה לא לגעת בו:
✗ סגנון האישי של הכותב
✗ בחירת מילים — אל תחלפי
✗ אמוג'ים
✗ מבנה כללי

החזר את הטקסט המתוקן בלבד, ללא הסברים."""


def proofread_text(text: str) -> str:
    """Return proofreaded version. Returns original on API failure."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return text
    try:
        resp = requests.post(
            _API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": _MODEL,
                "max_tokens": 400,
                "system": _PROOFREAD_SYSTEM,
                "messages": [{"role": "user", "content": text}],
            },
            timeout=10,
        )
        result = resp.json()["content"][0]["text"].strip()
        return result if result else text
    except Exception as e:
        print(f"[PROOFREAD] error: {repr(e)}")
        return text


def proofread_preview(original: str, corrected: str) -> str:
    """Format the proofread result as a WhatsApp reply."""
    if original.strip() == corrected.strip():
        return (
            f"✅ הטקסט תקין, לא מצאתי שגיאות.\n\n"
            f"{original}\n\n"
            f"✅ לפרסם | ✏️ ערכי | ❌ בטלי"
        )
    return (
        f"✏️ מצאתי מספר תיקונים שישפרו את הקריאות. רוצה לאשר אותם?\n\n"
        f"{corrected}\n\n"
        f"✅ אשרי את כל התיקונים | ✏️ ערכי בעצמי | 🔄 חזרי לטקסט המקורי"
    )
