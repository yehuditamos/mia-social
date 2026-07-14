"""
Carousel creation flow.

Design principle: Default To Execution.
  - Receive text/topic → do ALL processing in one shot → present full structure
  - Color choice = publish approval (no separate step)
  - Maximum 2 user messages from start to seeing the full carousel

Steps (3 total):
  awaiting_content  → user sends text or topic
  awaiting_approval → full structure shown; color pick = publish
  awaiting_slide_edit → user edits one slide → back to awaiting_approval

Public entry points:
  start_carousel_flow(user, business, original_message) — called from main_menu
  handle_carousel_flow(user, state, business, message, language) — called from decision_layer
"""

import json
import os
import re
import requests
from src.specialists.memory.models import User, Business
from src.specialists.memory.engine import update_conversation_flow, clear_conversation_flow
from src.brain.workflow_engine import (
    classify_intent, is_pure_command, is_valid_hook, is_valid_cta,
    active_task_reminder, looks_like_topic, detect_color_preference,
    NOTEBOOK_RESET,
)

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL   = "claude-haiku-4-5-20251001"

# ─── Public entry points ───────────────────────────────────────────────────────

def start_carousel_flow(user, business, original_message: str) -> str:
    """
    Called from main_menu when the user requests a carousel.

    Opens the notebook page for this carousel.
    First question: idea or professional advice?
    If inline topic/text already in the message → process immediately (skip question).
    """
    # Check if there's already an inline topic in the original request
    topic = _extract_topic_from_request(original_message)
    if topic and len(topic) >= 3:
        update_conversation_flow(user.id, "carousel_creation", {
            "step": "awaiting_idea_status",
            "inline_topic": topic,
        })
        return _process_content(user, {"inline_topic": topic}, business, topic)

    update_conversation_flow(user.id, "carousel_creation", {
        "step": "awaiting_idea_status",
        "inline_topic": "",
    })
    return "כבר חשבת על רעיון, או שאת צריכה ייעוץ ממני? 💡"


def handle_carousel_flow(user, state, business, message: str, language: str = "he") -> str:
    msg  = message.strip()
    data = state.flow_data or {}
    step = data.get("step", "awaiting_content")

    # Global cancel
    if classify_intent(msg, step) == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    # Active steps
    if step == "awaiting_idea_status":
        return _handle_idea_status(user, data, business, msg)
    if step == "awaiting_idea_pick":
        return _handle_idea_pick(user, data, business, msg)
    if step == "awaiting_content":
        return _handle_content(user, data, business, msg)
    if step == "awaiting_approval":
        return _handle_approval(user, data, business, msg)
    if step == "awaiting_slide_edit":
        return _handle_slide_edit(user, data, msg)

    # ── Backward-compatibility: old step names ─────────────────────────────────
    # Users in the middle of the old 8-step flow get gracefully redirected.
    _OLD_STEPS = {
        "awaiting_mode", "awaiting_topic", "awaiting_own_text",
        "awaiting_proofread_approval", "awaiting_hook", "awaiting_cta",
        "awaiting_color", "awaiting_hook_choice",
    }
    if step in _OLD_STEPS:
        slides = data.get("slides")
        if slides:
            # We already have a structure — jump to approval
            update_conversation_flow(user.id, "carousel_creation", {
                **data, "step": "awaiting_approval"
            })
            preview = _format_structure_preview(slides)
            return (
                f"ממשיכים! הנה המבנה ({len(slides)} דפים):\n\n{preview}\n\n"
                "⬛ פרסמי (רקע שחור)\n"
                "⬜ פרסמי עם רקע לבן\n"
                "✏️ ערכי דף [מספר]"
            )
        # No slides yet — treat current message as content
        update_conversation_flow(user.id, "carousel_creation", {"step": "awaiting_content"})
        if len(msg) >= 3 and not is_pure_command(msg):
            return _process_content(user, {}, business, msg)
        return (
            "שלחי את הטקסט לקרוסלה, או ספרי על הנושא ואני אכתוב."
        )

    clear_conversation_flow(user.id)
    return "נתחיל מחדש? כתבי *פוסט*."


# ─── Step handlers ─────────────────────────────────────────────────────────────

