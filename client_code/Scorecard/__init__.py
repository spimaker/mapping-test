from ._anvil_designer import ScorecardTemplate
import anvil.server
# ... other imports ...

class Scorecard(ScorecardTemplate):
  def __init__(self, **properties):
    # Conversion programs
    # Run only once and then comment out the call
    #anvil.server.call('populate_random_dates')
    #
    
    super().__init__(**properties)
   
    self.data_grid_1.columns = [
      {"id": "column_1", "title": "Name", "data_key": "display_name", "width": 250},
      {"id": "column_2", "title": "Total", "data_key": "column_2", "width": 80},
      {"id": "column_3", "title": "Day", "data_key": "column_3", "width": 80},
      {"id": "column_4", "title": "Week", "data_key": "column_4", "width": 80},
      {"id": "column_5", "title": "Month", "data_key": "column_5", "width": 80},
      {"id": "column_6", "title": "Quarter", "data_key": "column_6", "width": 80},
      {"id": "column_7", "title": "Year", "data_key": "column_7", "width": 80}
    ]

    self.refresh_table_view()

  def refresh_table_view(self):
    items = self.get_flattened_rows()
    print("DEBUG ROWS:", items)
    self.repeating_panel_1.items = items

  def get_flattened_rows(self):
    # Call your server function or return your regions data list here
    return anvil.server.call('get_flattened_rows')