import os
import requests
import base64

_GRAPH = "https://graph.facebook.com/v21.0"


def download_media(media_id: str) -> tuple:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    meta_res = requests.get(
        f"{_GRAPH}/{media_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    meta = meta_res.json()
    url = meta.get("url")
    mime_type = meta.get("mime_type", "image/jpeg")

    if not url:
        raise RuntimeError(f"Could not get media URL: {meta}")

    img_res = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    b64 = base64.b64encode(img_res.content).decode("utf-8")
    return b64, mime_type
