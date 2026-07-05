import requests
from typing import Optional
from src.db.connection import get_base_url, get_headers
from src.specialists.memory.models import User, Business, ConversationState


def get_user(phone_number: str) -> Optional[User]:
    try:
        res = requests.get(
            f"{get_base_url()}/users",
            headers=get_headers(),
            params={"phone_number": f"eq.{phone_number}", "limit": "1"},
        )
        data = res.json()
        if not data:
            return None
        d = data[0]
        return User(
            phone_number=d["phone_number"],
            id=d["id"],
            name=d.get("name"),
            accessibility=d.get("accessibility", False),
        )
    except Exception:
        return None


def save_user(user: User) -> User:
    res = requests.post(
        f"{get_base_url()}/users",
        headers=get_headers(),
        json={"phone_number": user.phone_number, "name": user.name, "accessibility": user.accessibility},
    )
    user.id = res.json()[0]["id"]
    return user


def update_user(user: User) -> None:
    requests.patch(
        f"{get_base_url()}/users",
        headers=get_headers(),
        params={"id": f"eq.{user.id}"},
        json={"name": user.name, "accessibility": user.accessibility},
    )


def get_business(user_id: str) -> Optional[Business]:
    try:
        res = requests.get(
            f"{get_base_url()}/businesses",
            headers=get_headers(),
            params={"user_id": f"eq.{user_id}", "limit": "1"},
        )
        data = res.json()
        if not data:
            return None
        d = data[0]
        return Business(
            user_id=d["user_id"],
            id=d["id"],
            brand_name=d.get("brand_name"),
            what_you_do=d.get("what_you_do"),
            writing_language=d.get("writing_language"),
            writing_style=d.get("writing_style"),
            communication_preferences=d.get("communication_preferences"),
        )
    except Exception:
        return None


def upsert_business_field(user_id: str, field: str, value: str) -> None:
    requests.post(
        f"{get_base_url()}/businesses",
        headers=get_headers(prefer="resolution=merge-duplicates,return=representation"),
        json={"user_id": user_id, field: value},
    )


def get_conversation_state(user_id: str) -> Optional[ConversationState]:
    try:
        res = requests.get(
            f"{get_base_url()}/conversation_states",
            headers=get_headers(),
            params={"user_id": f"eq.{user_id}", "limit": "1"},
        )
        data = res.json()
        if not data:
            return None
        d = data[0]
        return ConversationState(user_id=d["user_id"], step=d["step"], id=d["id"])
    except Exception:
        return None


def create_conversation_state(user_id: str) -> ConversationState:
    res = requests.post(
        f"{get_base_url()}/conversation_states",
        headers=get_headers(),
        json={"user_id": user_id, "step": 0},
    )
    d = res.json()[0]
    return ConversationState(user_id=d["user_id"], step=d["step"], id=d["id"])


def update_conversation_state(user_id: str, step: int) -> None:
    requests.patch(
        f"{get_base_url()}/conversation_states",
        headers=get_headers(),
        params={"user_id": f"eq.{user_id}"},
        json={"step": step},
    )
