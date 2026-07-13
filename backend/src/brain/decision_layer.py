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
from src.brain.story_flow import handle_story_flow, start_story_flow
from src.brain.image_flow import handle_image_flow, start_image_flow
from src.brain.reel_flow import handle_reel_flow, start_reel_flow
from src.brain.dev_commands import is_dev_command, handle_dev_command
from src.db.repositories.social_account import SocialAccountRepository
from src.db.repositories.auth_session import AuthSessionRepository

DEFAULT_LANGUAGE = "he"
_BASE_URL = os.getenv("BASE_URL", "https://mia-social-backend.onrender.com")


def _make_connect_url(user, business) -> str:
    repo = AuthSessionRepository()
    state = repo.get_valid_pending(business.id, user.phone_number)
    if not state:
        state = repo.create(
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

    if message == "__audio__":
        return get_string("audio_not_supported", language=DEFAULT_LANGUAGE)

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

            # First time after connecting — set up monthly planning
            if business.planning_day is None and state.flow is None:
                from src.specialists.memory.engine import update_conversation_flow
                update_conversation_flow(user.id, "setup_planning_schedule", {})
                return (
                    f"🗓️ שאלה אחת לפני שמתחילות!\n\n"
                    f"מתי בחודש תרצי שמיה תיזום ישיבת תכנון תוכן חודשית?\n\n"
                    f"למשל: *25 בשעה 10* או *סוף החודש בשעה 9*"
                )

            if state.flow == "setup_planning_schedule":
                from src.brain.monthly_plan import handle_setup_planning
                return handle_setup_planning(user, business, message)

            if message.strip().startswith("ענה"):
                rest = message.strip()[3:].lstrip(" :,")
                if rest:
                    return _handle_ig_reply(user, rest)

            if message.startswith("__image__:"):
                image_id = message.split(":", 1)[1]
                if state.flow == "story_creation":
                    return start_story_flow(user, business, image_id, DEFAULT_LANGUAGE)
                if state.flow in ("accessibility_image_confirm", "accessibility_choose_type", "awaiting_image_type"):
                    pass  # handled in flow checks below
                elif user.accessibility and not state.flow:
                    return _describe_image_for_blind(user, business, image_id, DEFAULT_LANGUAGE)
                elif not state.flow:
                    from src.specialists.memory.engine import update_conversation_flow
                    update_conversation_flow(user.id, "awaiting_image_type", {"image_id": image_id})
                    return "קיבלתי 📸 מה תרצי לעשות?\n\n1️⃣ פוסט\n2️⃣ סטורי"
                else:
                    return start_image_flow(user, business, image_id, DEFAULT_LANGUAGE)

            if message.startswith("__video__:"):
                video_id = message.split(":", 1)[1]
                if state.flow == "story_creation":
                    return start_story_flow(user, business, video_id, DEFAULT_LANGUAGE)
                if state.flow == "reel_creation":
                    return start_reel_flow(user, business, video_id, DEFAULT_LANGUAGE)
                from src.specialists.memory.engine import update_conversation_flow
                update_conversation_flow(user.id, "awaiting_video_type", {"video_id": video_id})
                return "🎬 מה תרצי לעשות עם הסרטון?\n\n1️⃣ סטורי\n2️⃣ ריל"

            if state.flow == "awaiting_video_type":
                msg = message.strip()
                stored_video = (state.flow_data or {}).get("video_id", "")
                if msg in {"1", "סטורי", "story", "1️⃣"}:
                    from src.specialists.memory.engine import update_conversation_flow
                    update_conversation_flow(user.id, "story_creation", {"step": "awaiting_image"})
                    return start_story_flow(user, business, stored_video, DEFAULT_LANGUAGE)
                if msg in {"2", "ריל", "reel", "2️⃣"}:
                    from src.specialists.memory.engine import update_conversation_flow
                    update_conversation_flow(user.id, "reel_creation", {"step": "awaiting_video"})
                    return start_reel_flow(user, business, stored_video, DEFAULT_LANGUAGE)
                return "🎬 מה תרצי לעשות עם הסרטון?\n\n1️⃣ סטורי\n2️⃣ ריל"

            if state.flow == "awaiting_image_type":
                return _handle_image_type_choice(user, business, message, DEFAULT_LANGUAGE)

            if state.flow == "idea_capture":
                from src.brain.idea_bank import save_idea_from_description
                return save_idea_from_description(user, business, message)

            if state.flow == "accessibility_image_confirm":
                return _handle_accessibility_confirm(user, business, message, DEFAULT_LANGUAGE)
            if state.flow == "accessibility_choose_type":
                return _handle_accessibility_type_choice(user, business, message, DEFAULT_LANGUAGE)
            if state.flow == "post_creation":
                return handle_post_flow(user, state, business, message, DEFAULT_LANGUAGE)
            if state.flow == "story_creation":
                return handle_story_flow(user, state, business, message, DEFAULT_LANGUAGE)
            if state.flow == "reel_creation":
                return handle_reel_flow(user, state, business, message, DEFAULT_LANGUAGE)
            if state.flow == "image_post":
                return handle_image_flow(user, state, business, message, DEFAULT_LANGUAGE)
        return handle_post_onboarding(user, business, message, DEFAULT_LANGUAGE)

    return route(user, state, message, DEFAULT_LANGUAGE)


def _handle_image_type_choice(user, business, message: str, language: str) -> str:
    from src.specialists.memory.engine import get_conversation_state, clear_conversation_flow, update_conversation_flow

    state = get_conversation_state(user.id)
    image_id = (state.flow_data or {}).get("image_id", "") if state else ""
    msg = message.strip().lower()

    if msg in {"1", "פוסט", "post", "1️⃣"}:
        clear_conversation_flow(user.id)
        return start_image_flow(user, business, image_id, language)
    if msg in {"2", "סטורי", "story", "סטוריז", "2️⃣"}:
        update_conversation_flow(user.id, "story_creation", {"step": "awaiting_image"})
        return start_story_flow(user, business, image_id, language)

    return "מה תרצי לעשות עם התמונה?\n\n1️⃣ פוסט\n2️⃣ סטורי"


def _handle_accessibility_type_choice(user, business, message: str, language: str) -> str:
    from src.specialists.memory.engine import get_conversation_state, clear_conversation_flow, update_conversation_flow

    state = get_conversation_state(user.id)
    image_id = (state.flow_data or {}).get("image_id", "") if state else ""
    msg = message.strip().lower()

    if msg in {"1", "פוסט", "1️⃣"}:
        clear_conversation_flow(user.id)
        return start_image_flow(user, business, image_id, language)
    if msg in {"2", "סטורי", "story", "סטוריז", "2️⃣"}:
        update_conversation_flow(user.id, "story_creation", {"step": "awaiting_image"})
        return start_story_flow(user, business, image_id, language)

    return "מה תרצי לעשות עם התמונה?\n\n1️⃣ פוסט\n2️⃣ סטורי"


def _describe_image_for_blind(user, business, image_id: str, language: str) -> str:
    from src.whatsapp.media import download_media
    from src.brain.free_chat import describe_image_accessibility
    from src.specialists.memory.engine import update_conversation_flow

    try:
        media_b64, mime_type = download_media(image_id)
        description = describe_image_accessibility(media_b64, mime_type)
    except Exception as e:
        print(f"[ACCESSIBILITY] image describe error: {repr(e)}")
        return start_image_flow(user, business, image_id, language)

    update_conversation_flow(user.id, "accessibility_image_confirm", {"image_id": image_id})
    return f"🖼 מיה רואה:\n{description}\n\nהתמונה נכונה? (כן / לא)"


def _handle_accessibility_confirm(user, business, message: str, language: str) -> str:
    from src.specialists.memory.engine import get_conversation_state, clear_conversation_flow

    state = get_conversation_state(user.id)
    image_id = (state.flow_data or {}).get("image_id", "") if state else ""
    msg = message.strip().lower()

    _CONFIRM = {"כן", "yes", "✅", "אישור", "נכון", "בדיוק", "כן זה", "כן תמשיכי"}
    _CANCEL = {"לא", "no", "❌", "לא זה", "אחרת", "שגוי"}

    if msg in _CONFIRM or any(w in msg for w in {"כן", "yes", "נכון", "בדיוק"}):
        if image_id:
            from src.specialists.memory.engine import update_conversation_flow
            update_conversation_flow(user.id, "accessibility_choose_type", {"image_id": image_id})
            return "מה תרצי לעשות עם התמונה?\n\n1️⃣ פוסט\n2️⃣ סטורי"
        clear_conversation_flow(user.id)
        return "בסדר, שלחי את התמונה שוב 💜"

    clear_conversation_flow(user.id)
    return "בסדר 💜 שלחי תמונה אחרת."


def _handle_ig_reply(user, text: str) -> str:
    from src.db.repositories.pending_ig_reply import PendingIgReplyRepository
    from src.specialists.publishing.instagram import reply_to_ig_comment

    pending = PendingIgReplyRepository().get_and_clear(user.phone_number)
    if not pending:
        return (
            "לא נמצאה תגובה ממתינה 🙁\n"
            "ייתכן שעברה יותר משעה מאז ההתראה, או שעדיין לא הגיעה תגובה."
        )

    try:
        reply_to_ig_comment(pending["comment_id"], text, pending["access_token"])
        return "✅ המענה פורסם באינסטגרם!"
    except Exception as e:
        print(f"[IG REPLY ERROR] {repr(e)}")
        return "אופס, לא הצלחתי לפרסם את המענה. בדקי שהחשבון מחובר ונסי שוב."
