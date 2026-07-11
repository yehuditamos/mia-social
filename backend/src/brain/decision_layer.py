from src.specialists.memory.engine import (
    get_user,
    save_user,
    get_conversation_state,
    create_conversation_state,
)
from src.specialists.memory.models import User
from src.specialists.conversation.onboarding import NUM_STEPS
from src.brain.router import route
from src.brain.main_menu import handle_post_onboarding
from src.brain.dev_commands import is_dev_command, handle_dev_command

DEFAULT_LANGUAGE = "he"


def process_message(phone_number: str, message: str) -> str:
    user = get_user(phone_number)

    if user is None:
        user = save_user(User(phone_number=phone_number))
        create_conversation_state(user.id)
        return route(user, None, message, DEFAULT_LANGUAGE)

    if is_dev_command(message):
        return handle_dev_command(user, message)

    state = get_conversation_state(user.id)

    if state is None:
        create_conversation_state(user.id)
        return route(user, None, message, DEFAULT_LANGUAGE)

    if state.step >= NUM_STEPS:
        return handle_post_onboarding(user, message, DEFAULT_LANGUAGE)

    return route(user, state, message, DEFAULT_LANGUAGE)
