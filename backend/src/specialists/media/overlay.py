import base64
import io
import os
import uuid
import requests as req
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from bidi.algorithm import get_display

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
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


def _open_from_url(url: str) -> Image.Image:
    res = req.get(url, timeout=20)
    res.raise_for_status()
    return Image.open(io.BytesIO(res.content)).convert("RGB")


def _apply_filter(img: Image.Image, filter_name: str) -> Image.Image:
    if filter_name == "warm":
        r, g, b = img.split()
        r = r.point(lambda x: min(255, int(x * 1.1 + 12)))
        b = b.point(lambda x: max(0, int(x * 0.82)))
        img = Image.merge("RGB", (r, g, b))
        img = ImageEnhance.Color(img).enhance(1.25)
        img = ImageEnhance.Contrast(img).enhance(1.06)

    elif filter_name == "cool":
        r, g, b = img.split()
        r = r.point(lambda x: max(0, int(x * 0.88)))
        b = b.point(lambda x: min(255, int(x * 1.15 + 10)))
        img = Image.merge("RGB", (r, g, b))
        img = ImageEnhance.Color(img).enhance(1.15)

    elif filter_name == "bw":
        img = img.convert("L").convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Brightness(img).enhance(1.04)

    elif filter_name == "vintage":
        img = ImageEnhance.Color(img).enhance(0.5)
        img = ImageEnhance.Brightness(img).enhance(1.06)
        r, g, b = img.split()
        r = r.point(lambda x: min(255, int(x * 1.08 + 8)))
        b = b.point(lambda x: max(0, int(x * 0.84)))
        img = Image.merge("RGB", (r, g, b))
        img = ImageEnhance.Contrast(img).enhance(0.88)

    return img


def _apply_brand_frame(img: Image.Image, brand_name: str = None) -> Image.Image:
    W, H = img.size
    side = max(14, W // 55)
    top = side
    bottom = max(64, H // 13) if brand_name else side

    framed = Image.new("RGB", (W + side * 2, H + top + bottom), (255, 255, 255))
    framed.paste(img, (side, top))

    if brand_name:
        font_size = max(20, bottom // 2)
        font = _load_font(font_size)
        draw = ImageDraw.Draw(framed)
        display_name = get_display(brand_name, base_dir="R")
        bbox = draw.textbbox((0, 0), display_name, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (framed.width - tw) / 2
        y = H + top + (bottom - th) / 2
        draw.text((x + 1, y + 1), display_name, font=font, fill=(210, 210, 210))
        draw.text((x, y), display_name, font=font, fill=(90, 90, 90))

    return framed


def _add_text(img: Image.Image, text: str) -> Image.Image:
    rgba = img.convert("RGBA")
    W, H = rgba.size
    font_size = max(38, H // 15)
    font = _load_font(font_size)
    display_text = get_display(text, base_dir="R")

    tmp = ImageDraw.Draw(rgba)
    bbox = tmp.textbbox((0, 0), display_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    pad_x, pad_y = 36, 20
    x = max(pad_x, (W - tw) / 2)
    y = H * 0.73 - th / 2

    band = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle([0, y - pad_y, W, y + th + pad_y], fill=(0, 0, 0, 155))
    rgba = Image.alpha_composite(rgba, band)

    draw = ImageDraw.Draw(rgba)
    draw.text((x + 2, y + 2), display_text, font=font, fill=(0, 0, 0, 190))
    draw.text((x, y), display_text, font=font, fill=(255, 255, 255, 255))

    return rgba


def compose_story(image_url: str, caption: str = None,
                  filter_name: str = None, brand_frame: bool = False,
                  brand_name: str = None) -> bytes:
    img = _open_from_url(image_url)

    if filter_name and filter_name != "none":
        img = _apply_filter(img, filter_name)

    if brand_frame:
        img = _apply_brand_frame(img, brand_name)

    if caption:
        img = _add_text(img, caption)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def upload_composed(image_bytes: bytes) -> str:
    from src.db.storage import upload_image
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return upload_image(b64, "image/jpeg", f"story_edit_{uuid.uuid4().hex[:10]}")
