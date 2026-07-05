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


def _parse_accessibility(answer: str) -> bool:
    return answer.strip().lower() in _ACCESSIBILITY_YES


def _save_answer(step: int, answer: str, user: User) -> None:
    entity, field = STEPS[step]["save_to"]

    if entity == "user":
        if field == "name":
            user.name = answer
        elif field == "accessibility":
            user.accessibility = _parse_accessibility(answer)
        update_user(user)

    elif entity == "business":
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
        writing_language=business.writing_language if business else "",
        writing_style=business.writing_style if business else "",
        communication_preferences=business.communication_preferences if business else "",
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
