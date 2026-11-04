from ._anvil_designer import RegionRowTemplateTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class RegionRowTemplate(RegionRowTemplateTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    # Any code you write here will run before the form opens.

  @handle("link_1", "click")
  def link_1_click(self, **event_args):
    """This method is called when the link is clicked"""
    # 1. Toggle the expanded state of the current item dictionary
    self.item['is_expanded'] = not self.item['is_expanded']

    # 2. Call your refresh method on the parent Scorecard form
    parent_form = self.parent.parent
    if hasattr(parent_form, 'refresh_table_view'):
      parent_form.refresh_table_view()
