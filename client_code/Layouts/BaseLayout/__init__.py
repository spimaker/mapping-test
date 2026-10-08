from ._anvil_designer import BaseLayoutTemplate
from anvil import *
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class BaseLayout(BaseLayoutTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
