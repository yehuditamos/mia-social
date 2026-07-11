import os
from src.specialists.memory.models import User
from src.specialists.memory.engine import (
    get_conversation_state,
    get_business,
    delete_conversation_state,
    delete_business,
    reset_user_profile,
)
from src.specialists.conversation.onboarding import STEPS, NUM_STEPS

_DEV_COMMANDS = {"/reset", "/debug", "/state", "/business"}


def is_dev_command(message: str) -> bool:
    if os.getenv("APP_ENV") != "development":
        return False
    return message.strip().lower() in _DEV_COMMANDS


def handle_dev_command(user: User, message: str) -> str:
    cmd = message.strip().lower()

    if cmd == "/reset":
        return _cmd_reset(user)
    if cmd == "/debug":
        return _cmd_debug(user)
    if cmd == "/state":
        return _cmd_state(user)
    if cmd == "/business":
        return _cmd_business(user)

    return "[dev] unknown command"


def _cmd_reset(user: User) -> str:
    delete_conversation_state(user.id)
    delete_business(user.id)
    reset_user_profile(user)
    return "[dev] reset complete — send any message to restart onboarding"


def _cmd_state(user: User) -> str:
    state = get_conversation_state(user.id)
    if state is None:
        return "[dev] state: None (no conversation state found)"
    completed = state.step >= NUM_STEPS
    step_name = STEPS[state.step]["key"] if not completed else "completed"
    return f"[dev] step: {state.step}/{NUM_STEPS} | name: {step_name} | completed: {completed}"


def _cmd_business(user: User) -> str:
    business = get_business(user.id)
    if business is None:
        return "[dev] no business profile found"
    return (
        f"[dev] business profile:\n"
        f"  id: {business.id}\n"
        f"  brand_name: {business.brand_name}\n"
        f"  what_you_do: {business.what_you_do}\n"
        f"  writing_language: {business.writing_language}\n"
        f"  writing_style: {business.writing_style}\n"
        f"  communication_preferences: {business.communication_preferences}"
    )


def _cmd_debug(user: User) -> str:
    state_info = _cmd_state(user)
    business_info = _cmd_business(user)
    return (
        f"[dev] user:\n"
        f"  id: {user.id}\n"
        f"  phone: {user.phone_number}\n"
        f"  name: {user.name}\n"
        f"  accessibility: {user.accessibility}\n\n"
        f"{state_info}\n\n"
        f"{business_info}"
    )
