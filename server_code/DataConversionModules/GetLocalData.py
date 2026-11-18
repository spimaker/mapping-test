import datetime
import random
import time
import requests
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables, query as q
from country_state_city import Country, State, City
from geopy.geocoders import Nominatim

# Initialize Nominatim geolocator
geolocator = Nominatim(user_agent="GetLocalDataHarvester/1.0")

TARGET_COUNTRIES = [
    {"code": "US", "name": "United States", "region": "North America"},
    {"code": "CA", "name": "Canada", "region": "North America"},
    {"code": "MX", "name": "Mexico", "region": "North America"}
]

# Targeted cities mapping by country and state code
TARGET_CITIES_MAP = {
    "CA": {
        "QC": ["Montreal", "Quebec City"],
        "ON": ["Toronto", "Ottawa", "Hamilton"]
    },
    "MX": {
        "CMX": ["Mexico City"],
        "DIF": ["Mexico City"],
        "MEX": ["Mexico City"],
        "JAL": ["Guadalajara"],
        "NLE": ["Monterrey"],
        "BCN": ["Tijuana"],
        "GUA": ["Leon", "San Miguel de Allende"],
        "CHH": ["Ciudad Juarez"]
    },
    "US": {
        "CA": ["Los Angeles", "San Francisco"],
        "AZ": ["Phoenix"],
        "TX": ["Houston", "Dallas"],
        "MO": ["St. Louis", "Kansas City"],
        "IL": ["Chicago"],
        "MA": ["Boston"],
        "PA": ["Philadelphia"],
        "NY": ["New York"]
    }
}

# ---------------------------------------------------------
# HELPER: Format Postal Code
# ---------------------------------------------------------
def clean_postal_code(country_code, pcode):
    """Ensures US postal codes are 5 digits and trims international codes."""
    if not pcode:
        return ""
    pcode = str(pcode).strip()
    if country_code.upper() == "US":
        if "-" in pcode:
            pcode = pcode.split("-")[0].strip()
        elif " " in pcode:
            pcode = pcode.split(" ")[0].strip()
            
        clean_digits = "".join(filter(str.isdigit, pcode))
        if len(clean_digits) >= 5:
            return clean_digits[:5]
    return pcode


# ---------------------------------------------------------
# STEP 1: Clear All Target Tables
# ---------------------------------------------------------
@anvil.server.callable
def clear_all_target_tables():
    """Clears all specified tables completely with console updates."""
    tables_to_clear = [
        ("mapitems_test", app_tables.mapitems_test),
        ("map_region_summary", app_tables.map_region_summary),
        ("map_country_summary", app_tables.map_country_summary),
        ("map_state_summary", app_tables.map_state_summary),
        ("map_city_summary", app_tables.map_city_summary),
        ("map_postal_summary", app_tables.map_postal_summary),
        ("map_user_lookup", app_tables.map_user_lookup),
        ("datahub_postal_codes", app_tables.datahub_postal_codes)
    ]
    
    print("\n[STEP 1/6] Clearing target tables...")
    for t_name, t_obj in tables_to_clear:
        rows = list(t_obj.search())
        count = len(rows)
        print(f" -> Clearing {count} records from '{t_name}'...")
        for row in rows:
            row.delete()
    print("[STEP 1/6] All target tables cleared successfully.\n")


# ---------------------------------------------------------
# STEP 2: Get Postal Codes via Robust Multi-Tier Nominatim Search
# ---------------------------------------------------------
def fetch_postal_codes_for_city(country_code, state_name, city_name):
    """Query Nominatim using multi-tier freeform and structured queries for high reliability."""
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "GetLocalDataHarvester/1.0"}
    postcodes = set()
    
    # Tier 1: Freeform query (Most reliable for international & Mexican cities)
    queries = [
        f"{city_name}, {state_name}, {country_code}",
        f"{city_name}, {country_code}"
    ]
    
    for q_str in queries:
        try:
            params = {
                "q": q_str,
                "format": "json",
                "addressdetails": 1,
                "limit": 40
            }
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            for item in response.json():
                address = item.get("address", {})
                raw_pcode = address.get("postcode")
                if raw_pcode:
                    fmt = clean_postal_code(country_code, raw_pcode)
                    if fmt:
                        postcodes.add(fmt)
            time.sleep(2)
        except Exception:
            time.sleep(3)
            
        if postcodes:
            return list(postcodes)
            
    print(f"    [Warning] Failed to fetch postal codes for {city_name}, {state_name} after retries.")
    return []


