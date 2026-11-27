from ._anvil_designer import NavLayoutTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ...AuthVisibilityService import auth_visibility

_active_nav_layout = None
_best_friends_expanded = False
_BEST_FRIENDS_SUBLINKS = (
    "blogs",
    "websites",
    "social",
    "commercial",
    "associations",
    "books",
    "other",
)
_profile_expanded = False
_PROFILE_SUBLINKS = (
    "have_done",
    "qr_code",
)


def get_active_nav_layout():
  return _active_nav_layout


class NavLayout(NavLayoutTemplate):

  def __init__(self, **properties):
    global _active_nav_layout
    _active_nav_layout = self
    super().__init__(**properties)

    if (
        hasattr(self, "login_register_link")
        and self.login_register_link is not None
    ):
      auth_visibility.bind(self.login_register_link, "login_register_link")
    if hasattr(self, "logout_link") and self.logout_link is not None:
      auth_visibility.bind(self.logout_link, "logout_link")

    self.set_best_friends_expanded(_best_friends_expanded)
    self.set_profile_expanded(_profile_expanded)
    self.refresh_auth_links()

  def show_in_content(self, component):
    if hasattr(self, "slots") and "content" in self.slots:
      self.slots["content"].clear()
      self.slots["content"].add_component(component)
    else:
      self.add_component(component, slot="content")

  def set_best_friends_expanded(self, expanded):
    global _best_friends_expanded
    _best_friends_expanded = bool(expanded)

    if hasattr(self, "best_friends") and self.best_friends is not None:
      arrow = "▾" if _best_friends_expanded else "▸"
      self.best_friends.text = f"Best Friends {arrow}"

    for name in _BEST_FRIENDS_SUBLINKS:
      comp = getattr(self, name, None)
      if comp is not None:
        comp.visible = _best_friends_expanded

  def set_profile_expanded(self, expanded):
    global _profile_expanded
    _profile_expanded = bool(expanded)

    if hasattr(self, "profile") and self.profile is not None:
      arrow = "▾" if _profile_expanded else "▸"
      self.profile.text = f"Profile {arrow}"

    for name in _PROFILE_SUBLINKS:
      comp = getattr(self, name, None)
      if comp is not None:
        comp.visible = _profile_expanded

  def set_auth_state(self, is_logged_in):
    auth_visibility.set_logged_in(bool(is_logged_in))

  def refresh_auth_links(self):
    auth_visibility.refresh_auth_state()

  @handle("self", "show")
  def form_show(self, **event_args):
    self.set_best_friends_expanded(_best_friends_expanded)
    self.set_profile_expanded(_profile_expanded)
    self.refresh_auth_links()

  @handle("about_link", "click")
  def about_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.About")

  @handle("view_scorecard_link", "click")
  def scorecard_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    from .Scorecard import Scorecard

    self.set_page_title("The Naturist Scorecard")
    self.show_in_content(Scorecard())

  def set_page_title(self, text):
    if hasattr(self, "slots") and "title" in self.slots:
      title_slot = self.slots["title"]
      for comp in title_slot.get_components():
        if hasattr(comp, "text"):
          comp.text = text
          return
      title_slot.clear()
      title_slot.add_component(Label(text=text, role="h1"))

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

  @handle("profile", "click")
  def profile_click(self, **event_args):
    """This method is called when the link is clicked"""
    self.set_profile_expanded(not _profile_expanded)
    open_form("Layouts.NavLayout.Profile")

  @handle("have_done", "click")
  def have_done_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Profile.HaveDone")

  @handle("best_friends", "click")
  def best_friends_click(self, **event_args):
    """This method is called when the link is clicked"""
    self.set_best_friends_expanded(not _best_friends_expanded)
    open_form("Layouts.NavLayout.BestFriends")

  @handle("blogs", "click")
  def blogs_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.BestFriends.Blogs")

  @handle("websites", "click")
  def websites_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.BestFriends.Websites")

  @handle("social", "click")
  def social_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.BestFriends.Social")

  @handle("commercial", "click")
  def commercial_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.BestFriends.Commercial")

  @handle("associations", "click")
  def associations_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.BestFriends.Associations")

  @handle("discussion", "click")
  def discussion_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Discussion")

  @handle("meetups", "click")
  def meetups_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Meetups")

  @handle("books", "click")
  def books_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.BestFriends.Books")

  @handle("Quotes", "click")
  def quotes_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Quotes")

  @handle("other", "click")
  def other_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.BestFriends.Other")

  @handle("terms", "click")
  def terms_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Terms")

  @handle("qr_code", "click")
  def qr_code_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Layouts.NavLayout.Profile.QRCode")