# Words/phrases that signal "I have an idea or text ready"
_HAS_IDEA_WORDS  = {"חשבתי", "יש", "כן", "רעיון", "yes", "ברור", "כבר", "כתבתי", "כתבנו", "כתוב", "טקסט", "תוכן"}
_NEEDS_ADVICE_WORDS = {"ייעוץ", "עזרי", "עצה", "תמליצי", "no", "עזרה"}

# "כתבתי" / "יש לי" signal the user has their own text — ask them to send it
_SELF_WROTE_WORDS = {"כתבתי", "כתבנו", "כתוב", "שכתבתי"}
_SELF_TEXT_PHRASES = ("יש לי טקסט", "יש לי תוכן", "כתבתי טקסט", "כתבתי תוכן", "יש לי")


def _wants_to_send_own_text(msg: str) -> bool:
    """True when the user is saying 'I have/wrote my own text' rather than naming a topic."""
    ml = msg.lower().strip()
    words = set(ml.split())
    return (
        bool(words & _SELF_WROTE_WORDS)
        or any(p in ml for p in _SELF_TEXT_PHRASES)
        or classify_intent(msg, "awaiting_idea_status") == "self_write"
    )


def _handle_idea_status(user, data: dict, business, msg: str) -> str:
    """
    Step 1: does the user have an idea/text, or need Mia's advice?

    Detection order:
    1. Cancel → close notebook
    2. "Needs advice" signal → show 3 ideas
    3. "Has own text" signal ("כתבתי", "יש לי טקסט") → ask to send it
    4. "Has idea" signal → ask for text + design in one message
    5. Anything else → treat the message itself as content/topic directly
    """
    if classify_intent(msg, "awaiting_idea_status") == "cancel":
        clear_conversation_flow(user.id)
        return "בסדר, ביטלנו. המחברת נקייה." + NOTEBOOK_RESET

    ml = msg.lower().strip()
    words = set(ml.split())

    needs_advice = (
        words & _NEEDS_ADVICE_WORDS
        or any(p in ml for p in {"לא יודעת", "לא בטוחה", "תמליצי לי", "עזרי לי", "לא"})
    )

    if needs_advice:
        ideas = _generate_content_ideas(business)
        ideas_text = "\n".join(
            f"{['1️⃣','2️⃣','3️⃣'][i]} {idea}" for i, idea in enumerate(ideas[:3])
        )
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_idea_pick", "ideas": ideas,
        })
        return (
            f"הנה 3 רעיונות שיעבדו מצוין לעסק שלך:\n\n"
            f"{ideas_text}\n\n"
            "איזה מדבר אלייך? (1 / 2 / 3)\n"
            "או ספרי לי על רעיון אחר שיש לך."
        )

    # User has their own text → ask them to send it
    if _wants_to_send_own_text(msg):
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_content"})
        return (
            "מעולה! 📝\n\n"
            "שלחי לי בהודעה אחת:\n"
            "1. את הטקסט לקרוסלה\n"
            "2. איך תרצי שתיראה (לדוג׳ *רקע שחור* / *רקע לבן*)\n\n"
            "אם אין העדפת עיצוב — אעלה עם רקע שחור."
        )

    has_idea = bool(words & _HAS_IDEA_WORDS) or any(
        p in ml for p in {"חשבתי על", "יש לי רעיון", "יש רעיון", "כן יש"}
    )

    if has_idea:
        # Check if they also embedded the topic/text in the same message
        for strip_phrase in ["חשבתי על ", "יש לי רעיון על ", "רעיון: ", "הנה: ", "על "]:
            if strip_phrase in ml:
                remaining = msg[ml.index(strip_phrase) + len(strip_phrase):].strip()
                # Only use as inline topic if it's clearly a topic (short, not their text)
                if 3 <= len(remaining) <= 60 and not _wants_to_send_own_text(remaining):
                    update_conversation_flow(user.id, "carousel_creation", {
                        **data, "step": "awaiting_content"
                    })
                    return _process_content(user, data, business, remaining)

        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_content"})
        return (
            "מעולה! 📝\n\n"
            "שלחי לי בהודעה אחת:\n"
            "1. את הטקסט לקרוסלה\n"
            "2. איך תרצי שתיראה (לדוג׳ *רקע שחור* / *רקע לבן*)\n\n"
            "אם אין העדפת עיצוב — אעלה עם רקע שחור."
        )

    # No clear signal → treat the message as content/topic directly
    update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_content"})
    return _process_content(user, data, business, msg)


