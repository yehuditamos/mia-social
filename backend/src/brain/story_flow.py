from personality.loader import get_string
from src.specialists.memory.models import User, Business, ConversationState
from src.specialists.memory.engine import clear_conversation_flow

_EXIT_KEYWORDS = {"פוסט", "ריל", "תפריט", "חזרי", "חזור", "מניו", "menu", "post", "reel", "ביטול", "בטלי"}


def handle_story_flow(user: User, state: ConversationState, business: Business,
                      message: str, language: str) -> str:
    flow_step = (state.flow_data or {}).get("step", "awaiting_image")

    if flow_step == "awaiting_image":
        return _handle_image(user, message, language)

    clear_conversation_flow(user.id)
    return get_string("main_menu", language=language, name=user.name or "")


def _handle_image(user: User, message: str, language: str) -> str:
    words = set(message.strip().lower().split())
    if words & _EXIT_KEYWORDS:
        clear_conversation_flow(user.id)
        return get_string("main_menu", language=language, name=user.name or "")

    if message.startswith("__image__:"):
        clear_conversation_flow(user.id)
        return get_string("story_coming_soon", language=language)

    clear_conversation_flow(user.id)
    return get_string("story_need_image", language=language)
