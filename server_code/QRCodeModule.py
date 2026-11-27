import io
from urllib.parse import quote
import qrcode
from PIL import Image, ImageDraw, ImageFont
import anvil.server
import anvil.users
from anvil.tables import app_tables


def _get_session_user_row():
    """Attempt to read the authenticated user row from mapusermodule if available."""
    for import_path in ("..mapusermodule", "...mapusermodule", "mapusermodule"):
        try:
            if import_path == "..mapusermodule":
                from .. import mapusermodule
            elif import_path == "...mapusermodule":
                from ... import mapusermodule
            else:
                import mapusermodule

            if hasattr(mapusermodule, "get_authenticated_user_row"):
                row = mapusermodule.get_authenticated_user_row()
                if row is not None:
                    return row
            if hasattr(mapusermodule, "get_authenticated_user_name"):
                name = mapusermodule.get_authenticated_user_name()
                if name:
                    return {"user_name": name}
        except Exception:
            continue
    return None


def _extract_username_from_record(record) -> str | None:
    """Extract a non-empty username from an Anvil Row or mapping."""
    if not record:
        return None

    for field in ("user_name", "username", "handle"):
        try:
            val = record[field]
            if val and str(val).strip():
                return str(val).strip()
        except (KeyError, TypeError):
            continue

    try:
        email = record["email"]
        if email and "@" in str(email):
            return str(email).split("@", 1)[0].strip()
    except (KeyError, TypeError):
        pass

    return None


def _resolve_username(username: str | None = None) -> str:
    """Resolve the target username from an explicit argument, session, or Anvil user."""
    if username and str(username).strip():
        return str(username).strip()

    session_record = _get_session_user_row()
    session_username = _extract_username_from_record(session_record)
    if session_username:
        return session_username

    user = anvil.users.get_user()
    if not user:
        raise ValueError("No logged-in user found. Please log in before generating a QR code.")

    anvil_username = _extract_username_from_record(user)
    if anvil_username:
        return anvil_username

    raise ValueError("Logged-in user record does not have a username.")


def _get_user_profile_table():
    """Locate User_profile table regardless of casing."""
    tbl = getattr(app_tables, "User_profile", None)
    if tbl is not None:
        return tbl
    for attr in dir(app_tables):
        if attr.lower() == "user_profile":
            return getattr(app_tables, attr)
    return None


def _get_qr_media_from_row(row):
    """Read saved QR media from a User_profile row across column name variations."""
    if row is None:
        return None
    for col in ("qr_code", "QR_code"):
        try:
            val = row[col]
            if val is not None:
                return val
        except Exception:
            continue
    return None


def _find_user_profile_row(user_name: str):
    """Find the User_profile row for user_name (case-insensitive)."""
    clean_user = (user_name or "").strip()
    if not clean_user:
        return None

    profile_tbl = _get_user_profile_table()
    if profile_tbl is None:
        return None

    try:
        row = profile_tbl.get(user=clean_user)
        if row is not None:
            return row
    except Exception:
        pass

    target_lower = clean_user.lower()
    try:
        return next(
            (
                r
                for r in profile_tbl.search()
                if str(r["user"] or "").strip().lower() == target_lower
            ),
            None,
        )
    except Exception:
        return None


def _save_qr_to_user_profile(user_name: str, qr_media: anvil.BlobMedia):
    """Save generated QR Media into User_profile.qr_code for user_name."""
    clean_user = (user_name or "").strip()
    if not clean_user:
        return

    for import_path in ("..MapUserModule", "...MapUserModule", "MapUserModule"):
        try:
            if import_path == "..MapUserModule":
                from .. import MapUserModule
            elif import_path == "...MapUserModule":
                from ... import MapUserModule
            else:
                import MapUserModule

            if hasattr(MapUserModule, "save_user_qr_code"):
                MapUserModule.save_user_qr_code(clean_user, qr_media)
                return
        except Exception:
            continue

    profile_tbl = _get_user_profile_table()
    if profile_tbl is None:
        return

    row = _find_user_profile_row(clean_user)
    if row is None:
        profile_tbl.add_row(user=clean_user, qr_code=qr_media)
    else:
        row.update(qr_code=qr_media)


