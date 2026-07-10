import uuid
import requests
from datetime import datetime, timedelta, timezone
from src.db.connection import get_base_url, get_headers

SESSION_TTL_MINUTES = 10


class AuthSessionRepository:

    def create(self, business_id: str, channel: str, channel_user_id: str, initiated_by: str = None) -> str:
        state = str(uuid.uuid4())
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)).isoformat()

        payload = {
            "state": state,
            "business_id": business_id,
            "channel": channel,
            "channel_user_id": channel_user_id,
            "expires_at": expires_at,
        }
        if initiated_by:
            payload["initiated_by"] = initiated_by

        res = requests.post(
            f"{get_base_url()}/auth_sessions",
            headers=get_headers(),
            json=payload,
        )
        print("AUTH_SESSION CREATE status:", res.status_code)
        print("AUTH_SESSION CREATE body:", res.text)
        return state

    def consume(self, state: str) -> dict:
        res = requests.get(
            f"{get_base_url()}/auth_sessions",
            headers=get_headers(),
            params={"state": f"eq.{state}", "limit": "1"},
        )
        data = res.json()
        print("AUTH_SESSION LOOKUP:", data)

        if not data:
            raise ValueError("Session not found")

        session = data[0]

        expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            raise ValueError("Session expired")

        if session.get("used_at"):
            raise ValueError("Session already used")

        requests.patch(
            f"{get_base_url()}/auth_sessions",
            headers=get_headers(prefer="return=minimal"),
            params={"state": f"eq.{state}"},
            json={"used_at": datetime.now(timezone.utc).isoformat()},
        )

        return {
            "business_id": session["business_id"],
            "initiated_by": session.get("initiated_by"),
            "channel": session["channel"],
            "channel_user_id": session["channel_user_id"],
        }
