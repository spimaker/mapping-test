from ._anvil_designer import RegionRowTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class RegionRow(RegionRowTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    # test prints
    print("ITEM KEYS:", list(self.item.keys()))
    print("METRICS:", self.item.get('metrics'))

    # Any code you write here will run before the form opens.
