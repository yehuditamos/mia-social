import os


def get_base_url() -> str:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    # Strip /rest/v1 if already included in env var
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    base = url + "/rest/v1"
    print("SUPABASE BASE URL:", base)
    return base


def get_headers(prefer: str = "return=representation") -> dict:
    key = os.getenv("SUPABASE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }
