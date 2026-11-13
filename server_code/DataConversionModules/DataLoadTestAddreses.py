import random
import time
from datetime import datetime, timedelta
import requests
import pycountry
import pycountry_convert as pc
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


def get_global_region(country_code_or_name):
  """Maps a country code or name to a global macro-region using pycountry_convert."""
  try:
    val = str(country_code_or_name).strip()
    alpha2 = None
    
    # Resolve input to an ISO Alpha-2 code
    if len(val) == 2:
      alpha2 = val.upper()
    elif len(val) == 3:
      c_obj = pycountry.countries.get(alpha_3=val.upper())
      if c_obj:
        alpha2 = c_obj.alpha_2
    else:
      c_obj = pycountry.countries.get(name=val)
      if not c_obj:
        results = pycountry.countries.search_fuzzy(val)
        if results:
          c_obj = results[0]
      if c_obj:
        alpha2 = c_obj.alpha_2

    if not alpha2:
      return "Other"

    # Get continent code (e.g., 'NA', 'EU', 'AS', etc.)
    continent_code = pc.country_alpha2_to_continent_code(alpha2)
    
    # Map continent codes to your 7 macro-regions
    continent_mapping = {
        "NA": "North America",
        "SA": "Latin America & Caribbean",
        "EU": "Europe",
        "AS": "Asia-Pacific", # (Or split further if needed, but covers Asian nations cleanly)
        "AF": "Sub-Saharan Africa / MENA", # Refined below if North African
        "OC": "Asia-Pacific"
    }
    
    region = continent_mapping.get(continent_code, "Other")
    
    # Fine-tune Middle East & North Africa (MENA) vs Sub-Saharan Africa based on standard groupings
    mena_alpha2 = {"AE", "SA", "EG", "TR", "IR", "IQ", "QA", "KW", "OM", "JO", "LB", "MA", "DZ", "TN", "BH", "YE", "LY", "SY"}
    if alpha2 in mena_alpha2:
      return "Middle East & North Africa"
      
    return region

  except Exception:
    return "Other"


