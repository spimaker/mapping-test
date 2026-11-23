from ._anvil_designer import NavLayoutTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class NavLayout(NavLayoutTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    # Any code you write here will run before the form opens.

  @handle("about_link", "click")
  def about_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("About")

  @handle("view_scorecard_link", "click")
  def scorecard_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form("Scorecard")

  @handle("view_map_link", "click")
  def map_link_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('MapEntry')
