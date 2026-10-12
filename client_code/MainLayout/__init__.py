from ._anvil_designer import MainLayoutTemplate
from anvil import *
import anvil.users
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables



class MainLayout(MainLayoutTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    # Automatically load the map view when the app opens
    self.map_link_click()

  def map_link_click(self, **event_args):
    """Triggered when you click the Map link in your sidebar"""
    # Import Form1 locally inside the function to prevent circular imports
    from ..Form1 import Form1

    self.content_panel.clear()
    self.content_panel.add_component(Form1(), full_width_row=True)