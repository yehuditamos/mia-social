import requests
from typing import Optional
from src.db.connection import get_base_url, get_headers


class PendingIgReplyRepository:

    def store(self, phone: str, comment_id: str, ig_user_id: str, access_token: str) -> None:
        requests.post(
            f"{get_base_url()}/pending_ig_replies",
            headers=get_headers(prefer="resolution=merge-duplicates,return=minimal"),
            json={
                "phone_number": phone,
                "comment_id": comment_id,
                "ig_user_id": ig_user_id,
                "access_token": access_token,
            },
        )

    def get_and_clear(self, phone: str) -> Optional[dict]:
        res = requests.get(
            f"{get_base_url()}/pending_ig_replies",
            headers=get_headers(),
            params={"phone_number": f"eq.{phone}", "limit": "1"},
        )
        data = res.json()
        if not isinstance(data, list) or not data:
            return None
        record = data[0]
        requests.delete(
            f"{get_base_url()}/pending_ig_replies",
            headers=get_headers(prefer="return=minimal"),
            params={"phone_number": f"eq.{phone}"},
        )
        return record
