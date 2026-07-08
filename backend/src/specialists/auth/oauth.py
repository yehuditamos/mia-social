import os
import time
import uuid
import requests
from urllib.parse import urlencode

_GRAPH = "https://graph.facebook.com/v20.0"
_DIALOG = "https://www.facebook.com/v20.0/dialog/oauth"
# In-memory state store — POC only, not for production
_pending_states: dict = {}
_STATE_TTL = 600  # 10 minutes


def generate_oauth_url() -> str:
    state = str(uuid.uuid4())
    _pending_states[state] = time.time()
    print(f"STATE GENERATED: {state}")
    print(f"PENDING STATES AFTER ADD: {list(_pending_states.keys())}")

    params = urlencode({
        "client_id": os.getenv("META_APP_ID"),
        "redirect_uri": os.getenv("META_REDIRECT_URI"),
        "config_id": os.getenv("META_CONFIG_ID"),
        "response_type": "code",
        "state": state,
    })
    return f"{_DIALOG}?{params}"


def validate_state(state: str) -> bool:
    print(f"STATE RECEIVED IN CALLBACK: {state}")
    print(f"PENDING STATES BEFORE VALIDATE: {list(_pending_states.keys())}")
    created_at = _pending_states.pop(state, None)
    if created_at is None:
        print("STATE NOT FOUND IN PENDING STATES — dict is empty or process restarted")
        return False
    return (time.time() - created_at) < _STATE_TTL


def exchange_code_for_token(code: str) -> str:
    secret = os.getenv("META_APP_SECRET")
    print("APP SECRET LENGTH:", len(secret) if secret else None)
    res = requests.get(
        f"{_GRAPH}/oauth/access_token",
        params={
            "client_id": os.getenv("META_APP_ID"),
            "client_secret": os.getenv("META_APP_SECRET"),
            "redirect_uri": os.getenv("META_REDIRECT_URI"),
            "code": code,
        },
    )
    data = res.json()
    print("TOKEN EXCHANGE:", data)
    if "error" in data:
        raise Exception(f"Token exchange failed: {data['error']}")
    return data["access_token"]


def get_long_lived_token(short_token: str) -> dict:
    res = requests.get(
        f"{_GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": os.getenv("META_APP_ID"),
            "client_secret": os.getenv("META_APP_SECRET"),
            "fb_exchange_token": short_token,
        },
    )
    data = res.json()
    print("LONG_LIVED TOKEN:", data)
    if "error" in data:
        raise Exception(f"Long-lived token exchange failed: {data['error']}")
    return data


def get_connected_assets(user_token: str) -> dict:
    pages_res = requests.get(
        f"{_GRAPH}/me/accounts",
        params={"access_token": user_token, "fields": "id,name,access_token"},
    )
    pages_data = pages_res.json()
    print("PAGES:", pages_data)

    assets = {"pages": [], "instagram_accounts": []}

    for page in pages_data.get("data", []):
        assets["pages"].append({"id": page["id"], "name": page["name"]})

        ig_res = requests.get(
            f"{_GRAPH}/{page['id']}",
            params={
                "fields": "instagram_business_account{id,name,username}",
                "access_token": page.get("access_token", user_token),
            },
        )
        ig_data = ig_res.json()
        print(f"INSTAGRAM FOR PAGE {page['id']}:", ig_data)

        ig = ig_data.get("instagram_business_account")
        if ig:
            assets["instagram_accounts"].append({
                "ig_user_id": ig["id"],
                "name": ig.get("name"),
                "username": ig.get("username"),
                "linked_page_id": page["id"],
            })

    return assets
