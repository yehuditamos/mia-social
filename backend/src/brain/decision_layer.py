import os
from personality.loader import get_string
from src.specialists.memory.engine import (
    get_user,
    save_user,
    get_business,
    get_conversation_state,
    create_conversation_state,
)
from src.specialists.memory.models import User
from src.specialists.conversation.onboarding import NUM_STEPS
from src.brain.router import route
from src.brain.main_menu import handle_post_onboarding
from src.brain.post_flow import handle_post_flow
from src.brain.story_flow import handle_story_flow
from src.brain.dev_commands import is_dev_command, handle_dev_command
from src.db.repositories.social_account import SocialAccountRepository
from src.db.repositories.auth_session import AuthSessionRepository

DEFAULT_LANGUAGE = "he"
_BASE_URL = os.getenv("BASE_URL", "https://mia-social-backend.onrender.com")


def _make_connect_url(user, business) -> str:
    state = AuthSessionRepository().create(
        business_id=business.id,
        channel="whatsapp",
        channel_user_id=user.phone_number,
        initiated_by=user.id,
        purpose="meta_connect",
    )
    return f"{_BASE_URL}/connect/{state}"


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
        business = get_business(user.id)
        print(f"POST_ONBOARDING: business={business}")
        if business:
            has_accounts = SocialAccountRepository().has_active_accounts(business.id)
            print(f"POST_ONBOARDING: has_active_accounts={has_accounts} flow={state.flow}")
            if not has_accounts:
                oauth_url = _make_connect_url(user, business)
                print(f"POST_ONBOARDING: sending connect URL={oauth_url}")
                return get_string("connect_accounts_prompt", language=DEFAULT_LANGUAGE, oauth_url=oauth_url)
            if state.flow == "post_creation":
                return handle_post_flow(user, state, business, message, DEFAULT_LANGUAGE)
            if state.flow == "story_creation":
                return handle_story_flow(user, state, business, message, DEFAULT_LANGUAGE)
        return handle_post_onboarding(user, message, DEFAULT_LANGUAGE)

    return route(user, state, message, DEFAULT_LANGUAGE)
