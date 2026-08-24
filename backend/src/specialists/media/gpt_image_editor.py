import base64
import os
import re
import uuid

import requests

from src.db.storage import upload_image


_EDIT_URL = "https://api.openai.com/v1/images/edits"
_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")


def edit_for_story(
    image_b64: str,
    mime_type: str,
    instruction: str,
    business_context: str = "",
) -> str:
    """Edit one user image and return a public URL suitable for preview/publishing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    image_bytes = base64.b64decode(image_b64)
    extension = _extension_for(mime_type)
    prompt = _build_prompt(instruction, business_context)

    response = requests.post(
        _EDIT_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        files=[
            ("image[]", (f"source.{extension}", image_bytes, mime_type)),
        ],
        data={
            "model": _MODEL,
            "prompt": prompt,
            "size": "1024x1824",
            "quality": "medium",
            "output_format": "jpeg",
        },
        timeout=150,
    )
    data = response.json()
    print(
        f"[GPT IMAGE EDIT] status={response.status_code} "
        f"request_id={response.headers.get('x-request-id', '')}"
    )
    if response.status_code != 200:
        raise RuntimeError(f"OpenAI image edit failed: {data}")

    results = data.get("data") or []
    edited_b64 = results[0].get("b64_json") if results else None
    if not edited_b64:
        raise RuntimeError("OpenAI image edit returned no image")

    return upload_image(
        edited_b64,
        "image/jpeg",
        f"gpt_story_edit_{uuid.uuid4().hex[:12]}",
    )


def edit_story_from_url(image_url: str, instruction: str, business_context: str = "") -> str:
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    mime_type = response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
    image_b64 = base64.b64encode(response.content).decode("utf-8")
    return edit_for_story(image_b64, mime_type, instruction, business_context)


def _build_prompt(instruction: str, business_context: str = "") -> str:
    user_instruction = instruction.strip() or "צרי מהתמונה סטורי שלם ומוכן לפרסום"
    context = business_context.strip() or "No additional business context was supplied."
    required_copy = _extract_required_copy(user_instruction)
    copy_directive = (
        "Exact required Hebrew copy (mandatory):\n"
        f"{required_copy}\n\n"
        "Render every word of the exact required copy above. You may split it into "
        "professional line breaks, but do not rewrite, shorten, translate, correct, "
        "replace or add any words. Do not render any other text from the user's request."
        if required_copy
        else "No exact mandatory copy was detected. Use professional judgment about whether text helps."
    )
    return f"""You are the senior social media creative director and art director for this business.
Create one complete, publication-ready Instagram Story from the supplied image. The owner should only need to approve it.

Business context:
{context}

User request in Hebrew:
{user_instruction}

{copy_directive}

Creative standard:
- Make the strongest professional creative decision independently. Do not ask the owner to choose a style, filter, layout or copy.
- The result must feel intentional, premium, current and specific to the image and business, never like a generic template.
- Build a clear visual hierarchy, purposeful composition, tasteful depth and a cohesive palette that supports the subject.
- Avoid generic white frames, random gradients, heavy filters, clip-art decorations and filler emojis.
- Treat phrases such as "סומכת עלייך", "תעשי מה שנראה לך", "תעצבי יפה" and "תעלי אותה ערוכה" as delegation instructions. NEVER print those phrases on the image.
- Text following an explicit Hebrew writing command such as "רק תכתבי", "תכתבי" or "תכתוב" is mandatory copy, even without quotation marks.
- When mandatory copy is provided above, use only that copy and make its typography, hierarchy and placement professionally excellent.
- If no mandatory copy was provided, decide whether copy improves the story.
- If copy improves it, write one short, sharp Hebrew line based on the actual image and business goal, maximum 6 words. No generic motivational filler.
- If accurate Hebrew cannot be rendered confidently, create a strong text-free visual instead of broken or invented text.

Non-negotiable preservation rules:
- Preserve every person's identity, exact facial features, body proportions, skin tone, pose and clothing.
- Do not beautify, reshape, age, replace or invent a person.
- Preserve existing logos, products and factual details unless the user explicitly requests changing them.
- Preserve existing readable text as faithfully as possible. Never invent dates, prices, claims or event details.
- Improve only the visual treatment requested: composition, background, lighting, color, depth, framing and tasteful design details.
- Keep the result photorealistic when the source is a photograph.
- Compose for a vertical 9:16 Instagram Story with safe margins near the top and bottom.
"""


def _extract_required_copy(instruction: str) -> str:
    """Extract literal Story copy after a direct Hebrew writing instruction."""
    normalized = (instruction or "").strip()
    patterns = (
        r"(?:^|[,:\-–—]\s*|\s)(?:רק\s+)?תכתבי(?:\s+על(?:יה|יו|\s+התמונה))?\s*[:\-–—]?\s*(.+)$",
        r"(?:^|[,:\-–—]\s*|\s)(?:רק\s+)?תכתוב(?:\s+על(?:יה|יו|\s+התמונה))?\s*[:\-–—]?\s*(.+)$",
        r"(?:^|[,:\-–—]\s*|\s)(?:רק\s+)?לכתוב\s*[:\-–—]?\s*(.+)$",
        r"[\"“](.+?)[\"”]",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip().strip('"“”')
    return ""


def _extension_for(mime_type: str) -> str:
    base = (mime_type or "image/jpeg").split(";", 1)[0].lower()
    return {
        "image/png": "png",
        "image/webp": "webp",
    }.get(base, "jpg")
