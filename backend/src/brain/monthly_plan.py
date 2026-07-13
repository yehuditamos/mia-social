import os
import re
import calendar
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
from src.specialists.memory.models import User, Business
from src.db.repositories.content_idea import ContentIdeaRepository

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"
_IL_TZ = timezone(timedelta(hours=3))

_HEBREW_MONTHS = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}

_PLAN_SYSTEM = """את מיה — מנהלת סושיאל מדיה ישראלית מקצועית.

פרטי העסק:
עסק: {brand_name}
מה עושים: {what_you_do}
סגנון: {writing_style}
מטרות: {goals}

רעיונות מבנק הרעיונות (שלבי אותם בתוכנית):
{ideas}

צרי גאנט תוכן חודשי ל{month} ({year}).

פורמט:
📅 [תאריך] [יום בשבוע] — [פוסט / סטורי / ריל / יום מנוחה]
[📸/🎬/✍️] [תיאור קצר מה לשלוח]
🎯 [מטרה: reach / ליד / אמון / engagement]

כללים:
- 18-22 ימי פרסום, השאר יום מנוחה
- לפחות ריל אחד בשבוע (reach), פוסט אחד (ערך), 2 סטוריז (קשר)
- שלבי רעיונות מהבנק (סמני אותם ב-💡)
- עברית ישראלית קצרה וברורה
- סיימי עם שורת עידוד"""

_PARSE_SCHEDULE_SYSTEM = """חלצי מהתשובה הבאה:
1. יום בחודש (מספר 1-31)
2. שעה (פורמט HH:MM)

ענה רק בפורמט:
DAY: 25
TIME: 10:00

אם לא ברור — השתמש בברירת מחדל: DAY: 25, TIME: 09:00"""


def generate_monthly_plan(user: User, business: Business) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "מצטערת, לא יכולה לייצר תוכנית כרגע."

    now_il = datetime.now(_IL_TZ)
    if now_il.day >= 20:
        target = now_il + timedelta(days=20)
    else:
        target = now_il
    next_month_num = (target.month % 12) + 1
    next_year = target.year + (1 if next_month_num == 1 else 0)
    month_name = _HEBREW_MONTHS[next_month_num]

    # Pull ideas from bank
    ideas_text = "אין רעיונות שמורים עדיין."
    if business:
        ideas = ContentIdeaRepository().get_unused(business.id)
        if ideas:
            ideas_text = "\n".join(f"💡 {i['title']}: {i['description']}" for i in ideas)

    system = _PLAN_SYSTEM.format(
        brand_name=_val(business, "brand_name", "העסק"),
        what_you_do=_val(business, "what_you_do", ""),
        writing_style=_val(business, "writing_style", "חמים ואישי"),
        goals=_val(business, "goals", "לא הוגדרו"),
        ideas=ideas_text,
        month=month_name,
        year=next_year,
    )

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
                "max_tokens": 1800,
                "system": system,
                "messages": [{"role": "user", "content": "צרי את הגאנט החודשי."}],
            },
            timeout=45,
        )
        data = res.json()
        print(f"[MONTHLY_PLAN] Claude status={res.status_code}")
        if res.status_code != 200 or "content" not in data:
            raise RuntimeError(f"Claude error: {data}")
        plan = data["content"][0]["text"].strip()

        # Save plan to DB
        if business:
            _save_plan(business.id, f"{month_name} {next_year}", plan)

        return f"🗓️ גאנט תוכן — {month_name} {next_year}\n\n{plan}"
    except Exception as e:
        print(f"[MONTHLY_PLAN ERROR] {repr(e)}")
        return "מצטערת, לא הצלחתי לייצר את הגאנט. נסי שוב."


def handle_setup_planning(user: User, business: Business, message: str) -> str:
    """Parse planning day/time from user message and save it."""
    from src.specialists.memory.engine import upsert_business_field, clear_conversation_flow

    api_key = os.getenv("ANTHROPIC_API_KEY")
    day, time_str = 25, "09:00"

    if api_key:
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
                    "max_tokens": 40,
                    "system": _PARSE_SCHEDULE_SYSTEM,
                    "messages": [{"role": "user", "content": message}],
                },
                timeout=15,
            )
            text = res.json()["content"][0]["text"].strip()
            print(f"[PLANNING SETUP] Claude: {text}")
            lines = {}
            for line in text.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    lines[k.strip()] = v.strip()
            if "DAY" in lines:
                day = max(1, min(31, int(lines["DAY"])))
            if "TIME" in lines:
                time_str = lines["TIME"].strip()
        except Exception as e:
            print(f"[PLANNING SETUP] parse error: {repr(e)}")

    # Save to businesses
    upsert_business_field(user.id, "planning_day", str(day))
    upsert_business_field(user.id, "planning_time", time_str)

    # Create first monthly reminder
    _create_first_planning_reminder(user, business, day, time_str)

    clear_conversation_flow(user.id)
    return (
        f"✅ מושלם! 🗓️\n\n"
        f"כל {_ordinal(day)} לחודש בשעה {time_str} מיה תיזום ישיבת תכנון תוכן.\n\n"
        f"תוכלי גם להגיד לי 'תכנן חודש' בכל עת ואייצר לך גאנט 💜"
    )


def _create_first_planning_reminder(user: User, business, day: int, time_str: str) -> None:
    from src.db.connection import get_base_url, get_headers

    now_il = datetime.now(_IL_TZ)
    hour, minute = (int(p) for p in (time_str + ":00").split(":")[:2])

    # Find next occurrence of this day
    target = now_il.replace(day=1)
    if now_il.day < day:
        try:
            target = now_il.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            pass
    else:
        # Next month
        if now_il.month == 12:
            target = now_il.replace(year=now_il.year + 1, month=1, day=1)
        else:
            target = now_il.replace(month=now_il.month + 1, day=1)
        max_day = calendar.monthrange(target.year, target.month)[1]
        target = target.replace(day=min(day, max_day), hour=hour, minute=minute, second=0, microsecond=0)

    brand = _val(business, "brand_name", "")
    ideas_count = ContentIdeaRepository().count_unused(business.id) if business else 0
    ideas_note = f"יש לנו כבר {ideas_count} רעיונות בבנק!" if ideas_count else "נאסוף רעיונות עד אז!"

    content = (
        f"🗓️ היי {user.name or ''}! היום בונות תוכן לחודש הבא 💜\n"
        f"{ideas_note}\n\n"
        f"כתבי *תכנן חודש* כשמוכנה!"
    )

    target_utc = target.astimezone(timezone.utc)

    res = requests.post(
        f"{get_base_url()}/reminders",
        headers=get_headers(),
        json={
            "user_id": user.id,
            "phone_number": user.phone_number,
            "content": content,
            "remind_at": target_utc.isoformat(),
            "sent": False,
            "recurrence": "monthly",
            "recurrence_day": day,
        },
    )
    print(f"[PLANNING REMINDER] Created for {target.strftime('%d/%m/%Y %H:%M')} status={res.status_code}")


def _save_plan(business_id: str, month: str, plan_text: str) -> None:
    from src.db.connection import get_base_url, get_headers
    requests.post(
        f"{get_base_url()}/content_plans",
        headers=get_headers(prefer="resolution=merge-duplicates,return=minimal"),
        json={"business_id": business_id, "month": month, "plan_text": plan_text},
    )


def _ordinal(day: int) -> str:
    return f"{day}"


def _val(business, field: str, default: str) -> str:
    if not business:
        return default
    return getattr(business, field, None) or default
