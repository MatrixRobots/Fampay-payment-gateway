"""QR code generation for branded UPI payments."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from urllib.parse import urlencode, quote
import os

import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from qrcode.constants import ERROR_CORRECT_H

from .utils import format_amount


def build_upi_uri(*, upi_id: str, payee_name: str, amount: Decimal, purpose: str) -> str:
    """Build a UPI URI for the payment."""

    query = urlencode(
        {
            "pa": upi_id,
            "pn": payee_name,
            "am": format_amount(amount),
            "cu": "INR",
            "tn": purpose,
        },
        quote_via=quote,
    )
    return f"upi://pay?{query}"


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    x_center: int,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    fill: str = "#111111",
) -> int:
    text_width, text_height = _text_size(draw, text, font)
    x = x_center - text_width // 2
    draw.text((x, y), text, font=font, fill=fill)
    return text_height


def _draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, text: str, font: ImageFont.ImageFont) -> None:
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill="#EAF2FF", outline="#C9DAFF", width=2)
    text_width, text_height = _text_size(draw, text, font)
    draw.text((x + (width - text_width) // 2, y + (height - text_height) // 2 - 2), text, font=font, fill="#1849A9")


def generate_branded_qr(
    *,
    brand_name: str,
    payee_name: str,
    amount: Decimal,
    upi_uri: str,
    purpose: str,
    upi_id: str,
) -> bytes:
    """Generate a premium branded payment QR as PNG bytes."""

    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=14, border=4)
    qr.add_data(upi_uri)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    canvas = Image.new("RGB", (1400, 1700), "#F6F8FC")
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((110, 80, 1290, 1620), radius=54, fill=(0, 0, 0, 74))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    canvas.paste(shadow.convert("RGB"), (0, 0), shadow)

    draw = ImageDraw.Draw(canvas)
    card = (90, 60, 1310, 1600)
    draw.rounded_rectangle(card, radius=54, fill="white", outline="#E3EAF6", width=3)
    draw.rounded_rectangle((90, 60, 1310, 220), radius=54, fill="#0F4C81")
    draw.rectangle((90, 150, 1310, 220), fill="#0F4C81")

    brand_font = _load_font(56, bold=True)
    title_font = _load_font(34, bold=True)
    subtitle_font = _load_font(24, bold=False)
    body_font = _load_font(30, bold=False)
    label_font = _load_font(24, bold=True)
    small_font = _load_font(22, bold=False)

    initials = "".join(part[0] for part in brand_name.split() if part)[:3].upper() or "PS"
    _draw_badge(draw, 120, 92, 92, 56, initials, _load_font(24, bold=True))
    _draw_centered_text(draw, 700, 88, brand_name, brand_font, fill="white")
    _draw_centered_text(draw, 700, 156, "Secure UPI Payment", subtitle_font, fill="#D9E8F7")

    qr_box = (290, 290, 1110, 1110)
    draw.rounded_rectangle(qr_box, radius=40, fill="white", outline="#DCE6F4", width=4)

    qr_size = 720
    qr_image = qr_image.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    qr_x = qr_box[0] + (qr_box[2] - qr_box[0] - qr_size) // 2
    qr_y = qr_box[1] + (qr_box[3] - qr_box[1] - qr_size) // 2
    canvas.paste(qr_image, (qr_x, qr_y))

    _draw_centered_text(draw, 700, 1160, "Scan to Pay", title_font, fill="#102A43")
    _draw_centered_text(draw, 700, 1208, f"₹{format_amount(amount)}", _load_font(44, bold=True), fill="#0F4C81")
    _draw_centered_text(draw, 700, 1260, f"Payee: {payee_name}", body_font, fill="#243B53")

    details_top = 1330
    details_left = 180
    details_right = 1220
    draw.rounded_rectangle((details_left, details_top, details_right, 1515), radius=32, fill="#F8FBFF", outline="#DDE7F3", width=2)

    detail_rows = [
        ("Purpose", purpose),
        ("UPI ID", upi_id),
    ]
    row_y = details_top + 26
    for label, value in detail_rows:
        draw.text((220, row_y), f"{label}", font=label_font, fill="#5B7083")
        draw.text((390, row_y), value, font=body_font, fill="#102A43")
        row_y += 72

    footer = f"{brand_name} • {purpose}"
    footer_width, footer_height = _text_size(draw, footer, small_font)
    draw.text(((canvas.width - footer_width) // 2, 1568), footer, font=small_font, fill="#66788A")

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
