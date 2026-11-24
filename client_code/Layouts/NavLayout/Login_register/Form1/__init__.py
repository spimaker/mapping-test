from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class Form1(Form1Template):

  def __init__(self, **properties):
    super().__init__(**properties)

  @handle("self", "show")
  def form_show(self, **event_args):
    print("Form1 show fired; layout:", getattr(self, "layout", None))
    if hasattr(self, "layout") and hasattr(self.layout, "refresh_auth_links"):
      self.layout.refresh_auth_links()
