import random
from datetime import datetime, timedelta
import anvil.server
from anvil.tables import app_tables

@anvil.server.callable
def populate_random_dates():
  count = 0
  for row in app_tables.mapitems.search():
    # Generate a random offset up to 90 days in the past
    random_days = random.randint(0, 90)
    random_seconds = random.randint(0, 86400)
    random_dt = datetime.now() - timedelta(days=random_days, seconds=random_seconds)

    # Update the row
    row.update(date_time=random_dt)
    count += 1

  return f"Successfully updated {count} records with random dates."