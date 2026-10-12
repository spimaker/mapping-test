import random
import datetime
import anvil.email
import anvil.users
import anvil.tables as tables
from anvil.tables import app_tables

@anvil.server.callable
def request_email_otp(email, first_name=None, last_name=None, user_name=None, mobile_phone=None):
  """Generates a 6-digit OTP code, creates or updates the user profile, and sends the code via email."""
  email = email.strip().lower()
  user = app_tables.users.get(email=email)

  # If user doesn't exist yet, create a new row with their info
  if not user:
    user = app_tables.users.add_row(
      email=email,
      enabled=True,
      first_name=first_name,
      last_name=last_name,
      user_name=user_name,
      mobile_phone=mobile_phone
    )
  else:
    # Update fields if user already exists (only update if new values were provided)
    update_dict = {}
    if first_name: update_dict['first_name'] = first_name
    if last_name: update_dict['last_name'] = last_name
    if user_name: update_dict['user_name'] = user_name
    if mobile_phone: update_dict['mobile_phone'] = mobile_phone
    if update_dict:
      user.update(**update_dict)

    # Generate random 6-digit string
  code = f"{random.randint(100000, 999999)}"
  expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

  user.update(otp_code=code, otp_expiry=expiry)

  # Send the email
  anvil.email.send(
    to=email,
    subject="Your Login Verification Code",
    text=f"Your 6-digit verification code is: {code}\nThis code will expire in 10 minutes."
  )

  return {'status': 'success', 'message': 'Verification code sent to your email!'}


@anvil.server.callable
def verify_email_otp(email, code_entered):
  """Verifies the 6-digit code and logs the user in on the server."""
  email = email.strip().lower()
  user = app_tables.users.get(email=email)

  if not user or not user['otp_code']:
    return {'status': 'error', 'message': 'No code requested for this email.'}

  if user['otp_code'] != str(code_entered).strip():
    return {'status': 'invalid', 'message': 'Incorrect verification code.'}

  if datetime.datetime.now() > user['otp_expiry']:
    return {'status': 'expired', 'message': 'Verification code has expired. Please request a new one.'}

    # Clear used OTP code
  user.update(otp_code=None, otp_expiry=None)

  # Force login session on server
  anvil.users.force_login(user)

  return {'status': 'success', 'message': 'Successfully authenticated!'}