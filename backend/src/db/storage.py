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

    public_url = f"{supabase_url}/storage/v1/object/public/post-media/{filename}"
    print(f"[IG STEP 3] Uploading to Supabase Storage: {filename} ({len(image_bytes)} bytes)")

    res = requests.post(
        f"{supabase_url}/storage/v1/object/post-media/{filename}",
        headers={
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "Content-Type": mime_type,
        },
        data=image_bytes,
        timeout=30,
    )
    print(f"[IG STEP 3] upload status={res.status_code} body={res.text[:200]}")

    if res.status_code not in (200, 201):
        raise RuntimeError(f"[IG FAIL step=storage_upload status={res.status_code}] {res.text}")

    # Step 4: Verify public URL is accessible
    print(f"[IG STEP 4] Verifying public URL: {public_url}")
    check = requests.head(public_url, timeout=10)
    print(f"[IG STEP 4] public URL check status={check.status_code}")
    if check.status_code not in (200, 206):
        raise RuntimeError(f"[IG FAIL step=public_url_check status={check.status_code}] URL not publicly accessible: {public_url}")

    return public_url
