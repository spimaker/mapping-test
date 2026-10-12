import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server

@anvil.server.callable
def delete_id_range():
  count = 0
  # Search all rows in mapitems
  for row in app_tables.mapitems.search():
    try:
      # Extract the number from strings like "ID126" -> 126
      num_id = int(str(row['id']).replace('ID', ''))

      # Check if it falls within your range
      if 126 <= num_id <= 250:
        row.delete()
        count += 1
    except (ValueError, TypeError):
      # Skip rows if an ID doesn't match the expected format
      continue

  return f"Successfully deleted {count} rows in the specified range."