import os
import requests


_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"


def generate_caption(brand_name: str, what_you_do: str, writing_style: str,
                     writing_language: str, topic: str, edit_note: str = None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    lang_instruction = "Write in Hebrew." if writing_language and "עברית" in writing_language else "Write in English."
    if writing_language and "שתי" in writing_language:
        lang_instruction = "Write in Hebrew."

    style_map = {
        "1": "warm and personal",
        "חמים": "warm and personal",
        "2": "professional",
        "מקצועיים": "professional",
        "3": "a mix of warm and professional",
        "שילוב": "a mix of warm and professional",
    }
    style = next((v for k, v in style_map.items() if k in (writing_style or "")), "warm and professional")

    system = (
        f"You are a social media copywriter for {brand_name or 'a business'}. "
        f"The business: {what_you_do or 'helps customers'}. "
        f"Tone: {style}. {lang_instruction} "
        "Write engaging Instagram/Facebook captions. "
        "Include 3-5 relevant emojis. Include 3-5 relevant hashtags at the end. "
        "Keep it under 200 words. Return ONLY the caption text, nothing else."
    )

    user_msg = f"Write a caption about: {topic}"
    if edit_note:
        user_msg += f"\n\nPrevious caption needs this change: {edit_note}"

    payload = {
        "model": _MODEL,
        "max_tokens": 512,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
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
    print("CAPTION_GEN status:", res.status_code)

    if res.status_code != 200 or "content" not in data:
        raise RuntimeError(f"Caption generation failed: {data}")

    return data["content"][0]["text"].strip()
