import anvil.email
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server

@anvil.server.callable
def get_flattened_rows():
  regions_list = []

  # Query your data tables and map them to your expected dictionary structure
  for row in app_tables.regions.search():  # Replace 'regions' with your actual table name
    regions_list.append({
      "display_name": row['region_name'],  # Replace with your table's column name
      "metrics": [
        row['total'], 
        row['day'], 
        row['week'], 
        row['month'], 
        row['quarter'], 
        row['year']
      ]
    })

  return regions_list