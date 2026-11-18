import time
import requests
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


def verify_postal_code_location(postal_code, country_code, expected_state):
  """
  Reverse geocode a postal code via Nominatim to confirm it physically
  belongs to the expected state/province before insertion.
  """
  url = "https://nominatim.openstreetmap.org/search"
  headers = {"User-Agent": "AnvilPostalCodeAuditor/1.0 (contact: admin@app.com)"}
  
  query_str = f"{postal_code}, {country_code}"
  params = {"q": query_str, "format": "json", "limit": 1, "addressdetails": 1}

  try:
    response = requests.get(url, params=params, headers=headers, timeout=5)
    results = response.json()
    
    if results:
      address = results[0].get("address", {})
      found_state = (
          address.get("state")
          or address.get("province")
          or address.get("region")
          or ""
      ).strip().upper()
      
      expected = expected_state.strip().upper()
      if expected in found_state or found_state in expected:
        return True
  except Exception:
    pass

  return False


@anvil.server.background_task
def process_north_america_datahub_summary_task():
  """Background task that audits every state/province in US, CA, and MX from DataHub tables."""
  us_states = [
      "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", 
      "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", 
      "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", 
      "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", 
      "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
  ]
  
  ca_provinces = [
      "AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK", "NT", "NU", "YT"
  ]
  
  mx_states = [
      "AGU", "BCN", "BCS", "CAM", "CHP", "CHH", "COA", "COL", "DUR", "GUA", 
      "GRO", "HID", "JAL", "MEX", "MIC", "MOR", "NAY", "NLE", "OAX", "PUE", 
      "QUE", "ROO", "SLP", "SIN", "SON", "TAB", "TAM", "TLA", "VER", "YUC", "ZAK"
  ]

  targets = [("US", us_states), ("CA", ca_provinces), ("MX", mx_states)]
  
  print("========================================")
  print("Starting North American DataHub Regional Audit")
  print("========================================")
  
  total_records_checked = 0
  
  for country_code, regions in targets:
    print(f"\n--- Processing Country: {country_code} ---")
    for state in regions:
      rows = list(app_tables.datahub_postal_codes.search(
          Country_Code=country_code,
          State_Code=state
      ))
      count = len(rows)
      total_records_checked += count
      print(f"[{country_code}] Region {state}: {count} postal codes found.")

  print(f"\n*** Audit complete! Checked {total_records_checked} total regional records across US, CA, and MX. ***")


@anvil.server.background_task
def rebuild_verified_postal_codes_task():
  """
  Rebuilds app_tables.datahub_postal_codes by fetching raw candidates,
  running Nominatim boundary validation, and writing only clean, verified records.
  """
  print("========================================")
  print("Starting Verified Postal Code Table Rebuild")
  print("========================================")

  us_states = ["AL", "AK"]  # Expand to full list when ready
  targets = [("US", us_states)]

  total_added = 0

  for country_code, regions in targets:
    for state in regions:
      print(f"\nProcessing candidate codes for {country_code} - {state}...")
      
      raw_candidates = app_tables.raw_staging_postal_codes.search(
          Country_Code=country_code,
          State_Code=state
      )
      
      state_added = 0
      for row in raw_candidates:
        pcode = row['Postal_Code']
        
        existing = app_tables.datahub_postal_codes.get(
            Country_Code=country_code, Postal_Code=pcode
        )
        if existing:
          continue

        if verify_postal_code_location(pcode, country_code, state):
          app_tables.datahub_postal_codes.add_row(
              Country_Code=country_code,
              State_Code=state,
              Postal_Code=pcode
          )
          state_added += 1
          total_added += 1
        else:
          print(f"-> Rejected mismatched postal code: {pcode} (claimed {state})")

        time.sleep(1.1)

      print(f"Successfully added {state_added} verified codes for {state}.")

  print(f"\n*** Rebuild complete! Added {total_added} verified records. ***")


# --- Registered Client Callables ---

@anvil.server.callable
def start_north_america_datahub_audit():
  """Client callable to kick off the background audit task."""
  task = anvil.server.launch_background_task("process_north_america_datahub_summary_task")
  return task


@anvil.server.callable
def start_full_north_america_harvest():
  """Client callable to kick off the full harvest background task."""
  task = anvil.server.launch_background_task("rebuild_verified_postal_codes_task")
  return task


@anvil.server.callable
def start_rebuild_verified_table():
  """Client callable to kick off the verified table rebuild background task."""
  task = anvil.server.launch_background_task("rebuild_verified_postal_codes_task")
  return task