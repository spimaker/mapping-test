from datetime import datetime, timedelta, timezone
import random
import re
import anvil.email
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server


def is_valid_email(email):
  """Strict structural check for valid email formatting."""
  if not email:
    return False
  pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
  return bool(re.match(pattern, str(email).strip()))


def _find_user_by_email(email):
  """Case-insensitive lookup in app_tables.users by email."""
  target = (email or "").strip().lower()
  if not target:
    return None
  return next(
      (
          row
          for row in app_tables.users.search()
          if (row["email"] or "").strip().lower() == target
      ),
      None,
  )


def _find_user_by_username(user_name):
  """Case-insensitive lookup in app_tables.users by user_name."""
  target = (user_name or "").strip().lower()
  if not target:
    return None
  return next(
      (
          row
          for row in app_tables.users.search()
          if (row["user_name"] or "").strip().lower() == target
      ),
      None,
  )


def _generate_and_send_otp(user, email, expiry_minutes=15):
  """Generates a 6-digit OTP, stores UTC expiry, and emails the code."""
  code = f"{random.randint(100000, 999999):06d}"
  expiry = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

  user.update(otp_code=code, otp_expiry=expiry)

  anvil.email.send(
      to=email,
      from_address="naturist-map@teleweb-pub.com",
      from_name="Naturist Map",
      bcc="naturist-map@teleweb-pub.com",
      subject="Naturist Map: Your Verification Code",
      text=(
          f"Your 6-digit verification code is: {code}\n"
          f"This code will expire in {expiry_minutes} minutes."
      ),
  )

  return {
      "status": "success",
      "message": "Verification code sent to your email!",
  }


@anvil.server.callable
def register_user(
    email, user_name, first_name="", last_name="", mobile_phone=""
):
  """Validates input, enforces case-insensitive uniqueness, creates user, and sends OTP."""
  clean_email = (email or "").strip().lower()
  clean_user_name = (user_name or "").strip()

  if not clean_email or not clean_user_name:
    return {
        "status": "error",
        "message": "Email and user name are required.",
    }

  if not is_valid_email(clean_email):
    return {
        "status": "error",
        "message": (
            "Please enter a valid email address format (e.g., name@example.com)."
        ),
    }

  # 1. Case-insensitive duplicate user_name check (SPI_Maker == spi_maker == SPi_maker)
  if _find_user_by_username(clean_user_name) is not None:
    return {
        "status": "error",
        "message": (
            "That user name is already taken (usernames are not"
            " case-sensitive)."
        ),
    }

  # 2. Case-insensitive duplicate email check
  if _find_user_by_email(clean_email) is not None:
    return {
        "status": "error",
        "message": "An account with that email address already exists.",
    }

  # 3. Create new user row aligned with the users table schema
  now_utc = datetime.now(timezone.utc)
  user = app_tables.users.add_row(
      email=clean_email,
      user_name=clean_user_name,
      first_name=(first_name or "").strip(),
      last_name=(last_name or "").strip(),
      mobile_phone=(mobile_phone or "").strip(),
      confirmed_email=False,
      enabled=True,
      signed_up=now_utc,
  )

  # 4. Generate and email OTP
  return _generate_and_send_otp(user, clean_email)


@anvil.server.callable
def request_login_otp(email):
  """Validates login email, checks account status, and sends an OTP code."""
  if not email or not str(email).strip():
    return {
        "status": "error",
        "message": "Please enter your email address to log in.",
    }

  clean_email = str(email).strip().lower()

  if not is_valid_email(clean_email):
    return {
        "status": "error",
        "message": "Please enter a valid email address format.",
    }

  user = _find_user_by_email(clean_email)
  if user is None:
    return {
        "status": "error",
        "message": (
            "No account found with this email address. Please register first."
        ),
    }

  if user["enabled"] is False:
    return {
        "status": "error",
        "message": "This account is disabled.",
    }

  return _generate_and_send_otp(user, clean_email)


@anvil.server.callable
def verify_email_otp(email, code_entered=None, code=None):
  """Verifies the 6-digit OTP code, marks email confirmed, and logs the user in."""
  submitted_code = code_entered if code_entered is not None else code

  if not email or not str(email).strip():
    return {
        "status": "error",
        "is_logged_in": False,
        "message": "Email address is missing.",
    }

  clean_email = str(email).strip().lower()
  clean_code = str(submitted_code or "").strip()

  user = _find_user_by_email(clean_email)
  if user is None:
    return {
        "status": "error",
        "is_logged_in": False,
        "message": "Account not found.",
    }

  if user["enabled"] is False:
    return {
        "status": "error",
        "is_logged_in": False,
        "message": "This account is disabled.",
    }

  if not user["otp_code"]:
    return {
        "status": "error",
        "is_logged_in": False,
        "message": "No active verification request found.",
    }

  if user["otp_code"] != clean_code:
    return {
        "status": "invalid",
        "is_logged_in": False,
        "message": "Incorrect verification code.",
    }

  if user["otp_expiry"] is not None:
    now_utc = datetime.now(timezone.utc)
    expiry = user["otp_expiry"]
    if expiry.tzinfo is None:
      expiry = expiry.replace(tzinfo=timezone.utc)
    if now_utc > expiry:
      return {
          "status": "expired",
          "is_logged_in": False,
          "message": (
              "Verification code has expired. Please request a new one."
          ),
      }

  now_utc = datetime.now(timezone.utc)
  user.update(
      confirmed_email=True,
      otp_code=None,
      otp_expiry=None,
      last_login=now_utc,
  )

  anvil.server.session["logged_in_email"] = clean_email

  return {
      "status": "success",
      "is_logged_in": True,
      "message": "Successfully authenticated!",
  }


