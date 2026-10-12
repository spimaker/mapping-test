import random
import datetime
import anvil.email
import anvil.users
import anvil.tables as tables
from anvil.tables import app_tables

@anvil.server.callable
def register_user(email, user_name, first_name, last_name, mobile_phone):
  """Validates uniqueness, creates user record, and sends initial OTP code."""
  email = email.strip().lower()
  user_name = user_name.strip()

  # Check if email already exists
  if app_tables.users.get(email=email):
    return {'status': 'error', 'message': 'An account with this email address already exists.'}

    # Check if username already exists
  if app_tables.users.get(user_name=user_name):
    return {'status': 'error', 'message': 'This username is already taken. Please choose another.'}

    # Create new user row
  user = app_tables.users.add_row(
    email=email,
    user_name=user_name,
    first_name=first_name,
    last_name=last_name,
    mobile_phone=mobile_phone,
    enabled=True
  )

  # Generate and send OTP
  return _generate_and_send_otp(user, email)


@anvil.server.callable
def request_login_otp(email):
  """Checks if user exists, then sends an OTP code for login."""
  email = email.strip().lower()
  user = app_tables.users.get(email=email)

  if not user:
    return {'status': 'error', 'message': 'No account found with this email address. Please register first.'}

  return _generate_and_send_otp(user, email)


import random
import datetime
import anvil.email
import anvil.users
import anvil.tables as tables
from anvil.tables import app_tables

def _generate_and_send_otp(user, email):
  """Helper to generate code, set timezone-aware expiration, and email the user."""
  code = f"{random.randint(100000, 999999)}"

  # Use timezone-aware UTC datetime so it matches Anvil data tables
  expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)

  user.update(otp_code=code, otp_expiry=expiry)

  anvil.email.send(
    to=email,
    from_address="Naturist-Map@teleweb-pub.com",
    from_name="Naturist Map",
    subject="Naturist Map: Your Verification Code",
    text=f"Your 6-digit verification code is: {code}\nThis code will expire in 10 minutes."
  )

  return {'status': 'success', 'message': 'Verification code sent to your email!'}


@anvil.server.callable
def verify_email_otp(email, code_entered):
  """Verifies the 6-digit code and logs the user in."""
  email = email.strip().lower()
  user = app_tables.users.get(email=email)

  if not user or not user['otp_code']:
    return {'status': 'error', 'message': 'No active verification request found.'}

  if user['otp_code'] != str(code_entered).strip():
    return {'status': 'invalid', 'message': 'Incorrect verification code.'}

    # Compare using timezone-aware UTC current time
  current_time = datetime.datetime.now(datetime.timezone.utc)
  if current_time > user['otp_expiry']:
    return {'status': 'expired', 'message': 'Verification code has expired. Please request a new one.'}

    # Clear code and force login session
  user.update(otp_code=None, otp_expiry=None)
  anvil.users.force_login(user)

  return {'status': 'success', 'message': 'Successfully authenticated!'}