import os
import requests
import base64

_GRAPH = "https://graph.facebook.com/v21.0"


def download_media(media_id: str) -> tuple:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    print(f"[IG STEP 1] Fetching WhatsApp media metadata for id={media_id}")
    meta_res = requests.get(
        f"{_GRAPH}/{media_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    print(f"[IG STEP 1] meta status={meta_res.status_code}")
    meta = meta_res.json()
    url = meta.get("url")
    mime_type = meta.get("mime_type", "image/jpeg")
    print(f"[IG STEP 1] mime_type={mime_type} url_present={bool(url)}")

    if not url:
        raise RuntimeError(f"[IG FAIL step=whatsapp_media_url] {meta}")

    print(f"[IG STEP 2] Downloading image...")
    img_res = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    print(f"[IG STEP 2] download status={img_res.status_code} size={len(img_res.content)} bytes")
    if img_res.status_code != 200:
        raise RuntimeError(f"[IG FAIL step=whatsapp_media_download] status={img_res.status_code}")

    b64 = base64.b64encode(img_res.content).decode("utf-8")
    return b64, mime_type