@anvil.server.callable
def get_authenticated_user():
  """Returns the authenticated user's normalized email if active, else None."""
  session_email = anvil.server.session.get("logged_in_email")
  if not session_email:
    return None

  clean_email = str(session_email).strip().lower()
  user = _find_user_by_email(clean_email)
  if user is None or user["enabled"] is False:
    clear_authenticated_user()
    return None

  return clean_email


@anvil.server.callable
def get_authenticated_user_name():
  """Returns the logged-in user's user_name from Users table, or None."""
  user_row = get_authenticated_user_row()
  if user_row is None:
    return None
  user_name = (user_row["user_name"] or "").strip()
  return user_name or None


def get_authenticated_user_row():
  """Returns the active app_tables.users row for the logged-in session, or None."""
  email = get_authenticated_user()
  if email:
    return _find_user_by_email(email)
  return anvil.users.get_user()


@anvil.server.callable
def clear_authenticated_user():
  """Clears custom session login state safely without calling .pop()."""
  try:
    if "logged_in_email" in anvil.server.session:
      del anvil.server.session["logged_in_email"]
  except Exception:
    pass
  return {"status": "success", "is_logged_in": False}


def _safe_get(row, col_name):
  """Safely reads a column/attribute/key from an Anvil Row, dict, or object."""
  if row is None:
    return None
  try:
    return row[col_name]
  except Exception:
    pass
  return getattr(row, col_name, None)


def _get_table(name):
  """Gets a table from app_tables using exact name first, then case-insensitive match."""
  tbl = getattr(app_tables, name, None)
  if tbl is not None:
    return tbl
  target = name.lower()
  for attr in dir(app_tables):
    if attr.lower() == target:
      return getattr(app_tables, attr)
  return None


def _find_row_by_user_name(table, user_name):
  """Finds a row in MapItems_Test or Map_user_lookup matching user (text)."""
  if table is None or not user_name:
    return None
  target = str(user_name).strip()
  target_lower = target.lower()

  for col in ("user", "user_name", "username"):
    try:
      row = table.get(**{col: target})
      if row is not None:
        return row
    except Exception:
      pass

    try:
      matched = next(
          (
              r
              for r in table.search()
              if str(_safe_get(r, col) or "").strip().lower() == target_lower
          ),
          None,
      )
      if matched is not None:
        return matched
    except Exception:
      continue

  return None


def _coords_from_postal_summary(postal_code):
  """Resolves (center_lat, center_lon) from Map_postal_summary by postal_code."""
  if not postal_code:
    return None, None

  code_clean = str(postal_code).strip()
  summary_tbl = _get_table("Map_postal_summary")
  if summary_tbl is None:
    return None, None

  for col in ("postal_code", "Postal_code"):
    try:
      row = summary_tbl.get(**{col: code_clean})
      if row is not None:
        lat = _safe_get(row, "center_lat")
        lon = _safe_get(row, "center_lon")
        if lat is not None and lon is not None:
          return float(lat), float(lon)
    except Exception:
      continue

  return None, None


@anvil.server.callable
def get_logged_in_user_postal_location(use_test_table=True):
  """Finds user_name from users, locates postal_code in MapItems_Test or Map_user_lookup,
  and resolves coordinates from Map_postal_summary (or MapItems_Test lat/lon)."""
  user_row = get_authenticated_user_row()
  if not user_row:
    return None

  user_name = (
      _safe_get(user_row, "user_name")
      or _safe_get(user_row, "username")
      or ""
  ).strip()
  if not user_name:
    return None

  postal_code = None
  lat = None
  lon = None

  # 1. Check MapItems_Test (or MapItems) where user column matches user_name
  items_tbl_name = "MapItems_Test" if use_test_table else "MapItems"
  items_row = _find_row_by_user_name(_get_table(items_tbl_name), user_name)
  if items_row is not None:
    raw_postal = _safe_get(items_row, "postal_code")
    if raw_postal:
      postal_code = str(raw_postal).strip()
    lat = _safe_get(items_row, "latitude")
    lon = _safe_get(items_row, "longitude")

  # 2. Check Map_user_lookup where user column matches user_name
  if not postal_code:
    lookup_row = _find_row_by_user_name(_get_table("Map_user_lookup"), user_name)
    if lookup_row is not None:
      raw_postal = _safe_get(lookup_row, "postal_code")
      if raw_postal:
        postal_code = str(raw_postal).strip()

  # 3. Resolve coordinates from Map_postal_summary using postal_code
  if postal_code and (lat is None or lon is None):
    summary_lat, summary_lon = _coords_from_postal_summary(postal_code)
    if lat is None:
      lat = summary_lat
    if lon is None:
      lon = summary_lon

  if lat is None or lon is None:
    return None

  return {
      "lat": float(lat),
      "lon": float(lon),
      "postal_code": postal_code or "My Postal Code",
  }


@anvil.server.callable
def is_email_registered(email):
  cleaned = (email or "").strip().lower()
  if not cleaned:
    return False

  users_tbl = getattr(app_tables, "users", None)
  if users_tbl is None:
    return False

  row = users_tbl.get(email=cleaned)
  if row is not None:
    return True

  for u in users_tbl.search():
    existing = (u["email"] or "").strip().lower() if "email" in u else ""
    if existing == cleaned:
      return True

  return False