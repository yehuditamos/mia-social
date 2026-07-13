import os
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
