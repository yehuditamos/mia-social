import os
import requests


def send_message(to: str, body: str) -> None:
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    requests.post(url, json=payload, headers=headers)
