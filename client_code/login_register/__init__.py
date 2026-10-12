from ._anvil_designer import login_registerTemplate
import anvil.server
from anvil import *

class login_register(login_registerTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

    # Programmatically assign your custom CSS role
    self.first_name_value.role = "highlight-bg"
    self.last_name_value.role = "highlight-bg"
    self.mobile_phone_value.role = "highlight-bg"

    # Set your message label foreground color here
    self.message_label.foreground = "#d9779c"

    self.active_email = ""
    self.show_entry_screens()

  def show_entry_screens(self):
    """Shows registration and login sections; hides code verification section."""
    # Registration Section Visible
    self.email_value.visible = True
    self.user_name_value.visible = True
    self.first_name_value.visible = True
    self.last_name_value.visible = True
    self.mobile_phone_value.visible = True
    self.submit_registration_button.visible = True

    # Login Section Visible (Make sure this matches your component name, e.g., login_email_value)
    if hasattr(self, 'login_email_value'):
      self.login_email_value.visible = True
    self.submit_login_button.visible = True

    # Code Verification Section Hidden
    if hasattr(self, 'code_value_label'): self.code_value_label.visible = False
    if hasattr(self, 'code_value'): self.code_value.visible = False
    if hasattr(self, 'submit_code_button'): self.submit_code_button.visible = False

  def show_verification_screen(self, email):
    """Hides entry sections; shows ONLY the 6-digit code verification components."""
    self.active_email = email

    # Registration Section Hidden
    self.email_value.visible = False
    self.user_name_value.visible = False
    self.first_name_value.visible = False
    self.last_name_value.visible = False
    self.mobile_phone_value.visible = False
    self.submit_registration_button.visible = False

    # Login Section Hidden
    if hasattr(self, 'login_email_value'):
      self.login_email_value.visible = False
    self.submit_login_button.visible = False

    # Code Verification Section Visible
    if hasattr(self, 'code_value_label'):
      self.code_value_label.visible = True
      self.code_value_label.text = f"Enter the 6-digit code sent to {email}:"

    if hasattr(self, 'code_value'): 
      self.code_value.visible = True
      self.code_value.text = ""

    if hasattr(self, 'submit_code_button'): 
      self.submit_code_button.visible = True

  @anvil.handle("submit_registration_button", "click")
  def submit_registration_button_click(self, **event_args):
    """Handles new user registration submission."""
    email = self.email_value.text.strip() if self.email_value.text else ""
    user_name = self.user_name_value.text.strip() if self.user_name_value.text else ""
    first_name = self.first_name_value.text.strip() if self.first_name_value.text else ""
    last_name = self.last_name_value.text.strip() if self.last_name_value.text else ""
    mobile_phone = self.mobile_phone_value.text.strip() if self.mobile_phone_value.text else ""

    if not email or not user_name:
      anvil.alert("Email and Username are required for registration.", title="Missing Information")
      return

    try:
      res = anvil.server.call('register_user', email, user_name, first_name, last_name, mobile_phone)
      if res['status'] == 'success':
        anvil.Notification("Registration successful! Check your email for the code.").show()
        self.show_verification_screen(email)
      else:
        anvil.alert(res['message'], title="Registration Failed")
    except Exception as e:
      anvil.alert(f"An error occurred: {e}")

  @anvil.handle("submit_login_button", "click")
  def submit_login_button_click(self, **event_args):
    """Handles login submission for existing users using login_email_value."""
    # Fallback check in case the component is named login_email_value vs email_value
    target_box = self.login_email_value if hasattr(self, 'login_email_value') else getattr(self, 'email_value', None)
    email = target_box.text.strip() if target_box and target_box.text else ""

    if not email:
      anvil.alert("Please enter your email address.", title="Missing Email")
      return

    try:
      res = anvil.server.call('request_login_otp', email)
      if res['status'] == 'success':
        anvil.Notification("Login code sent! Check your email.").show()
        self.show_verification_screen(email)
      else:
        anvil.alert(res['message'], title="Login Failed")
    except Exception as e:
      anvil.alert(f"An error occurred: {e}")

  @anvil.handle("submit_code_button", "click")
  def submit_code_button_click(self, **event_args):
    """Handles verification of the 6-digit code."""
    code = self.code_value.text.strip() if hasattr(self, 'code_value') and self.code_value.text else ""

    if not code:
      anvil.alert("Please enter the 6-digit verification code.", title="Missing Code")
      return

    try:
      res = anvil.server.call('verify_email_otp', self.active_email, code)
      if res['status'] == 'success':
        anvil.Notification("Successfully authenticated!").show()
        open_form('Form1') # Transition to map form
      else:
        anvil.alert(res['message'], title="Verification Failed")
    except Exception as e:
      anvil.alert(f"An error occurred: {e}")