from typing import Optional
from src.specialists.memory.models import User, ConversationState
from src.specialists.conversation.engine import handle_new_user, handle_onboarding


def route(user: User, state: Optional[ConversationState], message: str, language: str = "he") -> str:
    if state is None:
        return handle_new_user(user, language)
    return handle_onboarding(user, state, message, language)
