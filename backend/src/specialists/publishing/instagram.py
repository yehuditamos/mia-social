import requests

_GRAPH = "https://graph.facebook.com/v20.0"


def publish_image_to_instagram(ig_user_id: str, image_url: str,
                                caption: str, access_token: str) -> str:
    res1 = requests.post(
        f"{_GRAPH}/{ig_user_id}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    data1 = res1.json()
    print("INSTAGRAM MEDIA CREATE status:", res1.status_code, data1)

    if "error" in data1:
        raise RuntimeError(f"Instagram media create failed: {data1['error']}")

    creation_id = data1.get("id")
    if not creation_id:
        raise RuntimeError(f"No creation_id: {data1}")

    res2 = requests.post(
        f"{_GRAPH}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    data2 = res2.json()
    print("INSTAGRAM PUBLISH status:", res2.status_code, data2)

    if "error" in data2:
        raise RuntimeError(f"Instagram publish failed: {data2['error']}")

    post_id = data2.get("id", "")
    return f"https://www.instagram.com/p/{post_id}/"
