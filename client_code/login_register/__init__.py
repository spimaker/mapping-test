from ._anvil_designer import login_registerTemplate
import anvil.server
from anvil import *

class login_register(login_registerTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)

    # Stage tracking: 'request' or 'verify'
    self.stage = 'request'
    self.user_email = ""
    self.update_stage_ui()

    # Set background color of restricted fields
    self.mobile_phone_value.role = 'highlight-bg'

  def update_stage_ui(self):
    """Toggles visible inputs depending on stage."""
    if self.stage == 'request':
      self.Title_Label.text = "Sign In with Email Code"
      self.Email_Box.visible = True
      self.Code_Box.visible = False if hasattr(self, 'Code_Box') else None
      self.Submit_Button.text = "Send 6-Digit Code"
    else:
      self.Title_Label.text = f"Enter Code sent to {self.user_email}"
      self.Email_Box.visible = False
      if hasattr(self, 'Code_Box'):
        self.Code_Box.visible = True
      self.Submit_Button.text = "Verify & Log In"

  @anvil.handle("Submit_Button", "click")
  def submit_button_click(self, **event_args):
    """Handles both sending the OTP code and verifying it."""
    try:
      if self.stage == 'request':
        email = self.Email_Box.text.strip()
        if not email:
          anvil.alert("Please enter a valid email address.", title="Missing Email")
          return

        # Call server to send OTP email
        res = anvil.server.call('request_email_otp', email)
        if res['status'] == 'success':
          self.user_email = email
          self.stage = 'verify'
          self.update_stage_ui()
          anvil.Notification("6-digit code sent! Check your inbox.").show()
        else:
          anvil.alert(res['message'])

      elif self.stage == 'verify':
        code = self.Code_Box.text.strip() if hasattr(self, 'Code_Box') else ""
        if not code:
          anvil.alert("Please enter the 6-digit code.", title="Missing Code")
          return

        # Call server to verify OTP code
        res = anvil.server.call('verify_email_otp', self.user_email, code)
        if res['status'] == 'success':
          anvil.Notification("Logged in successfully!").show()
          open_form('Form1') # Proceed to map form
        else:
          anvil.alert(res['message'], title="Login Failed")

    except Exception as e:
      anvil.alert(f"An error occurred: {e}")