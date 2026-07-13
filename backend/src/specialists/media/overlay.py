import base64
import io
import os
from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def add_text_overlay(image_b64: str, text: str) -> str:
    image_bytes = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    W, H = img.size

    font_size = max(36, H // 16)
    font = _load_font(font_size)

    # Reorder Hebrew/RTL text to visual order for Pillow
    display_text = get_display(text, base_dir="R")

    tmp_draw = ImageDraw.Draw(img)
    bbox = tmp_draw.textbbox((0, 0), display_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    padding_x = 32
    padding_y = 18
    x = max(padding_x, (W - text_w) / 2)
    y = H * 0.72 - text_h / 2

    # Semi-transparent black band behind text
    band = Image.new("RGBA", img.size, (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band)
    band_draw.rectangle(
        [0, y - padding_y, W, y + text_h + padding_y],
        fill=(0, 0, 0, 150),
    )
    img = Image.alpha_composite(img, band)

    draw = ImageDraw.Draw(img)
    # Shadow
    draw.text((x + 2, y + 2), display_text, font=font, fill=(0, 0, 0, 200))
    # White text
    draw.text((x, y), display_text, font=font, fill=(255, 255, 255, 255))

    result = img.convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
