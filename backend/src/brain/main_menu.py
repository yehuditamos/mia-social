from typing import Optional
from personality.loader import get_string
from src.specialists.memory.models import User, Business
from src.specialists.memory.engine import update_conversation_flow, upsert_business_field

_POST_KEYWORDS = {"פוסט", "post", "1", "1️⃣"}
_STORY_KEYWORDS = {"סטורי", "story", "סטוריז", "2", "2️⃣"}
_REEL_KEYWORDS = {"ריל", "reel", "reels", "3", "3️⃣"}
_ACCESSIBILITY_KEYWORDS = {"נגישות", "accessibility", "♿"}
_SETTINGS_KEYWORDS = {"הגדרות", "settings", "⚙️"}

_GOAL_PHRASES = [
    "אני רוצה יותר", "המטרה שלי", "אני רוצה להגיע",
    "אני רוצה להביא", "אני רוצה לגדול", "יותר לקוחות",
    "יותר פניות", "יותר מכירות", "להגדיל את", "לצמוח",
    "המטרה שלנו", "אני רוצה שיהיו", "רוצה להביא",
]

_PLAN_PHRASES = [
    "שבוע תוכן", "תוכן לשבוע", "תכנון שבועי",
    "תכנית תוכן", "לבנות שבוע", "תכניית תוכן",
    "תכנן לי", "תכיני לי תוכן לשבוע", "תוכנית שבועית",
]

_MONTHLY_PLAN_PHRASES = [
    "תכנן חודש", "תכנני חודש", "גאנט", "חודש תוכן",
    "תוכן לחודש", "תכנון חודשי", "תוכנית חודשית",
]

_REMINDER_PHRASES = ["תזכירי לי", "תזכיר לי", "תשלחי לי תזכורת"]


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

    msg_lower = message.lower()
    if any(p in msg_lower for p in _REMINDER_PHRASES):
        return "reminder"
    if any(p in msg_lower for p in _MONTHLY_PLAN_PHRASES):
        return "monthly_plan"
    if any(p in msg_lower for p in _PLAN_PHRASES):
        return "weekly_plan"
    if any(p in msg_lower for p in _GOAL_PHRASES):
        return "save_goal"

    # Idea bank intents (checked last, before free chat)
    from src.brain.idea_bank import detect_idea_intent
    idea_intent, _ = detect_idea_intent(message)
    if idea_intent:
        return f"idea_{idea_intent}"

    return "free_chat"


def handle_post_onboarding(user: User, business: Optional[Business], message: str, language: str = "he") -> str:
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

    if intent == "reminder":
        from src.brain.reminder_handler import handle_reminder_request
        return handle_reminder_request(user, message)

    if not business:
        return get_string("main_menu", language=language, name=user.name or "")

    if intent == "monthly_plan":
        from src.brain.monthly_plan import generate_monthly_plan
        return generate_monthly_plan(user, business)

    if intent == "weekly_plan":
        from src.brain.free_chat import handle_weekly_plan
        return handle_weekly_plan(user, business)

    if intent == "save_goal":
        return _handle_save_goal(user, business, message)

    if intent == "idea_list_ideas":
        from src.brain.idea_bank import list_ideas
        return list_ideas(business)

    if intent == "idea_ask_for_idea":
        from src.brain.idea_bank import start_idea_capture
        return start_idea_capture(user)

    if intent == "idea_save_idea_now":
        from src.brain.idea_bank import detect_idea_intent, save_idea_from_description
        _, idea_text = detect_idea_intent(message)
        return save_idea_from_description(user, business, idea_text or message)

    if intent == "idea_use_idea":
        from src.brain.idea_bank import detect_idea_intent, use_idea
        _, n = detect_idea_intent(message)
        return use_idea(user, business, n or 1)

    from src.brain.free_chat import handle_free_chat
    return handle_free_chat(user, business, message)


def _handle_save_goal(user: User, business: Business, message: str) -> str:
    upsert_business_field(user.id, "goals", message.strip())
    business.goals = message.strip()
    from src.brain.free_chat import handle_free_chat
    advice = handle_free_chat(
        user, business,
        f"המשתמש הגדירה מטרה עסקית: '{message}'. תני לה טיפ תוכן אחד קצר שיעזור להשיג את המטרה הזו."
    )
    return f"💜 שמרתי את המטרה שלך!\n\n{advice}"