@anvil.server.callable
def get_user_qr_media(username: str | None = None):
    """Return the saved qr_code Media from User_profile for username/session user, or None."""
    try:
        resolved_user = _resolve_username(username)
    except Exception:
        return None

    row = _find_user_profile_row(resolved_user)
    return _get_qr_media_from_row(row)


def _normalize_lines(text_value) -> list[str]:
    """Convert a string with optional newlines or a sequence of lines into clean lines."""
    if text_value is None:
        return []
    if isinstance(text_value, (list, tuple)):
        raw_lines = []
        for item in text_value:
            if item is not None:
                raw_lines.extend(str(item).splitlines())
    else:
        raw_lines = str(text_value).splitlines()

    return [line.strip() for line in raw_lines if line and line.strip()]


def _band_height(lines: list[str], font_size: int) -> int:
    """Calculate pixel height for a header or footer text band."""
    if not lines:
        return 0
    line_spacing = max(8, int(font_size * 0.25))
    single_line_h = int(font_size * 1.25)
    total_lines_h = len(lines) * single_line_h + (len(lines) - 1) * line_spacing
    return total_lines_h + 36


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


@anvil.server.callable
def generate_user_qr_media(
    username: str | None = None,
    top_text: str | None = None,
    bottom_text: str | None = None,
    logo_media: anvil.Media | None = None,
    qr_size: int = 600,
    logo_ratio: float = 0.22,
    font_size: int = 44,
) -> anvil.BlobMedia:
    """
    Generate a QR code pointing to http://naturist.map/public_profiles/<username>
    for the logged-in user (or a specified username), save it to User_profile.qr_code,
    and return an Anvil BlobMedia PNG.
    """
    resolved_user = _resolve_username(username)
    encoded_user = quote(resolved_user, safe="")
    url = f"http://naturist.map/public_profiles/{encoded_user}"

    raw_top = top_text if top_text is not None else "Join me on\nthe Map"
    raw_bottom = bottom_text if bottom_text is not None else "Naturist Map"

    top_lines = _normalize_lines(raw_top)
    bottom_lines = _normalize_lines(raw_bottom)

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

    header_height = _band_height(top_lines, font_size)
    footer_height = _band_height(bottom_lines, font_size)
    total_height = qr_size + header_height + footer_height

    canvas = Image.new("RGBA", (qr_size, total_height), "white")
    canvas.paste(qr_img, (0, header_height))

    if top_lines or bottom_lines:
        draw = ImageDraw.Draw(canvas)

        def draw_centered_lines(lines: list[str], band_top: int, band_h: int):
            if not lines or band_h <= 0:
                return

            line_spacing = max(8, int(font_size * 0.25))
            measured = []
            total_block_h = 0

            for line in lines:
                current_size = int(font_size)
                current_font = _load_font(current_size)
                bbox = draw.textbbox((0, 0), line, font=current_font)
                text_w = bbox[2] - bbox[0]

                while text_w > (qr_size - 40) and current_size > 14:
                    current_size -= 2
                    current_font = _load_font(current_size)
                    bbox = draw.textbbox((0, 0), line, font=current_font)
                    text_w = bbox[2] - bbox[0]

                text_h = bbox[3] - bbox[1]
                measured.append((line, current_font, text_w, text_h, bbox[0], bbox[1]))
                total_block_h += text_h

            total_block_h += line_spacing * (len(measured) - 1)
            cursor_y = band_top + max(0, (band_h - total_block_h) // 2)

            for line, line_font, text_w, text_h, off_x, off_y in measured:
                x = ((qr_size - text_w) // 2) - off_x
                y = cursor_y - off_y
                draw.text((x, y), line, fill="black", font=line_font)
                cursor_y += text_h + line_spacing

        if top_lines:
            draw_centered_lines(top_lines, 0, header_height)
        if bottom_lines:
            draw_centered_lines(bottom_lines, header_height + qr_size, footer_height)

    out_buf = io.BytesIO()
    canvas.convert("RGB").save(out_buf, format="PNG")
    out_buf.seek(0)

    qr_media = anvil.BlobMedia(
        "image/png", out_buf.getvalue(), name=f"qr_{resolved_user}.png"
    )
    _save_qr_to_user_profile(resolved_user, qr_media)
    return qr_media