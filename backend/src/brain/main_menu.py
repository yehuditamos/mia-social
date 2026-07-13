from personality.loader import get_string
from src.specialists.memory.models import User
from src.specialists.memory.engine import update_conversation_flow

_POST_KEYWORDS = {"פוסט", "post", "1", "1️⃣"}
_STORY_KEYWORDS = {"סטורי", "story", "סטוריז", "2", "2️⃣"}
_REEL_KEYWORDS = {"ריל", "reel", "reels", "3", "3️⃣"}
_ACCESSIBILITY_KEYWORDS = {"נגישות", "accessibility", "♿"}
_SETTINGS_KEYWORDS = {"הגדרות", "settings", "⚙️"}


def _detect_intent(message: str) -> str:
    words = set(message.strip().lower().split())
    if words & _POST_KEYWORDS:
        return "create_post"
    if words & _STORY_KEYWORDS:
        return "create_story"
    if words & _REEL_KEYWORDS:
        return "create_reel"
    if words & _ACCESSIBILITY_KEYWORDS:
        return "accessibility"
    if words & _SETTINGS_KEYWORDS:
        return "settings"
    return "menu"


def handle_post_onboarding(user: User, message: str, language: str = "he") -> str:
    intent = _detect_intent(message)

    if intent == "create_post":
        update_conversation_flow(user.id, "post_creation", {"step": "awaiting_topic"})
        return get_string("post_ask_topic", language=language)
    if intent == "create_story":
        update_conversation_flow(user.id, "story_creation", {"step": "awaiting_image"})
        return get_string("menu_create_story", language=language)
    if intent == "create_reel":
        update_conversation_flow(user.id, "reel_creation", {"step": "awaiting_video"})
        return get_string("menu_create_reel", language=language)
    if intent == "accessibility":
        return get_string("menu_accessibility", language=language)
    if intent == "settings":
        return get_string("menu_settings", language=language)

    return get_string("main_menu", language=language, name=user.name or "")
