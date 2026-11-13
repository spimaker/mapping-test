import time
import requests
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


@anvil.server.background_task
def harvest_individual_addresses_90272():
  overpass_url = "https://overpass.openstreetmap.fr/api/interpreter"
  nominatim_url = "https://nominatim.openstreetmap.org/search"
  headers = {
      "User-Agent": "AnvilPostalCodeHarvester/1.0 (contact: admin@app.com)"
  }

  country = "US"
  state = "CA"
  pcode = "90272"

  print(f"Looking up bounding box for Postal Code: {pcode} ({state}, {country})...")

  # Step 1: Get bounding box from Nominatim
  bbox = None
  try:
    nom_params = {
        "postalcode": pcode,
        "country": country,
        "format": "json",
        "limit": 1
    }
    nom_response = requests.get(nominatim_url, params=nom_params, headers=headers, timeout=10)
    nom_response.raise_for_status()
    nom_data = nom_response.json()

    if nom_data and len(nom_data) > 0:
      raw_bbox = nom_data[0].get("boundingbox")
      if raw_bbox and len(raw_bbox) == 4:
        south, north, west, east = raw_bbox
        bbox = f"{south},{west},{north},{east}"
  except Exception as e:
    print(f"Nominatim lookup failed for {pcode}: {e}")

  if not bbox:
    print(f"Could not find bounding box for {pcode}. Aborting.")
    return

  print(f"Querying Overpass within bounding box [{bbox}] for {pcode}...")

  # Step 2: Query Overpass strictly inside that bounding box
  query = f"""
  [out:json][timeout:35];
  (
    node["addr:postcode"="{pcode}"]["addr:street"]["addr:housenumber"]({bbox});
    way["addr:postcode"="{pcode}"]["addr:street"]["addr:housenumber"]({bbox});
  );
  out center tags;
  """

  try:
    response = requests.post(
        overpass_url,
        data={"data": query},
        headers=headers,
        timeout=40,
    )
    response.raise_for_status()
    data = response.json()

    addresses_found = 0
    for element in data.get("elements", []):
      tags = element.get("tags", {})
      house_no = tags.get("addr:housenumber")
      street = tags.get("addr:street")
      suburb = tags.get("addr:suburb") or tags.get("addr:city") or "Pacific Palisades"
      
      # Extract lat/lon from node or way center
      lat = element.get("lat") or element.get("center", {}).get("lat")
      lon = element.get("lon") or element.get("center", {}).get("lon")
      
      if house_no and street and lat and lon:
        # Construct the CSV string with coordinates appended
        csv_address_line = f'"{house_no}","{street}","{suburb}","{state}","{country}","{pcode}","{lat}","{lon}"'

        # Write each individual address record to your table
        app_tables.data_addresses.add_row(
            Country_Code=country,
            State_Code=state,
            Postal_Code=pcode,
            CSV_Address=csv_address_line
        )
        addresses_found += 1

    print(f"Successfully wrote {addresses_found} individual address records with lat/lon for {pcode}!")

  except Exception as e:
    print(f"Error fetching addresses for {pcode}: {e}")

  print("Individual address harvesting with coordinates completed.")


@anvil.server.callable
def start_individual_harvest():
  task = anvil.server.launch_background_task("harvest_individual_addresses_90272")
  return task