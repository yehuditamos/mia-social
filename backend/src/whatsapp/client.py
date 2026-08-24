import os
from pathlib import Path
import requests

_GRAPH = "https://graph.facebook.com/v19.0"


def _phone_id():
    return os.getenv("WHATSAPP_PHONE_NUMBER_ID")


def _headers():
    return {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
        "Content-Type": "application/json",
    }


def send_message(to: str, body: str) -> None:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    print("SEND_MESSAGE START — to:", to)
    try:
        res = requests.post(f"{_GRAPH}/{_phone_id()}/messages", json=payload, headers=_headers())
        print("SEND_MESSAGE RESPONSE — status:", res.status_code)
        print("SEND_MESSAGE RESPONSE — body:", res.text)
    except Exception as e:
        print("SEND_MESSAGE ERROR:", repr(e))


def send_image(to: str, image_url: str, caption: str = "") -> None:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    print("SEND_IMAGE START — to:", to, "url:", image_url[:60])
    try:
        res = requests.post(f"{_GRAPH}/{_phone_id()}/messages", json=payload, headers=_headers())
        print("SEND_IMAGE RESPONSE — status:", res.status_code)
    except Exception as e:
        print("SEND_IMAGE ERROR:", repr(e))


def update_business_profile_picture(image_path: str) -> dict:
    """Upload an image to Meta and set it as this number's WhatsApp profile photo."""
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    app_id = os.getenv("META_APP_ID")
    phone_id = _phone_id()
    if not token or not app_id or not phone_id:
        raise RuntimeError("Missing WhatsApp/Meta configuration")

    image = Path(image_path)
    image_bytes = image.read_bytes()
    content_type = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"

    session = requests.post(
        f"{_GRAPH}/{app_id}/uploads",
        params={
            "file_length": len(image_bytes),
            "file_type": content_type,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    session.raise_for_status()
    upload_id = session.json()["id"]

    uploaded = requests.post(
        f"{_GRAPH}/{upload_id}",
        data=image_bytes,
        headers={
            "Authorization": f"OAuth {token}",
            "file_offset": "0",
            "Content-Type": "application/octet-stream",
        },
        timeout=60,
    )
    uploaded.raise_for_status()
    handle = uploaded.json()["h"]

    updated = requests.post(
        f"{_GRAPH}/{phone_id}/whatsapp_business_profile",
        json={
            "messaging_product": "whatsapp",
            "profile_picture_handle": handle,
        },
        headers=_headers(),
        timeout=30,
    )
    updated.raise_for_status()
    return updated.json()
