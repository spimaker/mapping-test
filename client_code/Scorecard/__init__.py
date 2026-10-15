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

    # 1. Build the header row programmatically
    headers = [
      ("Region / Country / City", 250, "center"),
      ("Total", 140, "center"),
      ("Day", 70, "center"),
      ("Week", 70, "center"),
      ("Month", 70, "center"),
      ("Quarter", 70, "center"),
      ("Year", 70, "center")
    ]

    for text, width, alignment in headers:
      lbl = anvil.Label(text=text, bold=True, width=width, align=alignment)
      self.table_header.add_component(lbl)

    # 2. Load the data immediately on startup
    self.load_scorecard_data()

  def load_scorecard_data(self):
    """Loads the default top-level global regions into the repeating panel"""
    regions = [
      'North America', 
      'South America', 
      'Asia', 
      'Europe', 
      'Africa', 
      'Oceania'
    ]

    display_rows = []
    for region in regions:
      display_rows.append({
        'display_name': region,
        'level': 0,
        'key': region,
        'is_expanded': False,
        'metrics': [0, 0, 0, 0, 0, 0]
      })

    print("SETTING REPEATING PANEL ITEMS:", display_rows)
    self.repeating_panel_scorecard.items = display_rows

    # Force-populate each instantiated template row to guarantee rendering
    for child in self.repeating_panel_scorecard.get_components():
      if hasattr(child, 'set_item_data') and child.item:
        child.set_item_data(child.item)