def _handle_idea_pick(user, data: dict, business, msg: str) -> str:
    """
    User responds to the 3-ideas list.
    Expected: 1/2/3 pick, a custom topic description, or "I have my own text".
    """
    if classify_intent(msg, "awaiting_idea_pick") == "cancel":
        clear_conversation_flow(user.id)
        return "בסדר, ביטלנו." + NOTEBOOK_RESET

    # "I have my own text" → ask them to send it
    if _wants_to_send_own_text(msg):
        update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_content"})
        return (
            "מעולה! 📝\n\n"
            "שלחי לי בהודעה אחת:\n"
            "1. את הטקסט לקרוסלה\n"
            "2. סגנון עיצוב (לדוג׳ *רקע שחור* / *רקע לבן*)\n\n"
            "אם אין העדפה — אעלה עם רקע שחור."
        )

    ideas = data.get("ideas", [])
    _NUM = {"1": 0, "2": 1, "3": 2, "1️⃣": 0, "2️⃣": 1, "3️⃣": 2}
    picked_idx = _NUM.get(msg.strip())

    if picked_idx is not None and picked_idx < len(ideas):
        topic = ideas[picked_idx]
    else:
        # Custom topic described by user
        topic = msg

    # Process immediately — no extra design question; default = black
    update_conversation_flow(user.id, "carousel_creation", {**data, "step": "awaiting_content"})
    return _process_content(user, data, business, topic)


def _generate_content_ideas(business, topic_hint: str = "") -> list:
    """Generate 3 carousel content ideas tailored to the business using Claude."""
    brand   = _bval(business, "brand_name",  "העסק")
    what_do = _bval(business, "what_you_do", "")

    system = (
        f"את מנהלת סושיאל לעסק {brand} ({what_do}).\n"
        "הצעי 3 רעיונות לקרוסלה בעלת ערך שתמשוך קהל ורלוונטית לעסק.\n"
        "כל רעיון: שורה אחת, עד 8 מילים, ללא מספור."
    )
    hint = f" בנושא {topic_hint}" if topic_hint else ""
    raw  = _call_claude(system, f"תני לי 3 רעיונות לקרוסלה{hint}.", max_tokens=130)
    lines = [l.strip().lstrip("123456789.•-) ") for l in raw.split("\n") if l.strip()]
    ideas = [l for l in lines if l][:3]

    # Fallback if Claude is unavailable
    if not ideas:
        ideas = [
            f"3 טיפים מקצועיים מ{brand}",
            "מאחורי הקלעים של העסק שלנו",
            "שאלות שלקוחות שואלים אותנו הכי הרבה",
        ]
    return ideas


def _handle_content(user, data: dict, business, msg: str) -> str:
    intent = classify_intent(msg, "awaiting_content")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    stored_topic = data.get("topic", "")
    color_in_msg  = detect_color_preference(msg)

    # Platform clarification ("לאינסטגרם", "אינסטגרם") — the carousel is always for Instagram.
    # Don't treat this as content; if we have a stored topic, proceed with it.
    _PLATFORM_WORDS = {"אינסטגרם", "instagram", "ig", "לאינסטגרם", "לאינסטגראם"}
    if set(msg.lower().split()) <= _PLATFORM_WORDS | {"אבל", "אני", "רוצה", "ל", "על", "ה"}:
        # Message is only platform words + filler — not actual content
        if stored_topic:
            return _process_content(user, data, business, stored_topic)
        update_conversation_flow(user.id, "carousel_creation", {**data})
        return (
            "הקרוסלה תועלה לאינסטגרם 📸\n\n"
            "שלחי לי את הטקסט לקרוסלה:"
        )

    # If we have a stored topic and user approves or gives only color
    if stored_topic:
        if intent == "approve" or msg.strip().lower() in {"כן", "בסדר", "ok", "אוקי", "המשיכי"}:
            return _process_content(user, data, business, stored_topic)
        if color_in_msg and len(msg.split()) <= 3:
            updated = {**data, "color_pref": color_in_msg}
            update_conversation_flow(user.id, "carousel_creation", updated)
            return _process_content(user, updated, business, stored_topic)

    if len(msg) < 3:
        return (
            "שלחי לי את הטקסט לקרוסלה ואת הסגנון הרצוי.\n\n"
            "לדוג׳: *רקע שחור* / *רקע לבן* — אם אין העדפה אעלה עם רקע שחור."
        )

    # Color-only message (no content) — store preference, ask for text
    if color_in_msg and len(msg.split()) <= 3 and not stored_topic:
        color_word = "לבן" if color_in_msg == "white" else "שחור"
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "color_pref": color_in_msg
        })
        return f"שמרתי: רקע {color_word}.\n\nשלחי את הטקסט לקרוסלה:"

    return _process_content(user, data, business, msg)


