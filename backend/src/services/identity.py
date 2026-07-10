from src.specialists.memory.engine import get_user, get_business
from src.specialists.memory.models import User, Business


class IdentityService:

    def resolve(self, channel: str, channel_user_id: str) -> tuple:
        if channel == "whatsapp":
            return self._resolve_whatsapp(channel_user_id)
        raise ValueError(f"Unsupported channel: {channel}")

    def _resolve_whatsapp(self, phone_number: str) -> tuple:
        user = get_user(phone_number)
        if user is None:
            raise ValueError(f"No user found for phone: {phone_number}")

        business = get_business(user.id)
        if business is None:
            raise ValueError(f"No business found for user: {user.id}")

        return user, business
