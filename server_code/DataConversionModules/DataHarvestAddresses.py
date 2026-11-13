import random
import time
import requests
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


@anvil.server.background_task
def harvest_ten_countries_postal_codes():
  overpass_url = "https://overpass.openstreetmap.fr/api/interpreter"
  nominatim_url = "https://nominatim.openstreetmap.org/search"
  headers = {
      "User-Agent": "AnvilPostalCodeHarvester/1.0 (contact: admin@app.com)"
  }

  rows = app_tables.datahub_postal_codes.search()
  
  country_success_counts = {}
  completed_countries = set()
  
  target_countries = 10
  target_codes_per_country = 10

  for row in rows:
    # Check if we have reached our global target of 10 completed countries
    if len(completed_countries) >= target_countries:
      print("Reached target of 10 completed countries. Stopping harvest.")
      break

    country = row.get('country_code') or row.get('Country_Code') or ''
    state = row.get('state_code') or row.get('State_Code') or ''
    pcode = str(row.get('postal_code') or row.get('Postal_Code') or '')

    if not country or not pcode:
      continue

    # If this country has already reached 10 successful postal codes, skip it
    if country in completed_countries:
      continue

    print(f"\n--- Checking Postal Code: {pcode} ({country}, {state}) ---")
    print("Looking up bounding box via Nominatim...")

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
      print(f"Could not find bounding box for {pcode}. Skipping...")
      time.sleep(10)
      continue

    print(f"Querying Overpass within bounding box [{bbox}]...")

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

      valid_elements = []
      for element in data.get("elements", []):
        tags = element.get("tags", {})
        house_no = tags.get("addr:housenumber")
        street = tags.get("addr:street")
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        
        if house_no and street and lat and lon:
          valid_elements.append({
              "house_no": house_no,
              "street": street,
              "suburb": tags.get("addr:suburb") or tags.get("addr:city") or state,
              "lat": lat,
              "lon": lon
          })

      print(f"Found {len(valid_elements)} valid addresses for {pcode}.")

      # Require at least 10 addresses to consider this postal code successful
      if len(valid_elements) < 10:
        print(f"Not enough addresses ({len(valid_elements)} < 10) for {pcode}. Skipping...")
        time.sleep(10)
        continue

      # Sample 10 random addresses
      sampled_addresses = random.sample(valid_elements, 10)

      # Write each address row individually
      for addr in sampled_addresses:
        csv_address_line = f'"{addr["house_no"]}","{addr["street"]}","{addr["suburb"]}","{state}","{country}","{pcode}","{addr["lat"]}","{addr["lon"]}"'

        app_tables.data_addresses.add_row(
            Country_Code=country,
            State_Code=state,
            Postal_Code=pcode,
            CSV_Address=csv_address_line
        )

      current_country_count = country_success_counts.get(country, 0) + 1
      country_success_counts[country] = current_country_count
      print(f"Success for {country}: Postal code {pcode} logged ({current_country_count}/{target_codes_per_country}).")

      if current_country_count >= target_codes_per_country:
        completed_countries.add(country)
        print(f"*** Completed country '{country}' with 10 successful postal codes! Moving to next country. ***")

    except Exception as e:
      print(f"Error fetching addresses for {pcode}: {e}")

    # 10-second pause between queries
    print("Pausing for 10 seconds...")
    time.sleep(10)

  print(f"\nHarvesting complete! Successfully harvested across {len(completed_countries)} countries.")


@anvil.server.callable
def start_individual_harvest():
  task = anvil.server.launch_background_task("harvest_ten_countries_postal_codes")
  return task