def _process_content(user, data: dict, business, msg: str) -> str:
    """
    Core engine: receives text or topic, does ALL carousel work in one shot.

    Execution Point logic (pre-response checklist):
    1. Is this a topic phrase or actual content text?
    2. Generate slides + hook + CTA via single Claude call
    3. If Claude fails for a topic → ask for actual text (don't loop)
    4. If Claude fails for text → use mechanical split (never fail)
    5. If color was stated anywhere → auto-publish, skip approval step
    """
    brand   = _bval(business, "brand_name",    "העסק")
    what_do = _bval(business, "what_you_do",   "")
    style   = _bval(business, "writing_style", "חמים ואישי")

    is_topic    = looks_like_topic(msg)
    color_in_msg = detect_color_preference(msg)

    # Inherit color stored from a previous message in this session
    color_pref = color_in_msg or data.get("color_pref")

    # Single Claude call: slides + hooks + CTAs
    structure = _generate_all(msg, is_topic, brand, what_do, style)

    if not structure and is_topic:
        # Topic + Claude unavailable → we cannot write the content; ask for text.
        # Do NOT reset to awaiting_content in a loop — give a clear, one-time message.
        update_conversation_flow(user.id, "carousel_creation", {
            **data,
            "step":       "awaiting_content",
            "color_pref": color_pref,
        })
        return (
            "לא הצלחתי לכתוב תוכן עכשיו.\n\n"
            "שלחי את הטקסט המלא ואני אחלק לדפים."
        )

    # If Claude failed for text input → mechanical split (never returns empty for text)
    if not structure:
        structure = _mechanical_structure(msg)

    body_slides = structure.get("body_slides", [])
    hooks       = structure.get("hooks", [])
    ctas        = structure.get("ctas", [])

    # Guarantee at least one slide — absolute floor
    if not body_slides:
        body_slides = [msg[:200]]

    hook = hooks[0] if hooks else body_slides[0][:40]
    cta  = ctas[0]  if ctas  else "שתפי עם מי שזה רלוונטי לה"

    # Deduplicate: Claude sometimes includes the hook text as the first body slide.
    # If that happens, remove the first body slide to avoid showing the same text twice.
    if body_slides and hook and body_slides[0].strip()[:40].lower() == hook.strip()[:40].lower():
        body_slides = body_slides[1:] if len(body_slides) > 1 else body_slides

    all_slides = [hook] + body_slides + [cta]

    update_conversation_flow(user.id, "carousel_creation", {
        "step":       "awaiting_approval",
        "slides":     all_slides,
        "body_text":  msg,
        "hooks":      hooks,
        "ctas":       ctas,
        "topic":      msg if is_topic else "",
        "color_pref": color_pref,
    })

    # Execution Point reached + color already known → publish immediately, no more questions
    if color_pref:
        return _publish(user, business, all_slides, color_pref)

    preview = _format_structure_preview(all_slides)
    return (
        f"הקרוסלה מוכנה ({len(all_slides)} דפים):\n\n"
        f"{preview}\n\n"
        "⬛ פרסמי (רקע שחור)\n"
        "⬜ פרסמי עם רקע לבן\n"
        "✏️ ערכי דף [מספר]\n"
        "💾 שמרי כטיוטה"
    )


