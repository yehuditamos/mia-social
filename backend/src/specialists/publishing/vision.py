import os
import requests

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"


def analyze_image(image_b64: str, mime_type: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")

    payload = {
        "model": _MODEL,
        "max_tokens": 400,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Analyze this image for social media caption writing. "
                        "In 4-6 sentences describe:\n"
                        "- What is happening and who is in it\n"
                        "- The dominant emotion and mood\n"
                        "- Key visual details: body language, environment, lighting, colors\n"
                        "- The story the image already tells on its own\n"
                        "- What the image does NOT communicate (what the caption should add)\n\n"
                        "Be specific. Write in English. This analysis will be used to write a Hebrew caption."
                    ),
                },
            ],
        }],
    }

    res = requests.post(
        _API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    data = res.json()
    print("VISION status:", res.status_code)

    if res.status_code != 200 or "content" not in data:
        raise RuntimeError(f"Vision analysis failed: {data}")

    return data["content"][0]["text"].strip()
