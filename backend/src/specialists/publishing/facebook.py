import requests

_GRAPH = "https://graph.facebook.com/v20.0"


def publish_text_post(page_id: str, page_access_token: str, message: str) -> str:
    res = requests.post(
        f"{_GRAPH}/{page_id}/feed",
        params={"access_token": page_access_token},
        json={"message": message},
        timeout=30,
    )
    data = res.json()
    print("FACEBOOK PUBLISH status:", res.status_code)
    print("FACEBOOK PUBLISH body:", data)

    if "error" in data:
        raise RuntimeError(f"Facebook publish failed: {data['error']}")

    post_id = data.get("id", "")
    return f"https://www.facebook.com/{post_id}"
