import os
import requests
from datetime import datetime, timezone, timedelta
from src.db.connection import get_base_url, get_headers
from src.specialists.memory.models import User

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"
_IL_TZ = timezone(timedelta(hours=3))

_PARSE_SYSTEM = """חלצי מהודעה הבאה:
1. מתי להזכיר — תאריך ושעה בתבנית ISO8601 בזמן ישראל (UTC+3)
2. מה להזכיר — תיאור קצר (עד 8 מילים)

היום ושעה נוכחית: {now}

כללי פרשנות:
- "מחר" = יום למחרת בשעה 09:00
- "בשבוע הבא" = +7 ימים בשעה 09:00
- "בעוד X שעות/דקות" = +X מעכשיו
- "בשעה HH:MM" = אותו יום; אם עבר — מחר
- ברירת מחדל לשעה כשלא צוינה: 09:00

ענה רק בפורמט זה, בלי טקסט נוסף:
TIME: 2026-07-14T09:00:00+03:00
CONTENT: תיאור מה להזכיר"""


def handle_reminder_request(user: User, message: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    now_str = datetime.now(_IL_TZ).strftime("%Y-%m-%d %H:%M (ישראל UTC+3)")

    remind_at = None
    content = _strip_trigger_prefix(message)

    if api_key:
        try:
            remind_at, content = _parse_with_claude(api_key, message, now_str)
        except Exception as e:
            print(f"[REMINDER PARSE ERROR] {repr(e)}")

    if not remind_at:
        tomorrow_9am = (datetime.now(_IL_TZ) + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        remind_at = tomorrow_9am.isoformat()

    _save(user.id, user.phone_number, content, remind_at)

    try:
        dt = datetime.fromisoformat(remind_at).astimezone(_IL_TZ)
        time_display = dt.strftime("%d/%m/%Y בשעה %H:%M")
    except Exception:
        time_display = remind_at

    return f"✅ שמרתי תזכורת!\n\n📅 {time_display}\n📝 {content}"


def send_due_reminders() -> int:
    now = datetime.now(timezone.utc).isoformat()
    try:
        res = requests.get(
            f"{get_base_url()}/reminders",
            headers=get_headers(),
            params={"sent": "eq.false", "remind_at": f"lte.{now}", "limit": "50"},
        )
        due = res.json()
        if not isinstance(due, list):
            return 0
    except Exception as e:
        print(f"[REMINDERS] fetch error: {repr(e)}")
        return 0

    from src.whatsapp.client import send_message

    count = 0
    for reminder in due:
        phone = reminder.get("phone_number")
        content = reminder.get("content", "")
        rid = reminder.get("id")
        if not phone or not rid:
            continue
        try:
            send_message(phone, f"⏰ תזכורת מיה:\n\n{content}")
            _mark_sent(rid)
            count += 1
            print(f"[REMINDERS] sent to {phone}: {content[:40]}")
        except Exception as e:
            print(f"[REMINDERS] send error {rid}: {repr(e)}")

    if count:
        print(f"[REMINDERS] sent {count} reminder(s)")
    return count


def _parse_with_claude(api_key: str, message: str, now_str: str):
    system = _PARSE_SYSTEM.format(now=now_str)
    res = requests.post(
        _API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _MODEL,
            "max_tokens": 80,
            "system": system,
            "messages": [{"role": "user", "content": message}],
        },
        timeout=15,
    )
    text = res.json()["content"][0]["text"].strip()
    print(f"[REMINDER PARSE] Claude raw: {text}")

    lines = {}
    for line in text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            lines[k.strip()] = v.strip()

    remind_at = lines.get("TIME", "")
    content = lines.get("CONTENT", "")
    if not remind_at or not content:
        raise ValueError(f"Unparseable: {text}")

    return remind_at, content


def _strip_trigger_prefix(message: str) -> str:
    for prefix in ["תזכירי לי", "תזכיר לי", "תשלחי לי תזכורת"]:
        if message.strip().startswith(prefix):
            return message.strip()[len(prefix):].strip()
    return message.strip()


def _save(user_id: str, phone: str, content: str, remind_at: str) -> None:
    res = requests.post(
        f"{get_base_url()}/reminders",
        headers=get_headers(),
        json={
            "user_id": user_id,
            "phone_number": phone,
            "content": content,
            "remind_at": remind_at,
            "sent": False,
        },
    )
    print(f"[REMINDER SAVE] status={res.status_code} body={res.text[:100]}")


def _mark_sent(reminder_id: str) -> None:
    requests.patch(
        f"{get_base_url()}/reminders",
        headers=get_headers(prefer="return=minimal"),
        params={"id": f"eq.{reminder_id}"},
        json={"sent": True},
    )
