from ._anvil_designer import Login_registerTemplate
import anvil.js
import anvil.server
from anvil import *

try:
  from ...Layouts.NavLayout import get_active_nav_layout
except Exception:
  get_active_nav_layout = None


class Login_register(Login_registerTemplate):

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

  def _set_code_value_error_outline(self, is_error=True):
    """Applies or clears a high-priority red outline on code_value."""
    if not hasattr(self, "code_value"):
      return
    try:
      dom_node = anvil.js.get_dom_node(self.code_value)
      target = dom_node.querySelector("input, textarea") or dom_node
      if is_error:
        target.style.setProperty("border", "2px solid #d93025", "important")
        target.style.setProperty("outline", "1px solid #d93025", "important")
        target.style.setProperty("border-radius", "4px", "important")
      else:
        target.style.removeProperty("border")
        target.style.removeProperty("outline")
        target.style.removeProperty("border-radius")
    except Exception as e:
      print(f"Could not update code_value outline: {e}")

  def _schedule_code_value_outline(self, is_error=True):
    """Applies or clears the red outline slightly after visibility updates in DOM."""
    if not hasattr(self, "code_value"):
      return
    if not is_error:
      self._set_code_value_error_outline(False)
      return

    def _apply():
      self._set_code_value_error_outline(True)

    try:
      anvil.js.window.setTimeout(_apply, 50)
    except Exception:
      self._set_code_value_error_outline(True)

  def _clear_registration_form(self):
    """Clears registration fields after a duplicate email check."""
    for attr in (
        "email_value",
        "user_name_value",
        "first_name_value",
        "last_name_value",
        "mobile_phone_value",
    ):
      comp = getattr(self, attr, None)
      if comp is not None and hasattr(comp, "text"):
        comp.text = ""

  def _check_email_already_registered(self, **event_args):
    """Checks if email_value is already registered; clears form and alerts if so."""
    email = (
        self.email_value.text.strip()
        if hasattr(self, "email_value") and self.email_value.text
        else ""
    )
    if not email or "@" not in email:
      return

    try:
      already_exists = anvil.server.call("is_email_registered", email)
      if already_exists:
        self._clear_registration_form()
        anvil.alert(
            f"{email} is already registered. Please log in instead.",
            title="Email Already Registered",
        )
        if hasattr(self, "login_email_value"):
          self.login_email_value.text = email
          self.login_email_value.focus()
    except Exception as e:
      print(f"Could not check email registration: {e}")

  @anvil.handle("email_value", "lost_focus")
  def email_value_lost_focus(self, **event_args):
    self._check_email_already_registered(**event_args)

  @anvil.handle("email_value", "pressed_enter")
  def email_value_pressed_enter(self, **event_args):
    self._check_email_already_registered(**event_args)

  def code_value_change(self, **event_args):
    self._set_code_value_error_outline(False)

  def verify_code_button_click(self, **event_args):
    code_entered = (
        self.code_value.text.strip()
        if hasattr(self, "code_value") and self.code_value.text
        else ""
    )
    if not code_entered:
      self._set_code_value_error_outline(True)
      alert("Please enter your verification code.")
      return
    self._set_code_value_error_outline(False)

  def _sync_nav_auth_state(self, is_logged_in):
    """Updates NavLayout auth links immediately before navigating away."""
    nav = getattr(self, "layout", None)
    if nav is None and callable(get_active_nav_layout):
      nav = get_active_nav_layout()
    if nav is not None and hasattr(nav, "set_auth_state"):
      nav.set_auth_state(bool(is_logged_in))

  def show_entry_screens(self):
    """Shows registration and login sections; hides code verification section."""
    # Registration Section Visible
    self.email_value.visible = True
    self.user_name_value.visible = True
    self.first_name_value.visible = True
    self.last_name_value.visible = True
    self.mobile_phone_value.visible = True
    self.submit_registration_button.visible = True

    # Login Section Visible
    if hasattr(self, "login_email_value"):
      self.login_email_value.visible = True
    self.submit_login_button.visible = True

    # Code Verification Section Hidden
    if hasattr(self, "code_value_label"):
      self.code_value_label.visible = False
    if hasattr(self, "code_value"):
      self.code_value.visible = False
      self._set_code_value_error_outline(False)
    if hasattr(self, "submit_code_button"):
      self.submit_code_button.visible = False

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
    if hasattr(self, "login_email_value"):
      self.login_email_value.visible = False
    self.submit_login_button.visible = False

    # Code Verification Section Visible
    if hasattr(self, "code_value_label"):
      self.code_value_label.visible = True
      self.code_value_label.text = f"Enter the 6-digit code sent to {email}:"

    if hasattr(self, "code_value"):
      self.code_value.visible = True
      self.code_value.text = ""
      self._schedule_code_value_outline(True)

    if hasattr(self, "submit_code_button"):
      self.submit_code_button.visible = True

  @anvil.handle("submit_registration_button", "click")
  def submit_registration_button_click(self, **event_args):
    """Handles new user registration submission."""
    email = self.email_value.text.strip() if self.email_value.text else ""
    user_name = (
        self.user_name_value.text.strip() if self.user_name_value.text else ""
    )
    first_name = (
        self.first_name_value.text.strip() if self.first_name_value.text else ""
    )
    last_name = (
        self.last_name_value.text.strip() if self.last_name_value.text else ""
    )
    mobile_phone = (
        self.mobile_phone_value.text.strip()
        if self.mobile_phone_value.text
        else ""
    )

    if not email or not user_name:
      anvil.alert(
          "Email and Username are required for registration.",
          title="Missing Information",
      )
      return

    try:
      res = anvil.server.call(
          "register_user", email, user_name, first_name, last_name, mobile_phone
      )
      if res["status"] == "success":
        anvil.Notification(
            "Registration successful! Check your email for the code."
        ).show()
        self.show_verification_screen(email)
      else:
        anvil.alert(res["message"], title="Registration Failed")
    except Exception as e:
      anvil.alert(f"An error occurred: {e}")

  @anvil.handle("submit_login_button", "click")
  def submit_login_button_click(self, **event_args):
    """Handles login submission for existing users using login_email_value."""
    target_box = (
        self.login_email_value
        if hasattr(self, "login_email_value")
        else getattr(self, "email_value", None)
    )
    email = target_box.text.strip() if target_box and target_box.text else ""

    if not email:
      anvil.alert(
          "Please enter your email address.", title="Missing Email"
      )
      return

    try:
      res = anvil.server.call("request_login_otp", email)
      if res["status"] == "success":
        anvil.Notification("Login code sent! Check your email.").show()
        self.show_verification_screen(email)
      else:
        anvil.alert(res["message"], title="Login Failed")
    except Exception as e:
      anvil.alert(f"An error occurred: {e}")

  @anvil.handle("submit_code_button", "click")
  def submit_code_button_click(self, **event_args):
      """Handles verification of the 6-digit code."""
      code = (
          self.code_value.text.strip()
          if hasattr(self, "code_value") and self.code_value.text
          else ""
      )

      if not code:
        self._set_code_value_error_outline(True)
        anvil.alert(
            "Please enter the 6-digit verification code.", title="Missing Code"
        )
        return

      self._set_code_value_error_outline(False)

      try:
        res = anvil.server.call("verify_email_otp", self.active_email, code)
        if res["status"] == "success":
          self._sync_nav_auth_state(res.get("is_logged_in", True))
          anvil.Notification("Successfully authenticated!").show()
          open_form("Layouts.NavLayout.About")
        else:
          self._set_code_value_error_outline(True)
          anvil.alert(res["message"], title="Verification Failed")
      except Exception as e:
        self._set_code_value_error_outline(True)
        anvil.alert(f"An error occurred: {e}")