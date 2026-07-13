import requests
from datetime import datetime, timezone, timedelta
from src.db.connection import get_base_url, get_headers


class SeenIgCommentRepository:

    def is_seen(self, comment_id: str) -> bool:
        res = requests.get(
            f"{get_base_url()}/seen_ig_comments",
            headers=get_headers(),
            params={"comment_id": f"eq.{comment_id}", "limit": "1"},
        )
        data = res.json()
        return isinstance(data, list) and len(data) > 0

    def mark_seen(self, comment_id: str, ig_user_id: str) -> None:
        requests.post(
            f"{get_base_url()}/seen_ig_comments",
            headers=get_headers(prefer="resolution=ignore-duplicates,return=minimal"),
            json={"comment_id": comment_id, "ig_user_id": ig_user_id},
        )

    def cleanup_old(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        requests.delete(
            f"{get_base_url()}/seen_ig_comments",
            headers=get_headers(prefer="return=minimal"),
            params={"seen_at": f"lt.{cutoff}"},
        )
