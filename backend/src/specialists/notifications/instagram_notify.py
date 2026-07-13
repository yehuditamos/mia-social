import requests
from src.db.connection import get_base_url, get_headers
from src.db.repositories.social_account import SocialAccountRepository


def handle_ig_entry(entry: dict) -> None:
    ig_user_id = entry.get("id")
    if not ig_user_id:
        return
    for change in entry.get("changes", []):
        field = change.get("field")
        value = change.get("value", {})
        if field == "comments":
            _handle_comment(ig_user_id, value)
        elif field == "mentions":
            _handle_mention(ig_user_id, value)
        else:
            print(f"[IG NOTIFY] Unhandled field: {field}")


def _handle_comment(ig_user_id: str, value: dict) -> None:
    phone = _get_phone_by_ig_user(ig_user_id)
    if not phone:
        print(f"[IG NOTIFY] No user for ig_user_id={ig_user_id}")
        return

    username = value.get("from", {}).get("username", "מישהי")
    text = value.get("text", "")
    media_type = value.get("media", {}).get("media_product_type", "POST")
    type_label = "סטורי" if media_type == "STORY" else "פוסט"

    msg = f"💬 תגובה חדשה על ה{type_label} שלך!\n\n@{username} כתב:\n\"{text}\""

    from src.whatsapp.client import send_message
    send_message(phone, msg)
    print(f"[IG NOTIFY] Comment notification sent to {phone} from @{username}")


def _handle_mention(ig_user_id: str, value: dict) -> None:
    phone = _get_phone_by_ig_user(ig_user_id)
    if not phone:
        print(f"[IG NOTIFY] No user for ig_user_id={ig_user_id}")
        return

    comment_id = value.get("comment_id")
    username = "מישהי"
    text = ""

    if comment_id:
        access_token = _get_access_token_by_ig_user(ig_user_id)
        if access_token:
            try:
                r = requests.get(
                    "https://graph.facebook.com/v20.0/" + comment_id,
                    params={"fields": "text,username", "access_token": access_token},
                    timeout=5,
                )
                d = r.json()
                text = d.get("text", "")
                username = d.get("username", "מישהי")
            except Exception as e:
                print(f"[IG NOTIFY] Failed to fetch mention text: {repr(e)}")

    if text:
        msg = f"📣 @{username} הזכיר אותך בתגובה:\n\n\"{text}\""
    else:
        msg = "📣 מישהו הזכיר אותך! כדאי לבדוק את האינסטגרם 🙂"

    from src.whatsapp.client import send_message
    send_message(phone, msg)
    print(f"[IG NOTIFY] Mention notification sent to {phone}")


def _get_phone_by_ig_user(ig_user_id: str):
    """ig_user_id → social_accounts → businesses → users → phone_number"""
    try:
        account = SocialAccountRepository().get_by_platform_account_id("instagram", ig_user_id)
        if not account:
            return None
        business_id = account.get("business_id")
        if not business_id:
            return None

        res = requests.get(
            f"{get_base_url()}/businesses",
            headers=get_headers(),
            params={"id": f"eq.{business_id}", "limit": "1"},
        )
        businesses = res.json()
        if not isinstance(businesses, list) or not businesses:
            return None
        user_id = businesses[0].get("user_id")
        if not user_id:
            return None

        res2 = requests.get(
            f"{get_base_url()}/users",
            headers=get_headers(),
            params={"id": f"eq.{user_id}", "limit": "1"},
        )
        users = res2.json()
        if not isinstance(users, list) or not users:
            return None
        return users[0].get("phone_number")
    except Exception as e:
        print(f"[IG NOTIFY] Phone lookup error: {repr(e)}")
        return None


def _get_access_token_by_ig_user(ig_user_id: str):
    try:
        account = SocialAccountRepository().get_by_platform_account_id("instagram", ig_user_id)
        return account.get("access_token") if account else None
    except Exception:
        return None