# ---------------------------------------------------------
# STEPS 3 & 4: Get Addresses and Write to MapItems_Test
# ---------------------------------------------------------
def fetch_addresses_for_postal_code(country_code, state_code, city_name, postal_code):
    """Query Overpass API for addresses using bounding box derived from postal code lookup."""
    postal_code = clean_postal_code(country_code, postal_code)
    
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    overpass_urls = [
        "https://overpass.openstreetmap.fr/api/interpreter",
        "https://overpass-api.de/api/interpreter"
    ]
    headers = {"User-Agent": "GetLocalDataHarvester/1.0"}
    
    bbox = None
    for attempt in range(2):
        try:
            nom_params = {
                "postalcode": postal_code,
                "country": country_code,
                "format": "json",
                "limit": 1
            }
            nom_res = requests.get(nominatim_url, params=nom_params, headers=headers, timeout=15)
            nom_res.raise_for_status()
            nom_data = nom_res.json()
            if nom_data and len(nom_data) > 0:
                raw_bbox = nom_data[0].get("boundingbox")
                if raw_bbox and len(raw_bbox) == 4:
                    south, north, west, east = raw_bbox
                    bbox = f"{south},{west},{north},{east}"
                    break
        except Exception:
            time.sleep(3)

    if not bbox:
        return []

    query = (
        '[out:json][timeout:50];'
        '('
        f'  node["addr:postcode"="{postal_code}"]["addr:street"]["addr:housenumber"]({bbox});'
        f'  way["addr:postcode"="{postal_code}"]["addr:street"]["addr:housenumber"]({bbox});'
        ');'
        'out center tags;'
    )

    for attempt in range(3):
        for overpass_url in overpass_urls:
            try:
                response = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=55)
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
                        address_1 = f"{house_no} {street}"
                        if country_code and state_code and city_name and address_1 and postal_code:
                            valid_elements.append({
                                "address_1": address_1,
                                "lat": float(lat),
                                "lon": float(lon)
                            })
                time.sleep(3)
                return valid_elements
            except Exception:
                time.sleep(5)
                
    return []


# ---------------------------------------------------------
# STEP 5: Summary Table Updates
# ---------------------------------------------------------
def update_all_summaries():
    print("\n[STEP 5/6] Updating summary tables...")
    raw_rows = list(app_tables.mapitems_test.search())
    
    regions = set(r.get('region') for r in raw_rows if r.get('region'))
    countries = set(r.get('country_code') for r in raw_rows if r.get('country_code'))
    states = set((r.get('country_code'), r.get('state')) for r in raw_rows if r.get('country_code') and r.get('state'))
    cities = set((r.get('country_code'), r.get('state'), r.get('city')) for r in raw_rows if r.get('country_code') and r.get('state') and r.get('city'))
    postals = set((r.get('country_code'), r.get('postal_code')) for r in raw_rows if r.get('country_code') and r.get('postal_code'))

    summary_tables = [
        (app_tables.map_region_summary, "map_region_summary"),
        (app_tables.map_country_summary, "map_country_summary"),
        (app_tables.map_state_summary, "map_state_summary"),
        (app_tables.map_city_summary, "map_city_summary"),
        (app_tables.map_postal_summary, "map_postal_summary")
    ]
    
    for t_obj, t_name in summary_tables:
        rows = list(t_obj.search())
        for row in rows:
            row.delete()
        print(f" -> Cleared old summaries for {t_name}")

    for reg in regions:
        subset = [r for r in raw_rows if r.get('region') == reg]
        _write_summary_tier(app_tables.map_region_summary, {'region': reg}, subset)

    for c_code in countries:
        subset = [r for r in raw_rows if r.get('country_code') == c_code]
        _write_summary_tier(app_tables.map_country_summary, {'country_code': c_code}, subset)

    for c_code, st_code in states:
        subset = [r for r in raw_rows if r.get('country_code') == c_code and r.get('state') == st_code]
        _write_summary_tier(app_tables.map_state_summary, {'country_code': c_code, 'state': st_code}, subset)

    for c_code, st_code, ct_name in cities:
        subset = [r for r in raw_rows if r.get('country_code') == c_code and r.get('state') == st_code and r.get('city') == ct_name]
        _write_summary_tier(app_tables.map_city_summary, {'country_code': c_code, 'state': st_code, 'city': ct_name}, subset)

    for c_code, p_code in postals:
        subset = [r for r in raw_rows if r.get('country_code') == c_code and r.get('postal_code') == p_code]
        _write_summary_tier(app_tables.map_postal_summary, {'country_code': c_code, 'postal_code': p_code}, subset)
    print("[STEP 5/6] Summary tables update complete.\n")