@anvil.server.background_task
def get_test_addresses(start_country=None, start_state=None, start_pcode=None):
  overpass_url = "https://overpass.openstreetmap.fr/api/interpreter"
  nominatim_url = "https://nominatim.openstreetmap.org/search"
  headers = {
      "User-Agent": "AnvilPostalCodeHarvester/1.0 (contact: admin@app.com)"
  }

  rows = app_tables.datahub_postal_codes.search()
  
  processed_count = 0
  resuming = bool(start_country and start_pcode)
  if resuming:
    print(f"Resumption requested starting at: Country={start_country}, State={start_state}, Postal Code={start_pcode}")

  def generate_numeric_id():
    return int(time.time() * 1000) + random.randint(1, 999)

  for row in rows:
    country = row.get('country_code') or row.get('Country_Code') or ''
    state = row.get('state_code') or row.get('State_Code') or ''
    pcode = str(row.get('postal_code') or row.get('Postal_Code') or '')

    if not country or not pcode:
      continue

    if resuming:
      match_state = True if not start_state else (state == start_state)
      if country == start_country and match_state and pcode == start_pcode:
        resuming = False
        print(f"Found resume point! Continuing harvest from {country} {state} {pcode}...")
      else:
        continue

    # Determine global region dynamically using pycountry_convert
    region_name = get_global_region(country)

    print(f"\n--- Examining Postal Code: {pcode} ({country}, {state}) [{region_name}] ---")
    current_timestamp = datetime.now()
    
    bbox_found = False
    bbox_str = ""
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
          bbox_str = f"{south},{west},{north},{east}"
          bbox_found = True
    except Exception as e:
      print(f"Nominatim lookup failed for {pcode}: {e}")

    if not bbox_found:
      print(f"Could not find bounding box for {pcode}. Logging result and skipping...")
      app_tables.data_address_results.add_row(
          id=generate_numeric_id(),
          created_time=current_timestamp,
          Country_Code=country,
          State_Code=state,
          Postal_Code=pcode,
          Bounding_Box_Found=False,
          Bounding_Box="",
          Addresses_Found=0,
          Addresses_Saved=0
      )
      time.sleep(10)
      continue

    print(f"Querying Overpass within bounding box [{bbox_str}]...")

    query = f"""
    [out:json][timeout:35];
    (
      node["addr:housenumber"]({bbox_str});
      way["addr:housenumber"]({bbox_str});
      relation["addr:housenumber"]({bbox_str});
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

      elements = data.get("elements", [])
      valid_elements = []
      for element in elements:
        tags = element.get("tags", {})
        house_no = tags.get("addr:housenumber")
        street = tags.get("addr:street")
        
        city = (
            tags.get("addr:suburb") 
            or tags.get("addr:city") 
            or tags.get("addr:town") 
            or tags.get("addr:municipality") 
            or state
        )
        
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        
        if house_no and lat and lon:
          if not street:
            street = tags.get("street") or "Unknown Street"

          valid_elements.append({
              "house_no": house_no,
              "street": street,
              "city": city,
              "lat": lat,
              "lon": lon
          })

      total_found = len(valid_elements)
      print(f"Valid parsed addresses found: {total_found}")

      if total_found == 0:
        print(f"0 valid addresses found for {pcode}. Logging result and skipping...")
        app_tables.data_address_results.add_row(
            id=generate_numeric_id(),
            created_time=current_timestamp,
            Country_Code=country,
            State_Code=state,
            Postal_Code=pcode,
            Bounding_Box_Found=True,
            Bounding_Box=bbox_str,
            Addresses_Found=0,
            Addresses_Saved=0
        )
        time.sleep(10)
        continue

      if total_found <= 150:
        sample_size = total_found
      else:
        sample_size = max(150, int(total_found * 0.10))
        sample_size = min(sample_size, total_found)

      sampled_addresses = random.sample(valid_elements, sample_size)
      print(f"Saving {sample_size} addresses (out of {total_found}) to mapitems_test...")

      for addr in sampled_addresses:
        h_no = addr["house_no"]
        st = addr["street"]
        ct = addr["city"]
        
        user_name_key = f"{country}{state}{pcode}{h_no}{st}{ct}"
        
        random_seconds = random.randint(0, 120 * 24 * 60 * 60)
        random_timestamp = current_timestamp - timedelta(seconds=random_seconds)

        app_tables.mapitems_test.add_row(
            id=generate_numeric_id(),
            created_time=current_timestamp,
            region=region_name,
            user_name=user_name_key,
            address_1=f"{h_no} {st}",
            address_2="",
            city=ct,
            state=state,
            postal_code=pcode,
            country_code=country,
            latitude=float(addr["lat"]),
            longitude=float(addr["lon"]),
            date_time=random_timestamp
        )

      app_tables.data_address_results.add_row(
          id=generate_numeric_id(),
          created_time=current_timestamp,
          Country_Code=country,
          State_Code=state,
          Postal_Code=pcode,
          Bounding_Box_Found=True,
          Bounding_Box=bbox_str,
          Addresses_Found=total_found,
          Addresses_Saved=sample_size
      )

      processed_count += 1
      print(f"Success #{processed_count}: Postal code {pcode} ({country}) successfully logged.")

    except Exception as e:
      print(f"Error fetching addresses for {pcode}: {e}")
      app_tables.data_address_results.add_row(
          id=generate_numeric_id(),
          created_time=datetime.now(),
          Country_Code=country,
          State_Code=state,
          Postal_Code=pcode,
          Bounding_Box_Found=bbox_found,
          Bounding_Box=bbox_str,
          Addresses_Found=0,
          Addresses_Saved=0
      )

    print("Pausing for 10 seconds...")
    time.sleep(10)

  print(f"\nFull harvesting complete! Processed {processed_count} successful postal codes.")


@anvil.server.callable
def start_test_address_load(start_country=None, start_state=None, start_pcode=None):
  task = anvil.server.launch_background_task("get_test_addresses", start_country=start_country, start_state=start_state, start_pcode=start_pcode)
  return task