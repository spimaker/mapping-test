from ._anvil_designer import NavLayoutTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

_active_nav_layout = None


def get_active_nav_layout():
  return _active_nav_layout


class NavLayout(NavLayoutTemplate):

  def __init__(self, **properties):
    global _active_nav_layout
    _active_nav_layout = self
    super().__init__(**properties)
    self.refresh_auth_links()

  def set_auth_state(self, is_logged_in):
    self.login_register_link.visible = not bool(is_logged_in)
    self.logout_link.visible = bool(is_logged_in)

  def refresh_auth_links(self):
    session_email = None
    try:
      session_email = anvil.server.call("get_authenticated_user")
    except Exception:
      session_email = None
    self.set_auth_state(bool(session_email))

  @handle("self", "show")
  def form_show(self, **event_args):
    self.refresh_auth_links()

  @handle("about_link", "click")
  def about_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.About")

  @handle("view_scorecard_link", "click")
  def scorecard_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Scorecard")

  @handle("view_map_link", "click")
  def map_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.MapEntry")

  @handle("login_register_link", "click")
  def login_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Login_register")

  @handle("logout_link", "click")
  def logout_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Logout")