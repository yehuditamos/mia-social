import os
import requests
from src.specialists.memory.models import User, Business
from src.db.repositories.content_idea import ContentIdeaRepository

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"

_IDEA_TRIGGERS = [
    "יש לי רעיון", "חשבתי על משהו", "רעיון מדהים", "רעיון נהדר",
    "רעיון מושלם", "תזכרי לי", "שמרי לי", "שמרי לי רעיון",
    "יש לי משהו", "חשבתי על רעיון",
]

_IDEA_BANK_TRIGGERS = [
    "בנק רעיונות", "פתחי בנק", "מה הרעיונות", "מה יש לנו", "הרעיונות שלי",
    "מה שמור", "מה שמרנו", "רעיונות שמורים",
]

_USE_IDEA_TRIGGERS = ["נעבד את", "נעשה פוסט מרעיון", "נעשה ריל מרעיון",
                      "נעשה סטורי מרעיון", "בואי נעבד", "עבדי על רעיון"]


def detect_idea_intent(message: str):
    """Returns ('save_idea_now', idea_text) | ('ask_for_idea', None) | ('list_ideas', None) | ('use_idea', N) | (None, None)"""
    msg_lower = message.lower().strip()

    # Check if user wants to list ideas
    if any(t in msg_lower for t in _IDEA_BANK_TRIGGERS):
        return "list_ideas", None

    # Check if user wants to use a specific idea
    if any(t in msg_lower for t in _USE_IDEA_TRIGGERS):
        import re
        match = re.search(r"(\d+)", message)
        n = int(match.group(1)) if match else 1
        return "use_idea", n

    # Check if user is describing an idea
    for trigger in _IDEA_TRIGGERS:
        if trigger in msg_lower:
            idx = msg_lower.index(trigger)
            rest = message[idx + len(trigger):].strip(" :!?...")
            if len(rest.split()) >= 4:
                return "save_idea_now", rest
            return "ask_for_idea", None

    return None, None


def start_idea_capture(user: User) -> str:
    from src.specialists.memory.engine import update_conversation_flow
    update_conversation_flow(user.id, "idea_capture", {})
    return "אני כל אוזן 👂 ספרי לי מה הרעיון!"


def save_idea_from_description(user: User, business: Business, idea_text: str) -> str:
    from src.specialists.memory.engine import clear_conversation_flow

    title, description = _generate_title_and_desc(idea_text)

    if business:
        ContentIdeaRepository().save(business.id, title, description)

    clear_conversation_flow(user.id)
    return f"💡 שמרתי בבנק הרעיונות!\n\n📌 {title}\n{description}\n\nנעבד אותו כשתרצי 💜"


def list_ideas(business: Business) -> str:
    if not business:
        return "לא נמצאו רעיונות שמורים."

    ideas = ContentIdeaRepository().get_unused(business.id)
    if not ideas:
        return "🗂️ בנק הרעיונות ריק כרגע.\n\nשלחי לי רעיון בכל עת ואשמור אותו!"

    lines = ["🗂️ *בנק הרעיונות שלנו*\n"]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"{i}. 📌 *{idea['title']}*\n   {idea['description']}")
    lines.append(f"\n{len(ideas)} רעיונות ממתינים 💜")
    lines.append("לעבוד על רעיון — כתבי: 'נעבד את רעיון 1'")
    return "\n".join(lines)


def use_idea(user: User, business: Business, index: int) -> str:
    """Starts a post creation flow with the idea as topic."""
    if not business:
        return "לא נמצאו רעיונות שמורים."

    idea = ContentIdeaRepository().get_by_index(business.id, index)
    if not idea:
        count = ContentIdeaRepository().count_unused(business.id)
        return f"לא נמצא רעיון מספר {index}. יש {count} רעיונות בבנק."

    # Start post creation flow with the idea as topic
    from src.specialists.memory.engine import update_conversation_flow
    from src.brain.post_flow import _generate_and_ask
    from src.specialists.memory.engine import get_conversation_state

    topic = f"{idea['title']} — {idea['description']}"
    state = get_conversation_state(user.id)

    try:
        ContentIdeaRepository().mark_used(idea["id"])
        result = _generate_and_ask(user, business, topic, "he")
        return f"📌 עובדים על: *{idea['title']}*\n\n{result}"
    except Exception as e:
        print(f"[IDEA USE] error: {repr(e)}")
        update_conversation_flow(user.id, "post_creation", {"step": "awaiting_topic", "topic_prefill": topic})
        return f"📌 בחרת: *{idea['title']}*\n{idea['description']}\n\nמאשרת לכתוב על זה?"


def _generate_title_and_desc(idea_text: str) -> tuple:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        words = idea_text.split()
        return " ".join(words[:4]), idea_text

    try:
        res = requests.post(
            _API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": _MODEL,
                "max_tokens": 80,
                "system": "מהרעיון הבא, צרי כותרת קצרה (3-5 מילים בעברית) ותיאור במשפט אחד קצר.\nענה רק בפורמט:\nTITLE: [כותרת]\nDESC: [תיאור]",
                "messages": [{"role": "user", "content": idea_text}],
            },
            timeout=15,
        )
        text = res.json()["content"][0]["text"].strip()
        lines = {}
        for line in text.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                lines[k.strip()] = v.strip()
        title = lines.get("TITLE") or " ".join(idea_text.split()[:4])
        desc = lines.get("DESC") or idea_text
        return title, desc
    except Exception as e:
        print(f"[IDEA BANK] title gen error: {repr(e)}")
        return " ".join(idea_text.split()[:4]), idea_text
