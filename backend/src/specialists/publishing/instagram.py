import time
import requests

_GRAPH = "https://graph.facebook.com/v20.0"


def publish_image_to_instagram(ig_user_id: str, image_url: str,
                                caption: str, access_token: str) -> str:
    print(f"[IG STEP 5] ig_user_id={ig_user_id}")
    print(f"[IG STEP 5] token_prefix={access_token[:12] if access_token else None}...")
    print(f"[IG STEP 6] image_url={image_url}")

    # Step 1: Create media container
    print("[IG STEP 7a] Creating media container...")
    res1 = requests.post(
        f"{_GRAPH}/{ig_user_id}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    print(f"[IG STEP 7b] Container create status: {res1.status_code}")
    print(f"[IG STEP 7b] Container create body: {res1.text}")
    data1 = res1.json()

    if "error" in data1:
        raise RuntimeError(
            f"[IG FAIL step=container_create status={res1.status_code}] "
            f"code={data1['error'].get('code')} "
            f"type={data1['error'].get('type')} "
            f"message={data1['error'].get('message')}"
        )

    creation_id = data1.get("id")
    if not creation_id:
        raise RuntimeError(f"[IG FAIL step=container_create] No id in response: {data1}")

    print(f"[IG STEP 7c] creation_id={creation_id}")

    # Step 2: Check container status (must be FINISHED before publishing)
    print("[IG STEP 8] Checking container status...")
    for attempt in range(6):
        status_res = requests.get(
            f"{_GRAPH}/{creation_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=15,
        )
        status_data = status_res.json()
        status_code = status_data.get("status_code")
        print(f"[IG STEP 8] attempt={attempt+1} status_code={status_code} body={status_data}")

        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"[IG FAIL step=container_status] Container ERROR: {status_data}")
        if status_code == "EXPIRED":
            raise RuntimeError(f"[IG FAIL step=container_status] Container EXPIRED: {status_data}")

        time.sleep(3)
    else:
        raise RuntimeError(f"[IG FAIL step=container_status] Timed out waiting for FINISHED, last={status_data}")

    # Step 3: Publish
    print(f"[IG STEP 9a] Publishing creation_id={creation_id}...")
    res2 = requests.post(
        f"{_GRAPH}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    print(f"[IG STEP 9b] Publish status: {res2.status_code}")
    print(f"[IG STEP 9b] Publish body: {res2.text}")
    data2 = res2.json()

    if "error" in data2:
        raise RuntimeError(
            f"[IG FAIL step=media_publish status={res2.status_code}] "
            f"code={data2['error'].get('code')} "
            f"type={data2['error'].get('type')} "
            f"message={data2['error'].get('message')}"
        )

    post_id = data2.get("id", "")
    print(f"[IG SUCCESS] post_id={post_id}")
    return f"https://www.instagram.com/p/{post_id}/"


def publish_story_to_instagram(ig_user_id: str, media_url: str, access_token: str,
                               media_kind: str = "image") -> None:
    print(f"[STORY STEP 1] ig_user_id={ig_user_id} kind={media_kind} url={media_url}")

    url_key = "video_url" if media_kind == "video" else "image_url"
    res1 = requests.post(
        f"{_GRAPH}/{ig_user_id}/media",
        data={
            url_key: media_url,
            "media_type": "STORIES",
            "access_token": access_token,
        },
        timeout=30,
    )
    print(f"[STORY STEP 2] Container status: {res1.status_code} body: {res1.text}")
    data1 = res1.json()

    if "error" in data1:
        raise RuntimeError(
            f"[STORY FAIL step=container_create] "
            f"code={data1['error'].get('code')} "
            f"message={data1['error'].get('message')}"
        )

    creation_id = data1.get("id")
    if not creation_id:
        raise RuntimeError(f"[STORY FAIL] No id in response: {data1}")

    print(f"[STORY STEP 2] creation_id={creation_id}")

    max_attempts, interval = (24, 5) if media_kind == "video" else (6, 3)
    for attempt in range(max_attempts):
        status_res = requests.get(
            f"{_GRAPH}/{creation_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=15,
        )
        status_data = status_res.json()
        status_code = status_data.get("status_code")
        print(f"[STORY STEP 3] attempt={attempt + 1}/{max_attempts} status_code={status_code}")

        if status_code == "FINISHED":
            break
        if status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"[STORY FAIL step=container_status] {status_data}")
        time.sleep(interval)
    else:
        raise RuntimeError(f"[STORY FAIL] Timed out, last={status_data}")

    res2 = requests.post(
        f"{_GRAPH}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    print(f"[STORY STEP 4] Publish status: {res2.status_code} body: {res2.text}")
    data2 = res2.json()

    if "error" in data2:
        raise RuntimeError(
            f"[STORY FAIL step=media_publish] "
            f"code={data2['error'].get('code')} "
            f"message={data2['error'].get('message')}"
        )

    print(f"[STORY SUCCESS] story_id={data2.get('id')}")
