"""
Central workflow intelligence: intent classification and task context for all flows.
Every flow handler imports from here instead of duplicating keyword logic.
"""

# ─── Intent keyword sets ───────────────────────────────────────────────────────

_CANCEL = {"ביטול", "בטל", "בטלי", "❌", "cancel", "עצרי", "הפסיקי", "לא רוצה"}
_BACK   = {"חזרה", "חזרי", "אחורה", "קודם", "שלב קודם", "חזור"}
_REGEN  = {"שוב", "אחרות", "חדשות", "חדש", "נסי", "נסה", "הצגי שוב", "אחרת",
            "הצעות חדשות", "נסי שוב"}
_EDIT   = {"תתקני", "תקני", "ערכי", "שפרי", "לתקן", "לערוך", "✏️", "לשנות"}
_APPROVE = {"כן", "בסדר", "אישור", "אשרי", "תמשיכי", "המשיכי", "טוב", "✅", "מאשרת"}
_SELF   = {"לבד", "בעצמי", "בעצמה"}

_SELF_PHRASES = ("תני לי לכתוב", "אכתוב לבד", "אני אכתוב", "אכתוב בעצמי")
_REGEN_PHRASES = ("הצגי שוב", "נסי שוב", "כותרות חדשות", "הצעות חדשות")

# Single Hebrew words that are clearly verb-imperatives (fem. form)
# Used to detect "תתקני", "תשני", "הצגי" etc. as commands, not content
_HEB_IMPERATIVE_PREFIXES = "תה"

# Known pure command single-words (beyond the sets above)
_EXTRA_COMMANDS = {
    "הצגי", "תשני", "תשנה", "תנסי", "תחזרי", "תמשיכי",
    "שנה", "נסה", "המשך", "בטוח", "לא", "כן",
}


def classify_intent(msg: str, step: str) -> str:
    """
    Classify user's message in the context of the current flow step.

    Returns one of:
      'cancel'     – user wants to abort the task
      'back'       – user wants to go to previous step
      'regenerate' – user wants new suggestions (hooks / CTAs)
      'edit'       – user wants to edit/fix something
      'approve'    – user confirms / accepts
      'self_write' – user wants to write themselves
      'input'      – user is providing actual content for this step
    """
    m = msg.strip()
    ml = m.lower()
    words = set(ml.split())

    if ml in _CANCEL or words & _CANCEL:
        return "cancel"

    if ml in _BACK or words & _BACK:
        return "back"

    if step in ("awaiting_hook", "awaiting_cta"):
        if ml in _REGEN or words & _REGEN or any(p in ml for p in _REGEN_PHRASES):
            return "regenerate"

    if ml in _EDIT or "✏️" in m or any(p in ml for p in {"תתקני", "לתקן", "ערכי", "שפרי"}):
        return "edit"

    if ml in _APPROVE:
        return "approve"

    if ml in _SELF or any(p in ml for p in _SELF_PHRASES):
        return "self_write"

    return "input"


def is_pure_command(msg: str) -> bool:
    """
    True when the message is a short command/keyword that should NOT be used as
    content text (e.g. hook title or CTA).

    Heuristic:
    1. Exact match in any known command set.
    2. Single Hebrew word ≤ 8 chars that starts with an imperative prefix (ת/ה).
    """
    m = msg.strip()
    ml = m.lower()

    if len(m) > 30:
        return False

    all_known = _CANCEL | _BACK | _REGEN | _EDIT | _APPROVE | _SELF | _EXTRA_COMMANDS
    if ml in all_known:
        return True

    if any(p in ml for p in _REGEN_PHRASES | set(_SELF_PHRASES)):
        return True

    words = m.split()
    if len(words) == 1 and len(m) <= 8 and m and m[0] in _HEB_IMPERATIVE_PREFIXES:
        return True

    return False


def is_valid_hook(msg: str) -> bool:
    """True when msg could plausibly be a carousel hook (title) for the first slide."""
    m = msg.strip()
    return (
        3 <= len(m) <= 70
        and "?" not in m
        and "\n" not in m
        and not is_pure_command(m)
    )


def is_valid_cta(msg: str) -> bool:
    """True when msg could plausibly be a CTA (last-slide call to action)."""
    m = msg.strip()
    return (
        3 <= len(m) <= 80
        and "\n\n" not in m
        and not is_pure_command(m)
    )


def step_label(flow: str, step: str) -> str:
    """Returns a one-line task status summary: '📋 קרוסלה | 📍 בחירת כותרת'"""
    _FLOWS = {
        "carousel_creation": "קרוסלה",
        "post_creation":     "פוסט טקסט",
        "image_post":        "פוסט עם תמונה",
        "story_creation":    "סטורי",
        "reel_creation":     "ריל",
    }
    _STEPS = {
        "awaiting_mode":               "בחירת מצב כתיבה",
        "awaiting_topic":              "נושא הפוסט",
        "awaiting_own_text":           "הטקסט שלך",
        "awaiting_proofread_approval": "אישור הגהה",
        "awaiting_hook":               "כותרת פתיחה",
        "awaiting_cta":                "הנעה לפעולה",
        "awaiting_color":              "צבע רקע",
        "awaiting_structure_approval": "אישור מבנה",
        "awaiting_slide_edit":         "עריכת דף",
        "awaiting_approval":           "אישור לפרסום",
        "awaiting_edit":               "עריכת טקסט",
        "awaiting_goal":               "מטרת הפוסט",
    }
    flow_name = _FLOWS.get(flow, flow)
    step_name = _STEPS.get(step, step)
    return f"📋 {flow_name}  |  📍 {step_name}"


def active_task_reminder(flow: str, step: str) -> str:
    """One-line reminder shown when user sends off-topic message in an active flow."""
    _STEP_PROMPTS = {
        "awaiting_mode":               "1️⃣ כתבי עבורי  |  2️⃣ אני אכתוב לבד",
        "awaiting_topic":              "מה הנושא לפוסט?",
        "awaiting_own_text":           "כתבי את הטקסט שלך:",
        "awaiting_proofread_approval": "✅ אשרי  |  🔄 מקורי  |  ✏️ ערכי",
        "awaiting_hook":               "בחרי מספר או כתבי כותרת משלך:",
        "awaiting_cta":                "בחרי מספר או כתבי הנעה לפעולה משלך:",
        "awaiting_color":              "שחור ⬛ או לבן ⬜?",
        "awaiting_structure_approval": "✅ לפרסם  |  ✏️ ערכי דף [מספר]  |  💾 טיוטה",
        "awaiting_slide_edit":         "כתבי את הטקסט החדש לדף:",
        "awaiting_approval":           "✅ לפרסם  |  ✏️ ערכי  |  ביטול",
        "awaiting_edit":               "כתבי את הטקסט המעודכן:",
    }
    label = step_label(flow, step)
    prompt = _STEP_PROMPTS.get(step, "נמשיך?")
    return f"{label}\n\n{prompt}"
