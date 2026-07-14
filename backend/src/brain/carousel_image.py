import io
import os
import uuid
import base64
import requests
from PIL import Image, ImageDraw, ImageFont

_W, _H = 1080, 1080  # Square for Instagram carousel
_FONT_SIZES = [96, 76, 60, 48, 38]
_MARGIN = int(_W * 0.12)
_MAX_W = _W - 2 * _MARGIN
_MAX_LINES = 5

_FONT_PATHS = [
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

_SLIDE_FORMAT_SYSTEM = """אתה מעצב גרפי ישראלי. קיבלת טקסט לשקופית קרוסלה.
חלק לשורות (עד 4 שורות). שמור על עברית תקינה. אל תוסיף ואל תגרע מילים.
ענה רק בשורות הטקסט, שורה אחת לכל שורה."""


def create_slide_image(text: str, bg_color: str = "black",
                       slide_num: int = None, total_slides: int = None) -> bytes:
    is_dark = any(w in bg_color.lower() for w in {"שחור", "black", "dark"})
    bg = (0, 0, 0) if is_dark else (255, 255, 255)
    fg = (255, 255, 255) if is_dark else (0, 0, 0)

    lines = _format_lines(text)

    img = Image.new("RGB", (_W, _H), color=bg)
    draw = ImageDraw.Draw(img)

    font = _pick_font(draw, lines)
    lh = _line_height(font)

    # Reserve bottom space for dots if needed
    dots_h = 50 if (slide_num is not None and total_slides and total_slides > 1) else 0
    usable_h = _H - dots_h
    total_text_h = len(lines) * lh
    y = (usable_h - total_text_h) // 2

    cx = _W // 2
    for line in lines:
        _draw_rtl(draw, line, font, fg, cx, y)
        y += lh

    if slide_num is not None and total_slides and total_slides > 1:
        _draw_dots(draw, slide_num, total_slides, fg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_slide_and_upload(text: str, bg_color: str,
                               slide_num: int = None, total: int = None) -> str:
    from src.db.storage import upload_image
    img_bytes = create_slide_image(text, bg_color, slide_num, total)
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    filename = f"carousel_{uuid.uuid4().hex[:10]}"
    return upload_image(img_b64, "image/png", filename)


def _draw_dots(draw, slide_num: int, total: int, fg):
    dot_r = 7
    gap = 24
    total_w = total * (2 * dot_r) + (total - 1) * (gap - 2 * dot_r)
    x_start = (_W - total_w) // 2
    y = _H - 35
    for i in range(total):
        cx = x_start + i * gap + dot_r
        if i == (slide_num - 1):
            fill = fg
        else:
            fill = tuple(min(c + 80, 255) if c < 128 else max(c - 80, 0) for c in fg)
        draw.ellipse([cx - dot_r, y - dot_r, cx + dot_r, y + dot_r], fill=fill)


def _draw_rtl(draw, line: str, font, fg, cx: int, y: int):
    try:
        draw.text((cx, y), line, font=font, fill=fg, direction="rtl", anchor="ma")
        return
    except Exception:
        pass
    try:
        from bidi.algorithm import get_display
        visual = get_display(line, base_dir="R")
    except Exception:
        visual = line
    bbox = draw.textbbox((0, 0), visual, font=font)
    x = ((_W - (bbox[2] - bbox[0])) // 2) - bbox[0]
    draw.text((x, y), visual, font=font, fill=fg)


def _line_height(font) -> int:
    try:
        a, d = font.getmetrics()
        return int((a + abs(d)) * 1.45)
    except Exception:
        try:
            return int(font.size * 1.5)
        except Exception:
            return 65


def _pick_font(draw, lines: list):
    for size in _FONT_SIZES:
        font = _load_font(size)
        if all(_line_fits(draw, ln, font) for ln in lines):
            return font
    return _load_font(_FONT_SIZES[-1])


def _line_fits(draw, line: str, font) -> bool:
    try:
        bbox = draw.textbbox((0, 0), line, font=font, direction="rtl")
    except Exception:
        bbox = draw.textbbox((0, 0), line, font=font)
    return (bbox[2] - bbox[0]) <= _MAX_W


def _load_font(size: int):
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _format_lines(text: str) -> list:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _simple_split(text)
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 120,
                "system": _SLIDE_FORMAT_SYSTEM,
                "messages": [{"role": "user", "content": text}],
            },
            timeout=8,
        )
        raw = resp.json()["content"][0]["text"].strip()
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        return lines[:_MAX_LINES] if lines else _simple_split(text)
    except Exception as e:
        print(f"[SLIDE IMG] format error: {repr(e)}")
        return _simple_split(text)


def _simple_split(text: str) -> list:
    words = text.split()
    if len(words) <= 5:
        return [text]
    mid = len(words) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]
