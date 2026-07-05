from personality.loader import get_string
from src.specialists.memory.engine import (
    get_user,
    save_user,
    get_conversation_state,
    create_conversation_state,
)
from src.specialists.memory.models import User
from src.specialists.conversation.onboarding import NUM_STEPS
from src.brain.router import route

DEFAULT_LANGUAGE = "he"


def process_message(phone_number: str, message: str) -> str:
    user = get_user(phone_number)

    if user is None:
        user = save_user(User(phone_number=phone_number))
        create_conversation_state(user.id)
        return route(user, None, message, DEFAULT_LANGUAGE)

    state = get_conversation_state(user.id)

    if state is None:
        create_conversation_state(user.id)
        return route(user, None, message, DEFAULT_LANGUAGE)

    if state.step >= NUM_STEPS:
        return get_string("post_onboarding_reply", language=DEFAULT_LANGUAGE)

    return route(user, state, message, DEFAULT_LANGUAGE)
