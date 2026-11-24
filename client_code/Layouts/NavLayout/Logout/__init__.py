from ._anvil_designer import LogoutTemplate
from anvil import *
import anvil.server
import anvil.users

try:
  from ...Layouts.NavLayout import get_active_nav_layout
except Exception:
  get_active_nav_layout = None


class Logout(LogoutTemplate):

  def __init__(self, **properties):
    super().__init__(**properties)
    self.logout_drop_down.items = ["Keep Me Logged In", "Yes - Log Me Out"]
    self.logout_drop_down.selected_value = "Keep Me Logged In"

  def _sync_nav_auth_state(self, is_logged_in):
    nav = getattr(self, "layout", None)
    if nav is None and callable(get_active_nav_layout):
      nav = get_active_nav_layout()
    if nav is not None and hasattr(nav, "set_auth_state"):
      nav.set_auth_state(bool(is_logged_in))

  @handle("continue_button", "click")
  def continue_button_click(self, **event_args):
    is_logged_in = True
    if self.logout_drop_down.selected_value == "Yes - Log Me Out":
      try:
        anvil.users.logout()
      except Exception:
        pass
      res = anvil.server.call("clear_authenticated_user")
      if isinstance(res, dict):
        is_logged_in = res.get("is_logged_in", False)
      else:
        is_logged_in = False
      self._sync_nav_auth_state(is_logged_in)
    open_form("Layouts.NavLayout.About")