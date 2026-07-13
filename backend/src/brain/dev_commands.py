import os
from src.specialists.memory.models import User
from src.specialists.memory.engine import (
    get_conversation_state,
    get_business,
    delete_conversation_state,
    delete_business,
    reset_user_profile,
)
from src.db.repositories.social_account import SocialAccountRepository
from src.specialists.conversation.onboarding import STEPS, NUM_STEPS

_DEV_COMMANDS = {"/reset", "/debug", "/state", "/business", "/reconnect_facebook", "/subscribe_ig"}


def is_dev_command(message: str) -> bool:
    env = os.getenv("APP_ENV")
    msg = message.strip().lower()
    print(f"DEV_CMD CHECK: APP_ENV={env!r} message={msg!r} is_cmd={msg in _DEV_COMMANDS}")
    if env != "development":
        return False
    return msg in _DEV_COMMANDS


def handle_dev_command(user: User, message: str) -> str:
    cmd = message.strip().lower()

    if cmd == "/reset":
        return _cmd_reset(user)
    if cmd == "/debug":
        return _cmd_debug(user)
    if cmd == "/state":
        return _cmd_state(user)
    if cmd == "/business":
        return _cmd_business(user)
    if cmd == "/reconnect_facebook":
        return _cmd_reconnect_facebook(user)
    if cmd == "/subscribe_ig":
        return _cmd_subscribe_ig(user)

    return "[dev] unknown command"


def _cmd_reset(user: User) -> str:
    business = get_business(user.id)
    if business:
        SocialAccountRepository().delete_by_business(business.id)
    delete_conversation_state(user.id)
    delete_business(user.id)
    reset_user_profile(user)
    return "[dev] reset complete — send any message to restart onboarding"


def _cmd_state(user: User) -> str:
    state = get_conversation_state(user.id)
    if state is None:
        return "[dev] state: None (no conversation state found)"
    completed = state.step >= NUM_STEPS
    step_name = STEPS[state.step]["key"] if not completed else "completed"
    return f"[dev] step: {state.step}/{NUM_STEPS} | name: {step_name} | completed: {completed}"


def _cmd_business(user: User) -> str:
    business = get_business(user.id)
    if business is None:
        return "[dev] no business profile found"
    return (
        f"[dev] business profile:\n"
        f"  id: {business.id}\n"
        f"  brand_name: {business.brand_name}\n"
        f"  what_you_do: {business.what_you_do}\n"
        f"  writing_language: {business.writing_language}\n"
        f"  writing_style: {business.writing_style}\n"
        f"  communication_preferences: {business.communication_preferences}"
    )


def _cmd_reconnect_facebook(user: User) -> str:
    import os
    from src.db.repositories.auth_session import AuthSessionRepository

    business = get_business(user.id)
    if not business:
        return "[dev] ❌ אין פרופיל עסק. עברי אונבורדינג קודם."

    SocialAccountRepository().delete_by_platform(business.id, "facebook")

    BASE_URL = os.getenv("BASE_URL", "https://mia-social-backend.onrender.com")
    state = AuthSessionRepository().create(
        business_id=business.id,
        channel="whatsapp",
        channel_user_id=user.phone_number,
        initiated_by=user.id,
        purpose="meta_connect",
    )
    url = f"{BASE_URL}/connect/{state}"
    return f"[dev] חשבונות פייסבוק נמחקו. חברי מחדש:\n\n{url}"


def _cmd_subscribe_ig(user: User) -> str:
    import requests as req
    business = get_business(user.id)
    if not business:
        return "[dev] ❌ אין פרופיל עסק."

    ig_accounts = SocialAccountRepository().get_by_business(business.id, platform="instagram")
    fb_accounts = SocialAccountRepository().get_by_business(business.id, platform="facebook")
    if not ig_accounts:
        return "[dev] ❌ אין חשבון אינסטגרם מחובר."

    # Build page_id → page_access_token lookup from Facebook accounts
    page_tokens = {}
    for fb in fb_accounts:
        pid = fb.get("page_id") or fb.get("platform_account_id")
        pt = (fb.get("metadata") or {}).get("page_access_token") or fb.get("access_token")
        if pid and pt:
            page_tokens[pid] = pt

    lines = []
    for acc in ig_accounts:
        ig_id = acc.get("platform_account_id")
        page_id = acc.get("page_id")
        username = acc.get("account_username", ig_id)

        # Approach 1: subscribe via the linked Facebook Page
        page_token = page_tokens.get(page_id) if page_id else None
        if page_token and page_id:
            try:
                r = req.post(
                    f"https://graph.facebook.com/v20.0/{page_id}/subscribed_apps",
                    params={"subscribed_fields": "instagram,mention", "access_token": page_token},
                    timeout=10,
                )
                body = r.json()
                lines.append(f"Page [{page_id}]: {body}")
                if body.get("success"):
                    lines.append(f"✅ @{username} — מנוי דרך Page")
                    continue
            except Exception as e:
                lines.append(f"Page error: {repr(e)}")

        # Approach 2: subscribe directly via IG user (old API)
        token = acc.get("access_token")
        try:
            r = req.post(
                f"https://graph.facebook.com/v20.0/{ig_id}/subscribed_apps",
                params={"subscribed_fields": "comments,mentions", "access_token": token},
                timeout=10,
            )
            body = r.json()
            lines.append(f"IG user [{ig_id}]: {body}")
            if body.get("success"):
                lines.append(f"✅ @{username} — מנוי ישירות")
            else:
                lines.append(f"❌ @{username} — שתי השיטות נכשלו")
        except Exception as e:
            lines.append(f"❌ @{username} — {repr(e)}")

    return "[dev] subscribe_ig:\n" + "\n".join(lines)


def _cmd_debug(user: User) -> str:
    state_info = _cmd_state(user)
    business_info = _cmd_business(user)
    return (
        f"[dev] user:\n"
        f"  id: {user.id}\n"
        f"  phone: {user.phone_number}\n"
        f"  name: {user.name}\n"
        f"  accessibility: {user.accessibility}\n\n"
        f"{state_info}\n\n"
        f"{business_info}"
    )
