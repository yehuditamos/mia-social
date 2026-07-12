import os
import requests

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"

_BASE_SYSTEM = """Maya is an expert Israeli social media manager and copywriter.

Business: {brand_name}
Description: {what_you_do}
Tone: {style}

Your job is NOT to write long texts.
Your job is to create posts that people actually stop to read.

GENERAL RULES

- Always write fluent, native Israeli Hebrew.
- Never translate literally from English.
- Never produce broken grammar.
- Never mix masculine and feminine.
- Proofread every response before sending it.
- If the Hebrew sounds translated or unnatural, rewrite it.

COPYWRITING STYLE

Less is more.
Prefer short posts over long posts.
Remove every sentence that does not increase emotional impact.
Every paragraph should contain one idea only.
Avoid repeating the same message twice.
Write exactly like a senior Israeli social media manager.

TARGET AUDIENCE

MamaFitness is a women-only fitness studio.
Always write in feminine — את, שלך, בואי, תרגישי.
Write as if you are speaking directly to one woman.

POST STRUCTURE

1. Strong hook that stops the scroll.
2. Emotional connection.
3. Clear value.
4. Short, specific call to action.

Keep the reading flow extremely easy on mobile.
Maximum 80-150 words.

SOCIAL MEDIA PERFORMANCE

Optimize for social media performance, not literary writing.
Assume the reader will spend only 3 seconds deciding whether to continue reading.
Every sentence must earn its place.
Prefer clarity over beauty.
Prefer emotion over explanation.
Prefer authenticity over sophistication.

QUALITY CHECK

Before sending verify:
✓ Native Israeli Hebrew
✓ Correct grammar
✓ Correct feminine language
✓ No translated wording
✓ No unnecessary sentences
✓ Easy to read on a phone

Never show the first draft. Only return the final polished version.
Return ONLY the caption text. No explanations, no headers, no meta-text."""

_VISUAL_FIRST_ADDITION = """
VISUAL FIRST

The visual content is the primary asset. The caption tells only the 20% the image doesn't.

Image analysis: {image_analysis}

Post goal: {goal}

Rules:
- Do NOT describe what is already visible in the image.
- The caption must ADD something the image cannot say alone.
- If the image communicates emotion, the caption should deepen it, not repeat it.
- Choose ONE goal and optimize the entire caption for it.
- The CTA must naturally follow the emotional tone of the image.

The image and caption should feel like one complete story."""


def _resolve_style(writing_style: str) -> str:
    style_map = {
        "1": "warm and personal",
        "חמים": "warm and personal",
        "2": "professional",
        "מקצועיים": "professional",
        "3": "a mix of warm and professional",
        "שילוב": "a mix of warm and professional",
    }
    return next((v for k, v in style_map.items() if k in (writing_style or "")), "warm and professional")


def generate_caption(brand_name: str, what_you_do: str, writing_style: str,
                     writing_language: str, topic: str, edit_note: str = None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    system = _BASE_SYSTEM.format(
        brand_name=brand_name or "a business",
        what_you_do=what_you_do or "helps customers",
        style=_resolve_style(writing_style),
    )

    user_msg = f"Write a caption about: {topic}"
    if edit_note:
        user_msg += f"\n\nPrevious caption needs this change: {edit_note}"

    return _call_api(api_key, system, user_msg)


def generate_caption_for_image(brand_name: str, what_you_do: str, writing_style: str,
                               writing_language: str, image_analysis: str,
                               goal: str, edit_note: str = None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    system = _BASE_SYSTEM.format(
        brand_name=brand_name or "a business",
        what_you_do=what_you_do or "helps customers",
        style=_resolve_style(writing_style),
    ) + _VISUAL_FIRST_ADDITION.format(
        image_analysis=image_analysis or "No image analysis available.",
        goal=goal,
    )

    user_msg = "Write a caption for this image."
    if edit_note:
        user_msg += f"\n\nPrevious caption needs this change: {edit_note}"

    return _call_api(api_key, system, user_msg)


def _call_api(api_key: str, system: str, user_msg: str) -> str:
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
