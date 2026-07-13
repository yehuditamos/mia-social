import requests
from datetime import datetime, timezone, timedelta
from src.db.connection import get_base_url, get_headers
from src.db.repositories.seen_ig_comment import SeenIgCommentRepository
from src.db.repositories.pending_ig_reply import PendingIgReplyRepository

_GRAPH = "https://graph.facebook.com/v20.0"
_POLL_WINDOW_MINUTES = 15


def poll_all_accounts() -> int:
    seen_repo = SeenIgCommentRepository()
    ig_accounts = _get_all_ig_accounts()
    total = 0

    for acc in ig_accounts:
        ig_user_id = acc.get("platform_account_id")
        access_token = acc.get("access_token")
        business_id = acc.get("business_id")
        if not ig_user_id or not access_token or not business_id:
            continue

        phone = _get_phone_by_business(business_id)
        if not phone:
            continue

        media_ids = _get_recent_media(ig_user_id, access_token)
        for media_id in media_ids:
            comments = _get_recent_comments(media_id, access_token)
            for comment in comments:
                comment_id = comment.get("id")
                if not comment_id or seen_repo.is_seen(comment_id):
                    continue

                _notify(phone, comment, comment_id, ig_user_id, access_token)
                seen_repo.mark_seen(comment_id, ig_user_id)
                total += 1

    seen_repo.cleanup_old()
    print(f"[POLLER] Done — {total} new comments notified")
    return total


def _get_all_ig_accounts() -> list:
    try:
        res = requests.get(
            f"{get_base_url()}/social_accounts",
            headers=get_headers(),
            params={"platform": "eq.instagram", "status": "eq.active"},
        )
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[POLLER] get_all_ig_accounts error: {repr(e)}")
        return []


def _get_phone_by_business(business_id: str):
    try:
        r1 = requests.get(
            f"{get_base_url()}/businesses",
            headers=get_headers(),
            params={"id": f"eq.{business_id}", "limit": "1"},
        )
        biz = r1.json()
        if not isinstance(biz, list) or not biz:
            return None
        user_id = biz[0].get("user_id")
        if not user_id:
            return None

        r2 = requests.get(
            f"{get_base_url()}/users",
            headers=get_headers(),
            params={"id": f"eq.{user_id}", "limit": "1"},
        )
        users = r2.json()
        if not isinstance(users, list) or not users:
            return None
        return users[0].get("phone_number")
    except Exception as e:
        print(f"[POLLER] phone lookup error: {repr(e)}")
        return None


def _get_recent_media(ig_user_id: str, access_token: str) -> list:
    try:
        res = requests.get(
            f"{_GRAPH}/{ig_user_id}/media",
            params={"fields": "id", "limit": "10", "access_token": access_token},
            timeout=10,
        )
        return [m["id"] for m in res.json().get("data", []) if "id" in m]
    except Exception as e:
        print(f"[POLLER] get_recent_media error: {repr(e)}")
        return []


def _get_recent_comments(media_id: str, access_token: str) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_POLL_WINDOW_MINUTES)
    try:
        res = requests.get(
            f"{_GRAPH}/{media_id}/comments",
            params={
                "fields": "id,text,username,timestamp",
                "limit": "50",
                "access_token": access_token,
            },
            timeout=10,
        )
        recent = []
        for c in res.json().get("data", []):
            ts_str = c.get("timestamp", "")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts >= cutoff:
                    recent.append(c)
            except Exception:
                pass
        return recent
    except Exception as e:
        print(f"[POLLER] get_recent_comments error: {repr(e)}")
        return []


def _notify(phone: str, comment: dict, comment_id: str,
            ig_user_id: str, access_token: str) -> None:
    username = comment.get("username", "מישהי")
    text = comment.get("text", "")

    msg = (
        f"💬 תגובה חדשה על הפוסט שלך!\n\n"
        f"@{username} כתב:\n\"{text}\"\n\n"
        f"↩️ לענות — שלחי: ענה [ההודעה שלך]"
    )

    from src.whatsapp.client import send_message
    send_message(phone, msg)
    PendingIgReplyRepository().store(phone, comment_id, ig_user_id, access_token)
    print(f"[POLLER] Notified {phone} — @{username}: {text[:40]}")
