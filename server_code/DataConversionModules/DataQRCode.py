import io
from urllib.parse import quote
import qrcode
from PIL import Image, ImageDraw, ImageFont
import anvil.server
import anvil.users


def _resolve_username(username: str | None = None) -> str:
    """Resolve the target username from an explicit argument or the logged-in user."""
    if username and str(username).strip():
        return str(username).strip()

    user = anvil.users.get_user()
    if not user:
        raise ValueError("No logged-in user found. Please log in before generating a QR code.")

    for field in ("username", "user_name", "handle"):
        try:
            val = user[field]
            if val and str(val).strip():
                return str(val).strip()
        except (KeyError, TypeError):
            continue

    try:
        email = user["email"]
        if email and "@" in str(email):
            return str(email).split("@", 1)[0].strip()
    except (KeyError, TypeError):
        pass

    raise ValueError("Logged-in user record does not have a username.")


@anvil.server.callable
def generate_user_qr_media(
    username: str | None = None,
    top_text: str | None = None,
    bottom_text: str | None = None,
    logo_media: anvil.Media | None = None,
    qr_size: int = 600,
    logo_ratio: float = 0.22,
    font_size: int = 32,
) -> anvil.BlobMedia:
    """
    Generate a QR code pointing to http://naturist.map/<username> for the
    logged-in user (or a specified username), returning an Anvil BlobMedia PNG.
    """
    resolved_user = _resolve_username(username)
    encoded_user = quote(resolved_user, safe="")
    url = f"http://naturist.map/{encoded_user}"

    effective_top = top_text if top_text is not None else "SCAN PROFILE"
    effective_bottom = bottom_text if bottom_text is not None else resolved_user

    has_logo = logo_media is not None
    error_level = (
        qrcode.constants.ERROR_CORRECT_H if has_logo else qrcode.constants.ERROR_CORRECT_M
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=error_level,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    resample_mode = Image.Resampling.LANCZOS if has_logo else Image.Resampling.NEAREST
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    qr_img = qr_img.resize((qr_size, qr_size), resample_mode)

    if has_logo:
        logo_bytes = io.BytesIO(logo_media.get_bytes())
        logo = Image.open(logo_bytes).convert("RGBA")

        safe_ratio = max(0.10, min(0.30, float(logo_ratio)))
        max_logo_dim = int(qr_size * safe_ratio)
        logo.thumbnail((max_logo_dim, max_logo_dim), Image.Resampling.LANCZOS)

        pad = 8
        logo_bg = Image.new(
            "RGBA", (logo.width + pad * 2, logo.height + pad * 2), "white"
        )
        logo_bg.paste(logo, (pad, pad), mask=logo)

        logo_pos = (
            (qr_size - logo_bg.width) // 2,
            (qr_size - logo_bg.height) // 2,
        )
        qr_img.paste(logo_bg, logo_pos, mask=logo_bg)

    header_height = (font_size + 44) if effective_top else 0
    footer_height = (font_size + 44) if effective_bottom else 0
    total_height = qr_size + header_height + footer_height

    canvas = Image.new("RGBA", (qr_size, total_height), "white")
    canvas.paste(qr_img, (0, header_height))

    if effective_top or effective_bottom:
        draw = ImageDraw.Draw(canvas)
        font = _load_font(font_size)

        def draw_centered_text(text: str, y_center: int):
            if not text:
                return
            current_font = font
            bbox = draw.textbbox((0, 0), text, font=current_font)
            text_w = bbox[2] - bbox[0]

            current_size = font_size
            while text_w > (qr_size - 40) and current_size > 12:
                current_size -= 2
                current_font = _load_font(current_size)
                bbox = draw.textbbox((0, 0), text, font=current_font)
                text_w = bbox[2] - bbox[0]

            text_h = bbox[3] - bbox[1]
            x = (qr_size - text_w) // 2
            y = y_center - (text_h // 2)
            draw.text((x, y), text, fill="black", font=current_font)

        if effective_top:
            draw_centered_text(effective_top, header_height // 2)
        if effective_bottom:
            draw_centered_text(
                effective_bottom, header_height + qr_size + (footer_height // 2)
            )

    out_buf = io.BytesIO()
    canvas.convert("RGB").save(out_buf, format="PNG")
    out_buf.seek(0)

    return anvil.BlobMedia("image/png", out_buf.getvalue(), name=f"qr_{resolved_user}.png")


def _load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()