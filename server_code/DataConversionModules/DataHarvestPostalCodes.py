import csv
import io
import time
import requests
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


def get_bounding_box(country_code, state_code=None):
  """Query OSM Nominatim API to get bounding box coordinates dynamically."""
  query_str = f"{state_code}, {country_code}" if state_code else country_code
  url = "https://nominatim.openstreetmap.org/search"
  headers = {"User-Agent": "AnvilPostalCodeHarvester/1.0"}
  params = {"q": query_str, "format": "json", "limit": 1}

  try:
    response = requests.get(url, params=params, headers=headers, timeout=10)
    results = response.json()
    if results:
      bb = results[0]["boundingbox"]
      return float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3])
  except Exception as e:
    print(f"Nominatim lookup failed: {e}")

  return None, None, None, None


def execute_postal_code_harvest(target_code, state_code=None, min_lat=None, min_lon=None, max_lat=None, max_lon=None):
  """Core worker function to fetch and store postal codes safely."""
  overpass_url = "https://overpass.openstreetmap.fr/api/interpreter"
  headers = {
      "User-Agent": "AnvilPostalCodeHarvester/1.0 (contact: admin@app.com)"
  }

  if min_lat is None:
    print(f"Fetching bounding box for Country: {target_code}, State/Province: {state_code or 'N/A'} from Nominatim...")
    min_lat, min_lon, max_lat, max_lon = get_bounding_box(target_code, state_code)
    time.sleep(1.5)

  print(f"Querying postal codes for Country: {target_code}, State/Region: {state_code or 'All'} via POST...")

  if min_lat is not None and min_lon is not None and max_lat is not None and max_lon is not None:
    query = f"""
    [out:json][timeout:25];
    (
      node["addr:postcode"]({min_lat}, {min_lon}, {max_lat}, {max_lon});
    );
    out tags;
    """
  else:
    query = f"""
    [out:json][timeout:25];
    area["ISO3166-1"="{target_code}"]->.searchArea;
    node(area.searchArea)["addr:postcode"];
    out tags;
    """

  try:
    response = requests.post(
        overpass_url,
        data={"data": query},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    harvested_data = {}
    for element in data.get("elements", []):
      tags = element.get("tags", {})
      pcode = tags.get("addr:postcode") or tags.get("postal_code")

      if pcode:
        pcode = pcode.strip()
        
        found_region = (
            tags.get("addr:state")
            or tags.get("addr:province")
            or tags.get("addr:municipality")
            or tags.get("is_in:municipality")
            or ""
        ).strip().upper()

        if state_code:
            expected_state = state_code.strip().upper()
            if found_region and found_region != expected_state and expected_state not in found_region:
                continue
            region = expected_state
        else:
            region = found_region or (state_code or "")

        harvested_data[pcode] = region

    print(f"Found {len(harvested_data)} unique validated postal codes for {state_code or target_code}.")

    total_added = 0
    for pcode, region in harvested_data.items():
      existing = app_tables.datahub_postal_codes.get(
          Country_Code=target_code, Postal_Code=pcode
      )
      if not existing:
        app_tables.datahub_postal_codes.add_row(
            Country_Code=target_code,
            State_Code=region,
            Postal_Code=pcode,
        )
        total_added += 1

    print(f"Successfully added {total_added} new records to table for {state_code or target_code}.")

  except Exception as e:
    print(f"Error during harvest for {target_code} ({state_code}): {e}")


# Background task with default optional arguments to satisfy Anvil's dispatcher without prompting
@anvil.server.background_task
def run_postal_code_harvest_task(
    target_code="US", state_code=None, min_lat=None, min_lon=None, max_lat=None, max_lon=None
):
  execute_postal_code_harvest(
      target_code=target_code,
      state_code=state_code,
      min_lat=min_lat,
      min_lon=min_lon,
      max_lat=max_lat,
      max_lon=max_lon
  )


# Completely parameter-free background task function for North America
@anvil.server.background_task
def harvest_all_states_us_ca_mx_task():
  """Loops through every state/province in the US, Canada, and Mexico without prompting."""
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

  for country_code, regions in targets:
    print(f"\n========================================")
    print(f"Starting harvest for Country: {country_code} ({len(regions)} regions)")
    print(f"========================================")

    for state in regions:
      print(f"\n---> Processing {country_code} : {state}")
      try:
        execute_postal_code_harvest(target_code=country_code, state_code=state)
      except Exception as e:
        print(f"Failed harvesting {country_code}-{state}: {e}")

      print("Pausing for 5 seconds...")
      time.sleep(5)

  print("\n*** Completed full North American (US, CA, MX) postal code harvest! ***")


@anvil.server.callable
def start_harvest_background(
    target_code="US", state_code=None, min_lat=None, min_lon=None, max_lat=None, max_lon=None
):
  task = anvil.server.launch_background_task(
      "run_postal_code_harvest_task",
      target_code=target_code,
      state_code=state_code,
      min_lat=min_lat,
      min_lon=min_lon,
      max_lat=max_lat,
      max_lon=max_lon,
  )
  return task


@anvil.server.callable
def start_full_north_america_harvest():
  """Client callable to kick off the multi-country US/CA/MX harvest background task."""
  task = anvil.server.launch_background_task("harvest_all_states_us_ca_mx_task")
  return task