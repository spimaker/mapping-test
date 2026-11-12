import csv
import io
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import requests


@anvil.server.callable
def populate_datahub_countries():
  # DataHub standard ISO country list CSV endpoint
  url = "https://datahub.io/core/country-list/r/data.csv"

  print("Fetching country list from DataHub...")
  response = requests.get(url)
  response.raise_for_status()

  # Parse CSV text natively using standard library
  f = io.StringIO(response.text)
  reader = csv.DictReader(f)

  # Iterate through the rows and add them directly to the Anvil data table
  count = 0
  errors = 0
  
  for row in reader:
    country_name = row.get("Name")
    country_code = row.get("Code")

    if country_name and country_code:
      try:
        app_tables.datahub_countries.add_row(
            Name=country_name.strip(),
            Code=country_code.strip(),
        )
        count += 1
      except Exception as e:
        errors += 1
        print(f"Failed to add row -> Name: '{country_name}', Code: '{country_code}'. Error: {e}")

  print(f"Finished. Successfully loaded {count} rows. Errors: {errors}")
  return f"Loaded {count} countries successfully with {errors} errors."