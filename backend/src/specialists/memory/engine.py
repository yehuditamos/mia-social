from typing import Optional
from src.db.connection import get_client
from src.specialists.memory.models import User, Business, ConversationState


def get_user(phone_number: str) -> Optional[User]:
    try:
        res = get_client().table("users").select("*").eq("phone_number", phone_number).execute()
        if not res.data:
            return None
        d = res.data[0]
        return User(
            phone_number=d["phone_number"],
            id=d["id"],
            name=d.get("name"),
            accessibility=d.get("accessibility", False),
        )
    except Exception:
        return None


def save_user(user: User) -> User:
    res = get_client().table("users").insert({
        "phone_number": user.phone_number,
        "name": user.name,
        "accessibility": user.accessibility,
    }).execute()
    user.id = res.data[0]["id"]
    return user


def update_user(user: User) -> None:
    get_client().table("users").update({
        "name": user.name,
        "accessibility": user.accessibility,
    }).eq("id", user.id).execute()


def get_business(user_id: str) -> Optional[Business]:
    try:
        res = get_client().table("businesses").select("*").eq("user_id", user_id).execute()
        if not res.data:
            return None
        d = res.data[0]
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
    get_client().table("businesses").upsert(
        {"user_id": user_id, field: value},
        on_conflict="user_id",
    ).execute()


def get_conversation_state(user_id: str) -> Optional[ConversationState]:
    try:
        res = get_client().table("conversation_states").select("*").eq("user_id", user_id).execute()
        if not res.data:
            return None
        d = res.data[0]
        return ConversationState(user_id=d["user_id"], step=d["step"], id=d["id"])
    except Exception:
        return None


def create_conversation_state(user_id: str) -> ConversationState:
    res = get_client().table("conversation_states").insert({
        "user_id": user_id,
        "step": 0,
    }).execute()
    d = res.data[0]
    return ConversationState(user_id=d["user_id"], step=d["step"], id=d["id"])


def update_conversation_state(user_id: str, step: int) -> None:
    get_client().table("conversation_states").update({
        "step": step,
    }).eq("user_id", user_id).execute()
