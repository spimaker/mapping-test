from ._anvil_designer import ScorecardTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class Scorecard(ScorecardTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)

    # Define your column titles
    headers = [
      ("Region / Country / City", 250, "center"), # Added alignment parameter
      ("Total", 140, "center"),
      ("Day", 70, "center"),
      ("Week", 70, "center"),
      ("Month", 70, "center"),
      ("Quarter", 70, "center"),
      ("Year", 70, "center")
    ]

    # Programmatically populate the table_header FlowPanel
    for text, width, alignment in headers:
      lbl = Label(text=text, bold=True, width=width, align=alignment)
      self.table_header.add_component(lbl)
      