def _handle_approval(user, data: dict, business, msg: str) -> str:
    """
    Execution Point: slides already exist in flow_data.
    Only valid actions here: publish (color), edit, draft.
    Never ask questions about content that was already provided.

    Color default: black — "כן"/"פרסמי" publishes with black without asking.
    """
    slides = data.get("slides", [])
    intent = classify_intent(msg, "awaiting_approval")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    # Guard: if state was somehow lost, don't loop
    if not slides:
        clear_conversation_flow(user.id)
        return "אירעה שגיאה — אנא שלחי *פוסט* להתחלה מחדש."

    # ── Color → publish ────────────────────────────────────────────────────────
    color = detect_color_preference(msg)
    if color:
        return _publish(user, business, slides, color)

    # ── "כן" / "פרסמי" / approve → publish with default black ─────────────────
    # This is the Execution Point: no more color question.
    # User can always specify "⬜ לבן" if they want white.
    _APPROVE_WORDS = {"כן", "אישור", "אשרי", "לפרסם", "פרסמי", "בסדר", "✅", "go", "ok"}
    stored_color = data.get("color_pref", "black")
    if intent == "approve" or msg.strip().lower() in _APPROVE_WORDS:
        return _publish(user, business, slides, stored_color)

    # ── Save as draft ──────────────────────────────────────────────────────────
    if "💾" in msg or "טיוטה" in msg:
        return _save_draft(user)

    # ── Edit specific slide by number ─────────────────────────────────────────
    match = re.search(r"(\d+)", msg)
    if match and any(w in msg for w in {"ערכי", "דף", "שנה", "ערוך", "תשני"}):
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(slides):
            update_conversation_flow(user.id, "carousel_creation", {
                **data, "step": "awaiting_slide_edit", "slide_edit_index": idx
            })
            return f"דף {idx + 1} כרגע:\n\n{slides[idx]}\n\nכתבי את הגרסה החדשה:"
        return f"לא נמצא דף {idx + 1} — יש {len(slides)} דפים בסך הכל."

    # ── Change hook (first slide) ──────────────────────────────────────────────
    if ("כותרת" in msg or "hook" in msg.lower() or "ראשון" in msg) and \
       any(w in msg for w in {"שני", "שנה", "ערכי", "אחרת", "חדשה"}):
        hooks = data.get("hooks", [])
        if len(hooks) > 1:
            choices = "\n".join(f"{['1️⃣','2️⃣','3️⃣'][i]} {h}" for i, h in enumerate(hooks[:3]))
            update_conversation_flow(user.id, "carousel_creation", {
                **data, "step": "awaiting_slide_edit", "slide_edit_index": 0
            })
            return f"בחרי כותרת לדף הראשון:\n\n{choices}\n\nאו כתבי כותרת משלך:"
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_slide_edit", "slide_edit_index": 0
        })
        return f"כותרת נוכחית:\n\n{slides[0]}\n\nכתבי כותרת חדשה:"

    # ── Change CTA (last slide) ────────────────────────────────────────────────
    if ("הנעה" in msg or "cta" in msg.lower() or "אחרון" in msg) and \
       any(w in msg for w in {"שני", "שנה", "ערכי", "אחרת", "חדשה"}):
        last_idx = len(slides) - 1
        ctas = data.get("ctas", [])
        if len(ctas) > 1:
            choices = "\n".join(f"{['1️⃣','2️⃣','3️⃣'][i]} {c}" for i, c in enumerate(ctas[:3]))
            update_conversation_flow(user.id, "carousel_creation", {
                **data, "step": "awaiting_slide_edit", "slide_edit_index": last_idx
            })
            return f"בחרי הנעה לפעולה לדף האחרון:\n\n{choices}\n\nאו כתבי משלך:"
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_slide_edit", "slide_edit_index": last_idx
        })
        return f"הנעה לפעולה נוכחית:\n\n{slides[last_idx]}\n\nכתבי הנעה חדשה:"

    # ── Off-topic / unclear → re-show structure (no new question) ─────────────
    preview = _format_structure_preview(slides)
    return (
        f"הקרוסלה מוכנה ({len(slides)} דפים):\n\n{preview}\n\n"
        "⬛ פרסמי (רקע שחור) | ⬜ רקע לבן | ✏️ ערכי דף [מספר] | 💾 טיוטה"
    )


