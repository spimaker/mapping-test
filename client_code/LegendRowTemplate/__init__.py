from ._anvil_designer import LegendRowTemplateTemplate

class LegendRowTemplate(LegendRowTemplateTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)

    # Assign the legend-row role to your container panel (replace flow_panel_1 with your container's actual name if different)
    if hasattr(self, 'flow_panel_1'):
      self.flow_panel_1.role = 'legend-row'

    if self.item:
      self.Range_Label.text = self.item['range']
      self.Color_Dot.role = self.item['role']