def _write_summary_tier(summary_table, query_dict, subset):
    if not subset:
        return
    lats = [float(r['latitude']) for r in subset if r.get('latitude') is not None]
    lons = [float(r['longitude']) for r in subset if r.get('longitude') is not None]
    users = set(r.get('user') for r in subset if r.get('user'))

    if not lats or not lons:
        return

    metrics = {
        'center_lat': sum(lats) / len(lats),
        'center_lon': sum(lons) / len(lons),
        'min_lat': min(lats),
        'max_lat': max(lats),
        'min_lon': min(lons),
        'max_lon': max(lons),
        'user_count': len(users)
    }
    summary_table.add_row(**query_dict, **metrics)


# ---------------------------------------------------------
# STEP 6: Update Map_user_lookup
# ---------------------------------------------------------
def rebuild_user_lookup():
    print("[STEP 6/6] Rebuilding Map_user_lookup table...")
    for row in list(app_tables.map_user_lookup.search()):
        row.delete()
        
    count = 0
    for item in list(app_tables.mapitems_test.search()):
        lookup_data = {
            'user': item.get('user'),
            'region': item.get('region'),
            'country_code': item.get('country_code'),
            'state': item.get('state'),
            'city': item.get('city'),
            'postal_code': item.get('postal_code')
        }
        try:
            lookup_data['id'] = item.get('id')
        except Exception:
            pass

        app_tables.map_user_lookup.add_row(**lookup_data)
        count += 1
    print(f" -> Added {count} lookup records to Map_user_lookup.")
    print("[STEP 6/6] Map_user_lookup rebuild complete.\n")


