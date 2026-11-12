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
      # Nominatim returns [min_lat, max_lat, min_lon, max_lon] as strings
      bb = results[0]["boundingbox"]
      return float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3])
  except Exception as e:
    print(f"Nominatim lookup failed: {e}")

  return None, None, None, None


@anvil.server.background_task
def run_postal_code_harvest_task(
    target_code, state_code=None, min_lat=None, min_lon=None, max_lat=None, max_lon=None
):
  overpass_url = "https://overpass.openstreetmap.fr/api/interpreter"
  headers = {
      "User-Agent": "AnvilPostalCodeHarvester/1.0 (contact: admin@app.com)"
  }

  # Predefined bounding boxes for reliable spatial queries
  known_boxes = {
      "LI": (47.04, 9.47, 47.27, 9.63),
      "NSW": (-37.50, 140.99, -28.15, 153.63),
      "VIC": (-39.20, 140.96, -33.98, 150.03),
      "QLD": (-29.17, 137.99, -9.14, 153.55),
      "WA": (-35.14, 112.92, -13.67, 129.00),
      "SA": (-38.07, 129.00, -26.00, 141.00),
      "TAS": (-43.74, 143.82, -39.36, 148.48),
      "ACT": (-35.92, 148.76, -35.12, 149.39),
      "NT": (-26.00, 129.00, -10.95, 138.00),
  }

  # 1. Check hardcoded dictionary first
  lookup_key = state_code.upper() if state_code else target_code.upper()
  if min_lat is None and lookup_key in known_boxes:
    min_lat, min_lon, max_lat, max_lon = known_boxes[lookup_key]
    print(f"Using predefined bounding box for {lookup_key}")

  # 2. If not hardcoded, fetch it dynamically from Nominatim
  elif min_lat is None:
    print(f"Fetching bounding box for Country: {target_code}, State: {state_code or 'N/A'} from Nominatim...")
    min_lat, min_lon, max_lat, max_lon = get_bounding_box(target_code, state_code)
    time.sleep(1)  # Polite pause for Nominatim rate limits

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
        region = (
            state_code
            or tags.get("addr:state")
            or tags.get("addr:province")
            or tags.get("addr:municipality")
            or tags.get("is_in:municipality")
            or ""
        )
        harvested_data[pcode] = region

    print(f"Found {len(harvested_data)} unique postal codes.")

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

    print(f"Successfully added {total_added} new records to table.")

  except Exception as e:
    print(f"Error during harvest for {target_code}: {e}")


@anvil.server.callable
def start_harvest_background(
    target_code, state_code=None, min_lat=None, min_lon=None, max_lat=None, max_lon=None
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