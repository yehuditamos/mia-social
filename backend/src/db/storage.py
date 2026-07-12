import os
import uuid
import base64
import requests


def upload_image(image_b64: str, mime_type: str, filename_hint: str = None) -> str:
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not service_key:
        raise RuntimeError("SUPABASE_SERVICE_KEY is not set")

    ext = mime_type.split("/")[-1] if "/" in mime_type else "jpg"
    filename = f"{filename_hint or str(uuid.uuid4())}.{ext}"
    image_bytes = base64.b64decode(image_b64)

    res = requests.post(
        f"{supabase_url}/storage/v1/object/post-media/{filename}",
        headers={
            "Authorization": f"Bearer {service_key}",
            "Content-Type": mime_type,
        },
        data=image_bytes,
        timeout=30,
    )
    print("STORAGE UPLOAD status:", res.status_code)
    print("STORAGE UPLOAD body:", res.text[:200])

    if res.status_code not in (200, 201):
        raise RuntimeError(f"Storage upload failed: {res.text}")

    return f"{supabase_url}/storage/v1/object/public/post-media/{filename}"
