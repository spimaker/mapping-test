from ._anvil_designer import LegendRowTemplate
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class LegendRow(LegendRowTemplate):
    def __init__(self, **properties):
        # Set Form properties and Data Bindings
        self.init_components(**properties)

    def item_changed(self, item, **event_args):
        """This method is called when a new item is bound to this row template."""
        if not item:
            return
            
        # Set the range text
        if hasattr(self, 'range_label'):
            self.range_label.text = item.get('range', str(item))
            
        # Force the swatch label text to be completely blank so only the CSS shape/color shows
        if hasattr(self, 'color_swatch_label'):
            self.color_swatch_label.text = ""
            self.color_swatch_label.role = item.get('role', '')