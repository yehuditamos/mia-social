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

# ─── "מה עושים עכשיו?" opener ──────────────────────────────────────────────────

_GREETING_WORDS = {
    "היי", "שלום", "בוקר", "ערב", "לילה", "מה נשמע", "מה קורה", "מה המצב",
    "hey", "hi", "hello", "shalom", "נשמע", "קורה", "המצב",
}

_TASK_WORDS = {
    "פוסט", "post", "קרוסלה", "carousel", "סטורי", "story", "סטוריז",
    "ריל", "reel", "תמונה", "סרטון", "תוכן", "content",
    "תכנון", "plan", "תכנית", "שבוע", "חודש", "רעיון", "idea",
    "אינסטגרם", "instagram", "ig", "אינסטגראם",
}


def _is_opener(msg: str) -> bool:
    """
    True when the message is a greeting or very short with no task keyword.
    These get "מה עושים עכשיו?" instead of free_chat.
    """
    ml = msg.lower().strip()
    words = ml.split()

    # If any task word present → has intent, NOT an opener
    if set(words) & _TASK_WORDS:
        return False

    # Exact match in greeting set
    if ml in _GREETING_WORDS:
        return True

    # Starts with a greeting word
    if words and words[0] in {"היי", "שלום", "בוקר", "ערב", "לילה", "hey", "hi", "hello"}:
        return True

    # Short (≤3 words) message with no task keyword and no question mark
    if len(words) <= 3 and "?" not in msg and "?" not in msg:
        return True

    return False


def _opener_message() -> str:
    return (
        "מה עושים עכשיו? 📋\n\n"
        "• פוסט / קרוסלה\n"
        "• סטורי\n"
        "• ריל\n"
        "• תכנון שבועי / חודשי\n\n"
        "כתבי מה על הפרק ואני כאן."
    )

_UPLOAD_VERBS = {"תעלי", "פרסמי", "העלי", "תפרסמי", "תעלה", "העלה", "שלחי ל"}

_TEXT_STORY_TRIGGERS = ["של טקסט", "רק טקסט", "טקסט בלבד", "טקסט:", "text:", "רק קישור", "כיתוב בלבד"]


def _detect_intent(message: str) -> str:
    msg_lower = message.lower().strip()
    words = set(msg_lower.split())

    # Explicit text story prefix
    if msg_lower.startswith("טקסט:") or msg_lower.startswith("text:"):
        return "text_story"

    # Natural upload commands — "תעלי סטורי", "פרסמי ריל", etc.
    if any(v in msg_lower for v in _UPLOAD_VERBS):
        if any(w in msg_lower for w in {"סטורי", "story", "סטוריז"}):
            if any(t in msg_lower for t in _TEXT_STORY_TRIGGERS):
                return "text_story"
            return "create_story"
        if any(w in msg_lower for w in {"ריל", "reel", "reels"}):
            return "create_reel"
        if any(w in msg_lower for w in {"פוסט", "post"}):
            return "create_post"

    if words & _POST_KEYWORDS:
        return "create_post"
    if words & _STORY_KEYWORDS:
        if any(t in msg_lower for t in _TEXT_STORY_TRIGGERS):
            return "text_story"
        return "create_story"
    if words & _REEL_KEYWORDS:
        return "create_reel"
    if words & _ACCESSIBILITY_KEYWORDS:
        return "accessibility"
    if words & _SETTINGS_KEYWORDS:
        return "settings"

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
    # Greetings and idle openers → home screen ("מה עושים עכשיו?")
    if _is_opener(message):
        return _opener_message()

    intent = _detect_intent(message)

    if intent == "create_post":
        from src.brain.carousel_flow import start_carousel_flow
        return start_carousel_flow(user, business, message)
    if intent == "text_story":
        return _handle_text_story_start(user, message, language)
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


def _handle_text_story_start(user: User, message: str, language: str) -> str:
    text = _extract_story_text(message)
    if text:
        update_conversation_flow(user.id, "text_story_creation", {"step": "awaiting_color", "text": text})
        return f"שמרתי: \"{text}\"\n\nאיזה רקע?\n\n⬛ שחור\n⬜ לבן"
    update_conversation_flow(user.id, "text_story_creation", {"step": "awaiting_text"})
    return "מה הטקסט לסטורי? ✍️\n\n(מיה תיצור תמונה עם הטקסט שלך)"


def _extract_story_text(message: str) -> str:
    msg = message.strip()
    for marker in ["של טקסט", "טקסט:", "text:", "רק טקסט", "כיתוב:"]:
        idx = msg.lower().find(marker.lower())
        if idx != -1:
            after = msg[idx + len(marker):].strip()
            if len(after) > 1:
                return after
    # "תעלי סטורי מחר נפגשות" — content after "סטורי"
    for kw in ["סטוריז", "סטורי", "story"]:
        idx = msg.lower().find(kw)
        if idx != -1:
            after = msg[idx + len(kw):].strip()
            # Only use if it's actual content (not a trigger keyword)
            if len(after) > 3 and not any(v in after.lower() for v in {"טקסט", "text"}):
                return after
    return ""


def _handle_save_goal(user: User, business: Business, message: str) -> str:
    upsert_business_field(user.id, "goals", message.strip())
    business.goals = message.strip()
    from src.brain.free_chat import handle_free_chat
    advice = handle_free_chat(
        user, business,
        f"המשתמש הגדירה מטרה עסקית: '{message}'. תני לה טיפ תוכן אחד קצר שיעזור להשיג את המטרה הזו."
    )
    return f"💜 שמרתי את המטרה שלך!\n\n{advice}"
