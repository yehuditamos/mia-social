from src.brain.workflow_engine import NOTEBOOK_RESET
from src.db.repositories.social_account import SocialAccountRepository
from src.specialists.memory.engine import (
    clear_conversation_flow,
    get_business,
    update_conversation_flow,
)
from src.specialists.memory.models import Business, ConversationState, User


_APPROVE = {"כן", "מאשרת", "מאשר", "אישור", "פרסמי", "תעלי", "✅", "yes"}
_CANCEL = {"לא", "ביטול", "בטל", "בטלי", "❌", "cancel"}
_EDIT_WORDS = {
    "ערכי", "ערוך", "עריכה", "ערוכה", "תערכי", "תערוך",
    "עיצוב", "תעצבי", "תעצב", "עצב", "מעוצבת", "שפרי", "תשפרי", "יפה",
    "תכיני סטורי", "תעשי סטורי", "סטורי",
}

_DELEGATION_PHRASES = {
    "סומכת עלייך", "סומך עלייך", "מה שנראה לך", "תחליטי את",
    "תבחרי את", "תעשי מה שאת רוצה", "תגדילי ראש",
}


def is_image_edit_request(message: str) -> bool:
    normalized = message.strip().lower()
    return any(word in normalized for word in _EDIT_WORDS)


def is_delegation_request(message: str) -> bool:
    normalized = message.strip().lower()
    return any(phrase in normalized for phrase in _DELEGATION_PHRASES)


def business_creative_context(business: Business) -> str:
    return "\n".join([
        f"Brand: {getattr(business, 'brand_name', '') or 'the business'}",
        f"Business: {getattr(business, 'what_you_do', '') or 'not specified'}",
        f"Writing style: {getattr(business, 'writing_style', '') or 'warm, direct and professional'}",
        f"Business goals: {getattr(business, 'goals', '') or 'build trust and drive action'}",
    ])


def start_image_edit_flow(
    user: User,
    business: Business,
    image_id: str,
    instruction: str,
) -> str:
    from src.specialists.media.gpt_image_editor import edit_for_story
    from src.whatsapp.media import download_media

    try:
        image_b64, mime_type = download_media(image_id)
        edited_url = edit_for_story(
            image_b64,
            mime_type,
            instruction,
            business_creative_context(business),
        )
    except Exception as exc:
        print(f"[IMAGE EDIT FLOW] generation failed: {repr(exc)}")
        clear_conversation_flow(user.id)
        return "לא הצלחתי לערוך את התמונה כרגע. היא לא פורסמה. שלחי אותה שוב וננסה מחדש."

    update_conversation_flow(user.id, "image_edit", {
        "step": "awaiting_approval",
        "edited_url": edited_url,
        "instruction": instruction.strip(),
    })
    return (
        f"__send_image__:{edited_url}\n||||\n"
        "ערכתי את התמונה והכנתי אותה לסטורי 👆\n\n"
        "כתבי *מאשרת* כדי שאעלה אותה, או *ביטול*."
    )


def handle_image_edit_flow(
    user: User,
    state: ConversationState,
    business: Business,
    message: str,
) -> str:
    data = state.flow_data or {}
    if data.get("step") != "awaiting_approval":
        clear_conversation_flow(user.id)
        return "העריכה התאפסה. שלחי את התמונה מחדש."

    normalized = message.strip().lower()
    if normalized in _CANCEL:
        clear_conversation_flow(user.id)
        return "בסדר, ביטלתי. התמונה לא פורסמה." + NOTEBOOK_RESET
    if normalized in _APPROVE:
        return _publish_edited_story(user, data)

    return "כתבי *מאשרת* כדי לפרסם את התמונה הערוכה, או *ביטול*."


def _publish_edited_story(user: User, flow_data: dict) -> str:
    from src.specialists.publishing.instagram import publish_story_to_instagram

    edited_url = flow_data.get("edited_url")
    business = get_business(user.id)
    if not edited_url or not business:
        clear_conversation_flow(user.id)
        return "התמונה הערוכה לא זמינה. היא לא פורסמה. שלחי אותה מחדש."

    accounts = SocialAccountRepository().get_by_business(business.id)
    instagram = next((a for a in accounts if a.get("platform") == "instagram"), None)
    if not instagram:
        clear_conversation_flow(user.id)
        return "חשבון האינסטגרם לא מחובר. התמונה לא פורסמה."

    try:
        publish_story_to_instagram(
            instagram.get("platform_account_id"),
            edited_url,
            instagram.get("access_token"),
            media_kind="image",
        )
    except Exception as exc:
        print(f"[IMAGE EDIT FLOW] publish failed: {repr(exc)}")
        return "לא הצלחתי לפרסם כרגע. התמונה הערוכה נשמרה. כתבי *מאשרת* כדי לנסות שוב."

    clear_conversation_flow(user.id)
    return "✅ התמונה הערוכה פורסמה בסטורי!" + NOTEBOOK_RESET
