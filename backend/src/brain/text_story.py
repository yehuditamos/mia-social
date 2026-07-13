import io
import uuid
import base64
from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display

_W, _H = 1080, 1920
_MAX_W = int(_W * 0.82)
_FONT_SIZES = [120, 100, 80, 64, 50]
_MAX_LINES = 7
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def create_text_story_image(text: str, bg_color: str = "black") -> bytes:
    is_dark = any(w in bg_color.lower() for w in {"שחור", "black", "dark"})
    bg = (0, 0, 0) if is_dark else (255, 255, 255)
    fg = (255, 255, 255) if is_dark else (0, 0, 0)

    img = Image.new("RGB", (_W, _H), color=bg)
    draw = ImageDraw.Draw(img)

    font, lines = _pick_font_and_lines(draw, text)

    try:
        line_h = int(font.size * 1.45)
    except Exception:
        line_h = 40

    total_h = max(1, len(lines)) * line_h
    y = (_H - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (_W - max(0, bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, fill=fg, font=font)
        y += line_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_and_upload(text: str, bg_color: str) -> str:
    from src.db.storage import upload_image

    img_bytes = create_text_story_image(text, bg_color)
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    filename = f"text_story_{uuid.uuid4().hex[:10]}"
    return upload_image(img_b64, "image/png", filename)


def _load_font(size: int):
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _build_lines(draw, text: str, font, max_width: int) -> list:
    words = text.split()
    lines = []
    current = []

    for word in words:
        test_display = get_display(" ".join(current + [word]))
        bbox = draw.textbbox((0, 0), test_display, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(get_display(" ".join(current)))
            current = [word]

    if current:
        lines.append(get_display(" ".join(current)))

    return lines or [get_display(text)]


def _pick_font_and_lines(draw, text: str):
    for size in _FONT_SIZES:
        font = _load_font(size)
        lines = _build_lines(draw, text, font, _MAX_W)
        if len(lines) <= _MAX_LINES:
            return font, lines

    font = _load_font(_FONT_SIZES[-1])
    return font, _build_lines(draw, text, font, _MAX_W)