def _handle_slide_edit(user, data: dict, msg: str) -> str:
    intent = classify_intent(msg, "awaiting_slide_edit")

    if intent == "cancel":
        clear_conversation_flow(user.id)
        return "הקרוסלה בוטלה."

    if intent == "back":
        slides  = data.get("slides", [])
        preview = _format_structure_preview(slides)
        update_conversation_flow(user.id, "carousel_creation", {
            **data, "step": "awaiting_approval"
        })
        return (
            f"חזרנו:\n\n{preview}\n\n"
            "⬛ שחור | ⬜ לבן | ✏️ ערכי דף [מספר] | 💾 טיוטה"
        )

    # Handle picking from a numbered list (when we showed hook/CTA alternatives)
    _NUM = {"1": 0, "2": 1, "3": 2, "1️⃣": 0, "2️⃣": 1, "3️⃣": 2}
    idx = data.get("slide_edit_index", 0)
    slides = list(data.get("slides", []))

    if not msg:
        return "כתבי את הטקסט החדש לדף:"

    # Numeric pick from alternatives
    num_pick = _NUM.get(msg.strip())
    if num_pick is not None and idx == 0:
        hooks = data.get("hooks", [])
        if num_pick < len(hooks):
            msg = hooks[num_pick]
    elif num_pick is not None and idx == len(slides) - 1:
        ctas = data.get("ctas", [])
        if num_pick < len(ctas):
            msg = ctas[num_pick]

    if 0 <= idx < len(slides):
        slides[idx] = msg

    update_conversation_flow(user.id, "carousel_creation", {
        **data, "step": "awaiting_approval", "slides": slides
    })
    preview = _format_structure_preview(slides)
    return (
        f"דף {idx + 1} עודכן.\n\n{preview}\n\n"
        "⬛ שחור | ⬜ לבן | ✏️ ערכי דף [מספר] | 💾 טיוטה"
    )


# ─── Publishing ────────────────────────────────────────────────────────────────

def _publish(user, business, slides: list, color: str) -> str:
    from src.db.repositories.social_account import SocialAccountRepository
    from src.specialists.publishing.instagram import publish_carousel_to_instagram
    from src.brain.carousel_image import generate_slide_and_upload

    clear_conversation_flow(user.id)

    if not business:
        return "לא נמצא עסק מחובר."

    ig_accounts = SocialAccountRepository().get_by_business(business.id, platform="instagram")
    if not ig_accounts:
        return "אין חשבון אינסטגרם מחובר — חברי חשבון ונסי שוב."

    ig           = ig_accounts[0]
    ig_user_id   = ig.get("platform_account_id")
    access_token = ig.get("access_token")

    if not ig_user_id or not access_token:
        return "נתוני החשבון חסרים — חברי מחדש."

    try:
        total      = len(slides)
        slide_urls = []
        for i, text in enumerate(slides):
            url = generate_slide_and_upload(text, color, slide_num=i + 1, total=total)
            slide_urls.append(url)
            print(f"[CAROUSEL] slide {i + 1}/{total} → {url}")

        caption  = slides[0] if slides else ""
        post_url = publish_carousel_to_instagram(ig_user_id, slide_urls, caption, access_token)
        icon     = "⬛" if color == "black" else "⬜"
        return f"✅ הקרוסלה פורסמה {icon}\n\n{post_url}" + NOTEBOOK_RESET
    except Exception as e:
        err = str(e)
        print(f"[CAROUSEL_FLOW] publish error: {repr(e)}")
        if "190" in err or "expired" in err.lower():
            return "פג תוקף החיבור לאינסטגרם — חברי מחדש."
        if "200" in err or "permission" in err.lower():
            return "חסרות הרשאות פרסום — בדקי שהחשבון מחובר כראוי."
        return f"לא הצלחתי לפרסם — נסי שוב.\n\n({err[:80]})"


def _save_draft(user) -> str:
    clear_conversation_flow(user.id)
    return "הקרוסלה נשמרה. כשתרצי לפרסם, כתבי *פוסט*."


# ─── Claude: single combined call ──────────────────────────────────────────────

