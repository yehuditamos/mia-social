import requests
from datetime import datetime, timezone
from src.db.connection import get_base_url, get_headers


class SocialAccountRepository:

    def has_active_accounts(self, business_id: str) -> bool:
        res = requests.get(
            f"{get_base_url()}/social_accounts",
            headers=get_headers(),
            params={"business_id": f"eq.{business_id}", "status": "eq.active", "limit": "1"},
        )
        data = res.json()
        return isinstance(data, list) and len(data) > 0

    def upsert(self, business_id: str, platform: str, platform_account_id: str, record: dict) -> None:
        payload = {
            "business_id": business_id,
            "platform": platform,
            "platform_account_id": platform_account_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **record,
        }

        res = requests.post(
            f"{get_base_url()}/social_accounts",
            headers=get_headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
        )
        print(f"SOCIAL_ACCOUNT UPSERT [{platform}/{platform_account_id}] status:", res.status_code)
        print(f"SOCIAL_ACCOUNT UPSERT [{platform}/{platform_account_id}] body:", res.text)
