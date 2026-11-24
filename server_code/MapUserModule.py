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
def clear_authenticated_user():
  """Clears custom session login state safely without calling .pop()."""
  try:
    if "logged_in_email" in anvil.server.session:
      del anvil.server.session["logged_in_email"]
  except Exception:
    pass
  return {"status": "success", "is_logged_in": False}