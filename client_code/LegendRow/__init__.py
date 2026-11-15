from ._anvil_designer import LegendRowTemplateTemplate
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class LegendRowTemplate(LegendRowTemplateTemplate):
    def __init__(self, **properties):
        # Set Form properties and Data Bindings
        self.init_components(**properties)

    def item_changed(self, item):
        """This method is called when a new item is bound to this row template."""
        if not item:
            return
            
        # Assuming your item dictionary or data row has 'color' and 'text' / 'range' keys:
        if hasattr(self, 'label_text'):
            self.label_text.text = item.get('text', str(item))
            
        # Optional: Set color swatch background or role if applicable
        if hasattr(self, 'color_swatch_label') and 'color' in item:
            self.color_swatch_label.role = item.get('color')