def _generate_all(content: str, is_topic: bool, brand: str,
                  what_do: str, style: str) -> dict:
    """
    Single Claude call that returns slides, hook suggestions, and CTA suggestions.
    Falls back to individual calls if JSON parsing fails.

    Returns: {"body_slides": [...], "hooks": [...], "ctas": [...]}
    """
    if is_topic:
        input_desc = f"כתבי תוכן מקצועי על הנושא: {content}"
    else:
        # Proofread + use as base
        input_desc = f"בסס את הקרוסלה על הטקסט הזה:\n{content[:600]}"

    system = (
        f"מנהלת סושיאל לעסק {brand} ({what_do}). סגנון: {style}.\n\n"
        f"{input_desc}\n\n"
        "החזירי JSON בפורמט הזה בדיוק:\n"
        '{"slides":["תוכן דף פנימי 1","תוכן דף פנימי 2"],'
        '"hooks":["כותרת 1","כותרת 2","כותרת 3"],'
        '"ctas":["הנעה 1","הנעה 2","הנעה 3"]}\n\n'
        "כללים:\n"
        "- slides: 2-4 דפי גוף בלבד (לא כולל כותרת פתיחה ולא הנעה לפעולה!), כל דף עד 15 מילים\n"
        "- hooks: בדיוק 3 כותרות פתיחה, מושכות תשומת לב, עד 8 מילים\n"
        "- ctas: בדיוק 3 הנעות לפעולה, עד 8 מילים\n"
        "- JSON בלבד, ללא טקסט נוסף"
    )

    raw = _call_claude(system, ".", max_tokens=500)

    if raw:
        # Strip markdown code fences if Claude wrapped the JSON
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        match = re.search(r"\{[\s\S]+\}", raw)
        if match:
            try:
                parsed = json.loads(match.group())
                result = {
                    "body_slides": [s for s in parsed.get("slides", []) if s][:4],
                    "hooks":       [h for h in parsed.get("hooks",  []) if h][:3],
                    "ctas":        [c for c in parsed.get("ctas",   []) if c][:3],
                }
                if result["body_slides"]:
                    return result
            except Exception as e:
                print(f"[CAROUSEL] JSON parse error: {repr(e)} raw={raw[:200]}")

    # Fallback: individual Claude calls
    print("[CAROUSEL] falling back to individual Claude calls")
    if is_topic:
        body = _generate_body(content, brand, what_do, style)
        if not body:
            # Topic + Claude down → cannot generate content; caller handles this
            return None
    else:
        body = content

    slides = _split_body_into_slides(body)
    if not slides:
        # Even individual split failed → mechanical split on original text
        return _mechanical_structure(content) if not is_topic else None

    return {
        "body_slides": slides,
        "hooks":       _generate_hook_suggestions(content[:60], body, brand),
        "ctas":        _generate_cta_suggestions(brand, what_do),
    }


# ─── Mechanical fallback (no Claude required) ─────────────────────────────────

def _mechanical_structure(text: str) -> dict:
    """
    Build carousel structure from user text WITHOUT any Claude call.
    Used when Claude is completely unavailable but user provided actual content.
    Always returns a non-empty body_slides list.
    """
    # Try splitting by explicit line breaks first
    lines = [l.strip().lstrip("-•*0123456789. ") for l in text.split("\n") if len(l.strip()) > 4]

    if len(lines) >= 2:
        body_slides = lines[:4]
    else:
        # Single paragraph: split by sentence-ending punctuation
        raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        if len(sentences) <= 1:
            # One long sentence or very short text: use as one slide
            body_slides = [text[:200]]
        elif len(sentences) <= 4:
            body_slides = sentences
        else:
            # Group sentences into ~3 slides
            chunk = max(1, len(sentences) // 3)
            body_slides = []
            for i in range(0, len(sentences), chunk):
                body_slides.append(" ".join(sentences[i:i + chunk]))
            body_slides = body_slides[:4]

    hook_text = body_slides[0][:50] if body_slides else text[:50]
    return {
        "body_slides": body_slides,
        "hooks":       [hook_text],
        "ctas":        ["שתפי עם מי שצריכה לשמוע"],
    }


# ─── Individual Claude helpers (fallback) ──────────────────────────────────────

def _call_claude(system: str, user_msg: str, max_tokens: int = 300) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        res = requests.post(
            _API_URL,
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      _MODEL,
                "max_tokens": max_tokens,
                "system":     system,
                "messages":   [{"role": "user", "content": user_msg}],
            },
            timeout=25,
        )
        data = res.json()
        if res.status_code != 200 or "content" not in data:
            print(f"[CAROUSEL_FLOW] Claude error: {data}")
            return ""
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[CAROUSEL_FLOW] Claude request error: {repr(e)}")
        return ""