# ---------------------------------------------------------
# MASTER ORCHESTRATOR BACKGROUND TASK
# ---------------------------------------------------------
@anvil.server.background_task
def run_full_data_generation_pipeline(start_country=None, start_state_code=None, clear_tables=True, **kwargs):
    print("==================================================")
    print(f"=== STARTING TARGETED PIPELINE (Clear Tables: {clear_tables}) ===")
    print("==================================================")
    
    if clear_tables:
        clear_all_target_tables()
    else:
        print("[INFO] clear_tables=False.")
    
    now = datetime.datetime.now()
    total_addresses_added = 0
    
    skip_country = True if start_country else False
    skip_state = True if start_state_code else False
    
    for country_info in TARGET_COUNTRIES:
        c_code = country_info["code"]
        c_name = country_info["name"]
        region = country_info["region"]
        
        if skip_country:
            if c_code == start_country:
                skip_country = False
            else:
                print(f" -> Skipping country {c_name} ({c_code}) as requested.")
                continue
        
        print(f"\n--------------------------------------------------")
        print(f"Processing Country: {c_name} ({c_code})")
        print(f"--------------------------------------------------")
        
        try:
            states = State.get_states_of_country(c_code)
            if not states:
                continue
            
            for state in states:
                state_code = state.iso_code
                state_name = state.name
                
                # Check if this state has target cities defined in our mapping
                if c_code not in TARGET_CITIES_MAP or state_code not in TARGET_CITIES_MAP[c_code]:
                    continue
                
                if skip_state:
                    if state_code == start_state_code:
                        skip_state = False
                        print(f" -> Resuming at state: {state_name} ({state_code})")
                    else:
                        print(f"   -> Skipping state {state_name} ({state_code})...")
                        continue
                
                print(f"\n   [State] {state_name} ({state_code})")
                target_city_names = TARGET_CITIES_MAP[c_code][state_code]
                
                for city_name in target_city_names:
                    print(f"\n      -> [City] {city_name}")
                    
                    postcodes = fetch_postal_codes_for_city(c_code, state_name, city_name)
                    if not postcodes or len(postcodes) < 1:
                        print(f"         -> No postal codes retrieved for {city_name}. Skipping.")
                        continue
                        
                    random.shuffle(postcodes)
                    
                    valid_postcodes_collected = 0
                    target_valid_count = 20
                    
                    for pcode in postcodes:
                        if valid_postcodes_collected >= target_valid_count:
                            break
                            
                        clean_pcode = clean_postal_code(c_code, pcode)
                        if not clean_pcode:
                            continue
                            
                        raw_addresses = fetch_addresses_for_postal_code(c_code, state_code, city_name, clean_pcode)
                        if len(raw_addresses) < 1:
                            continue
                            
                        valid_postcodes_collected += 1
                        
                        existing_pcode = app_tables.datahub_postal_codes.get(Country_Code=c_code, Postal_Code=clean_pcode)
                        if not existing_pcode:
                            app_tables.datahub_postal_codes.add_row(
                                Country_Code=c_code,
                                State_Code=state_code,
                                Postal_Code=clean_pcode
                            )
                            
                        addresses_to_add = raw_addresses[:50]
                        
                        added_in_pcode = 0
                        for addr in addresses_to_add:
                            user_handle = f"{c_code}/{state_code}/{city_name}/{clean_pcode}/{addr['address_1']}"
                            formatted_addr = f"{user_handle}/{addr['address_1']}/{city_name}, {state_code} {clean_pcode}/{c_name}"
                            random_days_ago = random.uniform(0, 120)
                            random_dt = now - datetime.timedelta(days=random_days_ago)
                            
                            app_tables.mapitems_test.add_row(
                                user=user_handle,
                                date_time=random_dt,
                                created_time=now,
                                region=region,
                                country_code=c_code,
                                country_name=c_name,
                                state=state_code,
                                state_name=state_name,
                                city=city_name,
                                address_1=addr["address_1"],
                                address_2="",
                                postal_code=clean_pcode,
                                formatted_address=formatted_addr,
                                latitude=addr["lat"],
                                longitude=addr["lon"]
                            )
                            added_in_pcode += 1
                            total_addresses_added += 1
                            
                        print(f"            -> Postal code {clean_pcode} ({valid_postcodes_collected}/{target_valid_count}): Added {added_in_pcode} addresses.")
                        
                    print(f"         -> Finished {city_name}: Collected {valid_postcodes_collected} valid postal codes.")
        except Exception as e:
            print(f"[Error] Processing country {c_code} failed: {e}")

    print(f"\nTotal new addresses generated in this run: {total_addresses_added}")

    update_all_summaries()
    rebuild_user_lookup()
    
    print("==================================================")
    print("=== PIPELINE COMPLETE SUCCESSFULLY ===")
    print("==================================================")


@anvil.server.callable
def start_data_generation_task(start_country=None, start_state_code=None, clear_tables=True, **kwargs):
    print(f"Launching hierarchical background task (Country: {start_country}, State: {start_state_code}, Clear: {clear_tables})...")
    task = anvil.server.launch_background_task(
        "run_full_data_generation_pipeline",
        start_country=start_country,
        start_state_code=start_state_code,
        clear_tables=clear_tables
    )
    print(f"Background task launched successfully. Task ID: {task.get_id()}")
    return task