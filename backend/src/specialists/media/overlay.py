import base64
import io
import os
import uuid
import requests as req
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from bidi.algorithm import get_display

STORY_W, STORY_H = 1080, 1920

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


def _load_font(size):
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _open_from_url(url):
    res = req.get(url, timeout=20)
    res.raise_for_status()
    return Image.open(io.BytesIO(res.content)).convert("RGB")


def _fit_to_story_canvas(img):
    """Scale image into 9:16 canvas with blurred background fill."""
    iw, ih = img.size
    img_ratio = iw / ih
    canvas_ratio = STORY_W / STORY_H

    if img_ratio > canvas_ratio:
        new_w = STORY_W
        new_h = int(new_w / img_ratio)
    else:
        new_h = STORY_H
        new_w = int(new_h * img_ratio)

    main = img.resize((new_w, new_h), Image.LANCZOS)

    bg = img.resize((STORY_W, STORY_H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=28))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)

    x = (STORY_W - new_w) // 2
    y = (STORY_H - new_h) // 2
    bg.paste(main, (x, y))
    return bg


def _smart_text_position(img):
    """Return 'top' or 'bottom' — whichever region is least visually busy."""
    sample = img.convert("L").resize((80, 142))
    W, H = sample.size
    zone = H // 5

    def variance(pixels):
        if len(pixels) < 2:
            return 0
        avg = sum(pixels) / len(pixels)
        return sum((p - avg) ** 2 for p in pixels) / len(pixels)

    top = list(sample.crop((0, 0, W, zone)).getdata())
    bottom = list(sample.crop((0, H - zone, W, H)).getdata())
    return "top" if variance(top) < variance(bottom) else "bottom"


def _wrap_text(draw, text, font, max_width):
    """Break text into lines that fit within max_width."""
    words = text.split()
    if not words:
        return [text]
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [text]


def _apply_filter(img, filter_name):
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


def _add_text(img, text, position=None):
    """Add text with auto word-wrap, smart positioning, and dark band."""
    rgba = img.convert("RGBA")
    W, H = rgba.size

    if position is None:
        position = _smart_text_position(img)

    font_size = max(52, H // 22)
    font = _load_font(font_size)
    max_text_w = int(W * 0.82)
    display_text = get_display(text, base_dir="R")

    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines = _wrap_text(tmp, display_text, font, max_text_w)

    line_h = font_size + 14
    total_h = len(lines) * line_h
    pad_x, pad_y = 40, 28

    if position == "top":
        y_start = int(H * 0.07)
    elif position == "center":
        y_start = (H - total_h) // 2
    else:
        y_start = int(H * 0.80) - total_h // 2

    band = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle(
        [0, y_start - pad_y, W, y_start + total_h + pad_y],
        fill=(0, 0, 0, 165),
    )
    rgba = Image.alpha_composite(rgba, band)

    draw = ImageDraw.Draw(rgba)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (W - lw) / 2
        y = y_start + i * line_h
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 185))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    return rgba


def _apply_story_watermark(img, brand_name):
    """Subtle brand name in bottom-right corner."""
    rgba = img.convert("RGBA")
    W, H = rgba.size
    font_size = max(28, W // 28)
    font = _load_font(font_size)
    display_name = get_display(brand_name, base_dir="R")

    draw = ImageDraw.Draw(rgba)
    bbox = draw.textbbox((0, 0), display_name, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = W - tw - 40
    y = H - th - 60

    draw.text((x + 1, y + 1), display_name, font=font, fill=(0, 0, 0, 110))
    draw.text((x, y), display_name, font=font, fill=(255, 255, 255, 170))
    return rgba


def _apply_brand_frame(img, brand_name=None):
    """White polaroid-style frame (for feed posts, not stories)."""
    W, H = img.size
    side = max(14, W // 55)
    bottom = max(64, H // 13) if brand_name else side
    framed = Image.new("RGB", (W + side * 2, H + side + bottom), (255, 255, 255))
    framed.paste(img, (side, side))
    if brand_name:
        font_size = max(20, bottom // 2)
        font = _load_font(font_size)
        draw = ImageDraw.Draw(framed)
        display_name = get_display(brand_name, base_dir="R")
        bbox = draw.textbbox((0, 0), display_name, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (framed.width - tw) / 2
        y = H + side + (bottom - th) / 2
        draw.text((x + 1, y + 1), display_name, font=font, fill=(210, 210, 210))
        draw.text((x, y), display_name, font=font, fill=(90, 90, 90))
    return framed


def compose_story(image_url, caption=None, filter_name=None,
                  brand_frame=False, brand_name=None):
    img = _open_from_url(image_url).convert("RGB")

    # Always produce a 9:16 canvas
    img = _fit_to_story_canvas(img)

    if filter_name and filter_name != "none":
        img = _apply_filter(img, filter_name)

    if brand_frame and brand_name:
        img = _apply_story_watermark(img, brand_name).convert("RGB")

    if caption:
        img = _add_text(img, caption)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def upload_composed(image_bytes):
    from src.db.storage import upload_image
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return upload_image(b64, "image/jpeg", f"story_edit_{uuid.uuid4().hex[:10]}")
