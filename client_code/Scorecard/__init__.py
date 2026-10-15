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

    # Track expansion states (e.g. set of region names or "Region:Country" keys)
    self.expanded_nodes = set()
    self.raw_hierarchy_data = {}

    self.load_scorecard_data()

  def load_scorecard_data(self):
    # Fetch data from server
    #print("TEST PING:", anvil.server.call('test_ping'))
    self.raw_hierarchy_data = anvil.server.call('get_scorecard_hierarchy_data')
    self.refresh_table_view()

  def get_flattened_rows(self):
    """Flattens the hierarchy into a list based on what is currently expanded."""
    display_rows = []
    regions = ['North America', 'South America', 'Asia', 'Europe', 'Africa', 'Oceania']

    for region in regions:
      # Only show region if it exists in data or always show all 6 major regions
      countries_dict = self.raw_hierarchy_data.get(region, {})

      is_reg_expanded = region in self.expanded_nodes
      reg_prefix = "[-] " if is_reg_expanded else "[+] "

      display_rows.append({
        'display_name': f"{reg_prefix}{region}",
        'level': 0,
        'key': region,
        'is_expanded': is_reg_expanded,
        'has_children': len(countries_dict) > 0,
        'metrics': [sum(sum(cities.values()) for cities in countries_dict.values()), 0, 0, 0, 0, 0]
      })

      # If region is expanded, add its countries
      if is_reg_expanded:
        for country, cities_dict in sorted(countries_dict.items()):
          country_key = f"{region}:{country}"
          is_country_expanded = country_key in self.expanded_nodes
          country_prefix = "    [-] " if is_country_expanded else "    [+] "

          country_total = sum(cities_dict.values())
          display_rows.append({
            'display_name': f"{country_prefix}{country}",
            'level': 1,
            'key': country_key,
            'is_expanded': is_country_expanded,
            'has_children': len(cities_dict) > 0,
            'metrics': [country_total, 0, 0, 0, 0, 0]
          })

          # If country is expanded, add its cities
          if is_country_expanded:
            for city, count in sorted(cities_dict.items()):
              display_rows.append({
                'display_name': f"        {city}",
                'level': 2,
                'key': f"{country_key}:{city}",
                'is_expanded': False,
                'has_children': False,
                'metrics': [count, 0, 0, 0, 0, 0]
              })

    return display_rows

  def refresh_table_view(self):
    items = self.get_flattened_rows()
    self.repeating_panel_scorecard.items = items
    for child in self.repeating_panel_scorecard.get_components():
      if hasattr(child, 'set_item_data') and child.item:
        child.set_item_data(child.item)

  def toggle_row(self, item):
    """Called when a row is clicked to expand/collapse"""
    if not item.get('has_children'):
      return

    key = item['key']
    if key in self.expanded_nodes:
      self.expanded_nodes.remove(key)
    else:
      self.expanded_nodes.add(key)

    self.refresh_table_view()