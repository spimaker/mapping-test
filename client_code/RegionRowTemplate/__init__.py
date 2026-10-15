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

    row_flow = anvil.FlowPanel(align='left', spacing='none')
    self.column_panel_1.add_component(row_flow)

    columns = [
      ('name', 250, 'left'),
      ('total', 140, 'center'),
      ('day', 70, 'center'),
      ('week', 70, 'center'),
      ('month', 70, 'center'),
      ('quarter', 70, 'center'),
      ('year', 70, 'center')
    ]

    self.labels = {}
    for key, width, align in columns:
      if key == 'name':
        # Use a Link for the name column so it is natively clickable
        comp = anvil.Link(align=align)
        comp.set_event_handler('click', self.row_clicked)
      else:
        # Use regular Labels for the numeric metric columns
        comp = anvil.Label(width=width, align=align)

      row_flow.add_component(comp)
      self.labels[key] = comp

  def set_item_data(self, item):
    """Explicitly called to populate the row data"""
    self.item = item
    if not item:
      return

    self.labels['name'].text = item.get('display_name', '')

    metrics = item.get('metrics', [0, 0, 0, 0, 0, 0])
    self.labels['total'].text = str(metrics[0])
    self.labels['day'].text = str(metrics[1])
    self.labels['week'].text = str(metrics[2])
    self.labels['month'].text = str(metrics[3])
    self.labels['quarter'].text = str(metrics[4])
    self.labels['year'].text = str(metrics[5])

  def row_clicked(self, **event_args):
    """Fires when the row name link is clicked, bubbling up to Scorecard"""
    form = get_open_form()
    if hasattr(form, 'toggle_row'):
      form.toggle_row(self.item)