import os
import requests


def is_duplicate_and_mark(message_id: str) -> bool:
    """
    Returns True if this message_id was already processed (duplicate).
    Atomically inserts the ID — if insert succeeds it's new, if 409 it's a duplicate.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not service_key or not message_id:
        return False

    try:
        res = requests.post(
            f"{supabase_url}/processed_webhooks",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={"message_id": message_id},
            timeout=5,
        )
        if res.status_code in (200, 201):
            return False  # inserted — new message
        if res.status_code == 409:
            return True   # conflict — duplicate
        print(f"[DEDUP] unexpected status={res.status_code} for id={message_id}")
        return False
    except Exception as e:
        print(f"[DEDUP] error: {repr(e)} — allowing message through")
        return False
