import os


def get_base_url() -> str:
    return os.getenv("SUPABASE_URL").rstrip("/") + "/rest/v1"


def get_headers(prefer: str = "return=representation") -> dict:
    key = os.getenv("SUPABASE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }
