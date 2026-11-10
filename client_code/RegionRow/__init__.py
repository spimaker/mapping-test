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

    # 1. Force exact column widths summing to 100% using default names
        self.link_1.css_properties = {'width': '40%', 'display': 'inline-block'}

        numeric_labels = [
            self.label_1,
            self.label_2,
            self.label_3,
            self.label_4,
            self.label_5,
            self.label_6,
        ]

        for label in numeric_labels:
          label.css_properties = {
              'width': '10%',
              'display': 'inline-block',
              'text-align': 'right',
          # 1. Force exact column widths summing to 100% using default names
              self.link_1.css_properties = {'width': '40%', 'display': 'inline-block'}

              numeric_labels = [
                  self.label_1,
                  self.label_2,
                  self.label_3,
                  self.label_4,
                  self.label_5,
                  self.label_6,
              ]

              for label in numeric_labels:
                label.css_properties = {
                    'width': '10%',
                    'display': 'inline-block',
                    'text-align': 'right',
                }

  def link_1_click(self, **event_args):
      """Triggered when clicking the region/country name to drill down"""
      item = self.item
      if item and item.get('next_level'):
        self.parent.raise_event(
            'x-drill-down',
            level=item['next_level'],
            parent_id=item['id'],
            parent_name=item['name'],
        )

     
