from ._anvil_designer import RegionRowTemplateTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class RegionRowTemplate(RegionRowTemplateTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)

  def row_clicked(self, **event_args):
    """Fires when the row name link is clicked, bubbling up to Scorecard"""
    form = get_open_form()
    if hasattr(form, 'toggle_row'):
      form.toggle_row(self.item)