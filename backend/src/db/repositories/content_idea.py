import requests
from src.db.connection import get_base_url, get_headers


class ContentIdeaRepository:

    def save(self, business_id: str, title: str, description: str) -> dict:
        res = requests.post(
            f"{get_base_url()}/content_ideas",
            headers=get_headers(),
            json={"business_id": business_id, "title": title, "description": description, "used": False},
        )
        print(f"[IDEA SAVE] status={res.status_code}")
        data = res.json()
        return data[0] if isinstance(data, list) and data else {}

    def get_unused(self, business_id: str) -> list:
        res = requests.get(
            f"{get_base_url()}/content_ideas",
            headers=get_headers(),
            params={
                "business_id": f"eq.{business_id}",
                "used": "eq.false",
                "order": "created_at.asc",
                "limit": "20",
            },
        )
        data = res.json()
        return data if isinstance(data, list) else []

    def get_by_index(self, business_id: str, index: int):
        ideas = self.get_unused(business_id)
        if 1 <= index <= len(ideas):
            return ideas[index - 1]
        return None

    def mark_used(self, idea_id: str) -> None:
        requests.patch(
            f"{get_base_url()}/content_ideas",
            headers=get_headers(prefer="return=minimal"),
            params={"id": f"eq.{idea_id}"},
            json={"used": True},
        )

    def count_unused(self, business_id: str) -> int:
        return len(self.get_unused(business_id))
