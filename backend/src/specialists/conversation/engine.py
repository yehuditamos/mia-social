from personality.loader import get_string
from src.specialists.memory.models import User, ConversationState
from src.specialists.memory.engine import (
    update_user,
    get_business,
    upsert_business_field,
    update_conversation_state,
)
from src.specialists.conversation.onboarding import STEPS, NUM_STEPS

_ACCESSIBILITY_YES = {"yes", "1", "sure", "ok", "ken", "כן"}

_PLANNING_MAP = {
    "1": (1,  "09:00"),
    "1️⃣": (1,  "09:00"),
    "תחילת": (1,  "09:00"),
    "בתחילת": (1, "09:00"),
    "2": (25, "09:00"),
    "2️⃣": (25, "09:00"),
    "שבוע אחרון": (25, "09:00"),
    "בשבוע": (25, "09:00"),
    "3": (15, "09:00"),
    "3️⃣": (15, "09:00"),
    "תאריך קבוע": (15, "09:00"),
    "קבוע": (15, "09:00"),
}


def _parse_accessibility(answer: str) -> bool:
    return answer.strip().lower() in _ACCESSIBILITY_YES


def _parse_planning(answer: str):
    """Returns (day, time) or (None, None) if user chose 'not now'."""
    a = answer.strip().lower()
    # "not now" choices → return None to skip
    if any(w in a for w in {"4", "4️⃣", "לא עכשיו", "לא", "בהמשך", "skip"}):
        return (None, None)
    for key, val in _PLANNING_MAP.items():
        if key in a:
            return val
    # Try to extract a number like "15" or "20 בשעה 10"
    import re
    day_match = re.search(r'\b(\d{1,2})\b', a)
    time_match = re.search(r'(\d{1,2}):(\d{2})', a)
    day = int(day_match.group(1)) if day_match else None
    if day and 1 <= day <= 31:
        time = f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else "09:00"
        return (day, time)
    return (None, None)


def _save_answer(step: int, answer: str, user: User) -> None:
    entity, field = STEPS[step]["save_to"]

    if entity == "user":
        if field == "name":
            user.name = answer
        elif field == "accessibility":
            user.accessibility = _parse_accessibility(answer)
        update_user(user)

    elif entity == "business":
        if field == "planning_schedule":
            day, time = _parse_planning(answer)
            if day is not None:
                upsert_business_field(user.id, "planning_day", day)
                upsert_business_field(user.id, "planning_time", time)
        else:
            upsert_business_field(user.id, field, answer)


def _format_question(step: int, user: User, language: str = "he") -> str:
    key = STEPS[step]["key"]
    return get_string(key, language=language, name=user.name or "")


def _build_completion(user: User, language: str = "he") -> str:
    business = get_business(user.id)
    return get_string(
        "completion_message",
        language=language,
        name=user.name or "",
        brand_name=business.brand_name if business else "",
        what_you_do=business.what_you_do if business else "",
        writing_style=business.writing_style if business else "",
    )


def handle_new_user(user: User, language: str = "he") -> str:
    return _format_question(0, user, language)


def handle_onboarding(user: User, state: ConversationState, message: str, language: str = "he") -> str:
    step = state.step
    _save_answer(step, message.strip(), user)

    next_step = step + 1
    update_conversation_state(user.id, next_step)

    if next_step >= NUM_STEPS:
        return _build_completion(user, language)

    return _format_question(next_step, user, language)