def _generate_body(topic: str, brand: str, what_do: str, style: str) -> str:
    system = (
        f"מנהלת סושיאל לעסק {brand} ({what_do}). סגנון: {style}.\n"
        "כתבי תוכן לקרוסלה: 3-4 נקודות, כל אחת עד 15 מילים, בלי כותרת ובלי הנעה לפעולה.\n"
        "כל נקודה בשורה נפרדת."
    )
    return _call_claude(system, f"נושא: {topic}", max_tokens=220)


def _generate_hook_suggestions(topic: str, body: str, brand: str) -> list:
    system = (
        "כתבי 3 כותרות פתיחה מושכות לקרוסלה (עד 8 מילים כל אחת). "
        "כל כותרת בשורה נפרדת, בלי מספור."
    )
    raw = _call_claude(system, f"נושא: {topic}\nתוכן: {body[:180]}", max_tokens=130)
    return _clean_list(raw)[:3]


def _generate_cta_suggestions(brand: str, what_do: str) -> list:
    system = (
        "כתבי 3 הנעות לפעולה קצרות לפוסט אינסטגרם (עד 8 מילים כל אחת). "
        "מגוון: שמרי, שתפי, כתבי תגובה, שלחי הודעה. "
        "כל הנעה בשורה נפרדת, בלי מספור."
    )
    raw = _call_claude(system, f"עסק: {brand} — {what_do}", max_tokens=100)
    return _clean_list(raw)[:3]


def _split_body_into_slides(body_text: str) -> list:
    if not body_text:
        return []
    lines = [l.strip().lstrip("-•*0123456789. ") for l in body_text.split("\n") if l.strip()]
    if len(lines) >= 2:
        return lines[:4]
    system = (
        "חלק את הטקסט ל-2-4 שקופיות לקרוסלה. "
        "כל שקופית עד 15 מילים, רעיון אחד. "
        "כל שקופית בשורה נפרדת, בלי מספור."
    )
    raw    = _call_claude(system, body_text, max_tokens=220)
    slides = _clean_list(raw)
    return slides[:4] if slides else [body_text]


# ─── Topic extraction ──────────────────────────────────────────────────────────

def _extract_topic_from_request(message: str) -> str:
    """
    Extract inline topic/content from a message like:
    'תעלי קרוסלה לאינסטגרם על טיפים לבריאות'
    → returns 'טיפים לבריאות'
    """
    msg = message.strip()

    # Patterns to strip (longest first to avoid partial matches)
    _TRIGGERS = [
        "תעלי קרוסלה לאינסטגרם", "תעלי פוסט לאינסטגרם",
        "צרי קרוסלה לאינסטגרם", "הכיני קרוסלה לאינסטגרם",
        "תעלי קרוסלה", "צרי קרוסלה", "הכיני קרוסלה",
        "תעלי פוסט", "צרי פוסט",
        "קרוסלה לאינסטגרם", "פוסט לאינסטגרם",
        "קרוסלה", "פוסט",
    ]
    ml = msg.lower()
    for trigger in _TRIGGERS:
        idx = ml.find(trigger.lower())
        if idx != -1:
            remaining = msg[idx + len(trigger):].strip()
            for prep in ["על ", "בנושא ", "לגבי ", "לנושא "]:
                if remaining.lower().startswith(prep):
                    remaining = remaining[len(prep):].strip()
            if len(remaining) >= 3 and not remaining.lower().startswith("?"):
                return remaining
    return ""


# ─── Display helpers ───────────────────────────────────────────────────────────

def _format_structure_preview(slides: list) -> str:
    total = len(slides)
    out   = []
    for i, text in enumerate(slides):
        if i == 0:
            label = "דף 1 — כותרת"
        elif i == total - 1:
            label = f"דף {total} — הנעה לפעולה"
        else:
            label = f"דף {i + 1}"
        preview = text if len(text) <= 55 else text[:52] + "..."
        out.append(f"📄 {label}:\n{preview}")
    return "\n\n".join(out)


def _clean_list(raw: str) -> list:
    lines = [l.strip().lstrip("-•*123456789️⃣. ") for l in raw.split("\n") if l.strip()]
    return [l for l in lines if l]


def _bval(business, field: str, default: str) -> str:
    if not business:
        return default
    return getattr(business, field, None) or default
