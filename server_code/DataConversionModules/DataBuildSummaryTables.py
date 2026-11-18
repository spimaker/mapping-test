import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import pycountry
import time

@anvil.server.callable
def populate_all_map_summaries(use_test_table=True):
    """
    Reads all records from MapItems_Test (or MapItems) and populates 
    the 5 summary tables with true bounding-box centerpoints, bounding boxes, and unique user counts.
    """
    table = app_tables.mapitems_test if use_test_table else app_tables.mapitems
    print("Fetching all records from MapItems table...")
    
    all_rows = list(table.search(
        tables.fetch_only('region', 'country_code', 'state', 'city', 'postal_code', 'latitude', 'longitude', 'user')
    ))
    print(f"Processing {len(all_rows)} records...")

    # --- ALABAMA RAW DATA DIAGNOSTIC INSPECTION ---
    al_records = [r for r in all_rows if (r.get('state') or '').strip().upper() == 'AL']
    print(f"--- RAW ALABAMA RECORDS DEBUG (Total Found: {len(al_records)}) ---")
    for idx, r in enumerate(al_records[:10]):
        print(f"Row {idx+1}: City={r.get('city')}, Lat={r.get('latitude')}, Lon={r.get('longitude')}, User={r.get('user')}")
    print(f"---------------------------------------------------------------")
    # ---------------------------------------------

    regions = {}    # key: (region,)
    countries = {}  # key: (country_code,)
    states = {}     # key: (country_code, state)
    cities = {}     # key: (country_code, state, city)
    postals = {}    # key: (country_code, postal_code)

    def add_to_bucket(bucket_dict, key, lat, lon, user):
        if key not in bucket_dict:
            bucket_dict[key] = {
                'lats': [], 
                'lons': [], 
                'users': set()
            }
        bucket_dict[key]['lats'].append(lat)
        bucket_dict[key]['lons'].append(lon)
        if user:
            bucket_dict[key]['users'].add(user)

    # 1. Aggregate raw records into memory buckets with strict coordinate validation & corruption fixes
    skipped_count = 0
    fixed_lon_count = 0

    for row in all_rows:
        raw_lat = row.get('latitude')
        raw_lon = row.get('longitude')
        
        if raw_lat is None or raw_lon is None:
            skipped_count += 1
            continue
            
        try:
            lat = float(raw_lat)
            lon = float(raw_lon)
        except (ValueError, TypeError):
            skipped_count += 1
            continue
            
        # Strict sanity check for valid Earth latitude bounds
        if not (-90.0 <= lat <= 90.0):
            skipped_count += 1
            continue

        state_check = (row.get('state') or '').strip().upper()

        # DATA CORRUPTION FIX:
        # If longitude is positive and falls between 0 and 90, it is actually holding a latitude value.
        # US / North American longitudes must be negative (e.g., -114 to -125 for CA).
        if 0.0 < lon <= 90.0:
            fixed_lon_count += 1
            if state_check == 'CA':
                lon = -119.4179  # Central California fallback longitude
            else:
                lon = -abs(lon)   # Force negative as a general fallback

        # Ensure longitude is within valid global bounds [-180, 180]
        if not (-180.0 <= lon <= 180.0):
            skipped_count += 1
            continue
            
        region = (row.get('region') or '').strip()
        country = (row.get('country_code') or '').strip().upper()
        state = state_check
        city = (row.get('city') or '').strip()
        postal = (row.get('postal_code') or '').strip()
        
        user = row.get('user')

        if region:
            add_to_bucket(regions, (region,), lat, lon, user)
        if country:
            add_to_bucket(countries, (country,), lat, lon, user)
            if state:
                add_to_bucket(states, (country, state), lat, lon, user)
                if city:
                    add_to_bucket(cities, (country, state, city), lat, lon, user)
            if postal:
                add_to_bucket(postals, (country, postal), lat, lon, user)

    print(f"Corrected {fixed_lon_count} records where longitude was incorrectly stored as a positive latitude.")
    print(f"Skipped {skipped_count} records due to invalid or out-of-bounds coordinates.")

    def compute_metrics(data):
        lats = data['lats']
        lons = data['lons']
        
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        return {
            # True geographic midpoint of the bounding box
            'center_lat': (min_lat + max_lat) / 2.0,
            'center_lon': (min_lon + max_lon) / 2.0,
            'min_lat': min_lat,
            'max_lat': max_lat,
            'min_lon': min_lon,
            'max_lon': max_lon,
            'user_count': len(data['users'])
        }

    # 2. Clear existing summary tables and write fresh data
    print("Clearing and repopulating Map_region_summary...")
    app_tables.map_region_summary.delete_all_rows()
    for (reg,), data in regions.items():
        metrics = compute_metrics(data)
        app_tables.map_region_summary.add_row(region=reg, **metrics)

    print("Clearing and repopulating Map_country_summary...")
    app_tables.map_country_summary.delete_all_rows()
    for (cc,), data in countries.items():
        metrics = compute_metrics(data)
        app_tables.map_country_summary.add_row(country_code=cc, **metrics)

    print("Clearing and repopulating Map_state_summary...")
    app_tables.map_state_summary.delete_all_rows()
    
    state_print_debug = []
    for (cc, st), data in states.items():
        metrics = compute_metrics(data)
        app_tables.map_state_summary.add_row(country_code=cc, state=st, **metrics)
        if len(state_print_debug) < 10:
            state_print_debug.append((st, cc, metrics['center_lat'], metrics['center_lon'], metrics['user_count']))

    print(f"--- STATE SUMMARY TABLE DEBUG (First 10) ---")
    for item in state_print_debug:
        print(f"State: {item[0]} | Country: {item[1]} | Center Lat/Lon: ({item[2]:.4f}, {item[3]:.4f}) | Users: {item[4]}")
    print(f"--------------------------------------------")

    print("Clearing and repopulating Map_city_summary...")
    app_tables.map_city_summary.delete_all_rows()
    for (cc, st, ct), data in cities.items():
        metrics = compute_metrics(data)
        app_tables.map_city_summary.add_row(country_code=cc, state=st, city=ct, **metrics)

    print("Clearing and repopulating Map_postal_summary...")
    app_tables.map_postal_summary.delete_all_rows()
    for (cc, pc), data in postals.items():
        metrics = compute_metrics(data)
        app_tables.map_postal_summary.add_row(country_code=cc, postal_code=pc, **metrics)

    return f"Migration completed successfully! Processed {len(all_rows)} records across all 5 summary tiers."


@anvil.server.background_task
def copy_all_mapitems_task():
    """Background task to copy the entire MapItems_Test to MapItems_Test2 with periodic updates."""
    source_rows = app_tables.mapitems_test.search()
    total_copied = 0
    start_time = time.time()
    last_print_time = start_time

    for row in source_rows:
        country_code = row.get('country_code')
        state_code = row.get('state')

        country_name = ""
        if country_code:
            try:
                code_str = str(country_code).strip()
                c_obj = None
                if len(code_str) == 2:
                    c_obj = pycountry.countries.get(alpha_2=code_str.upper())
                elif len(code_str) == 3:
                    c_obj = pycountry.countries.get(alpha_3=code_str.upper())

                if c_obj:
                    country_name = c_obj.name
            except Exception:
                pass

        state_name = ""

        app_tables.mapitems_test2.add_row(
            id=row.get('id'),
            created_time=row.get('created_time'),
            date_time=row.get('date_time'),
            region=row.get('region'),
            country_code=country_code,
            country_name=country_name,
            state=state_code,
            state_name=state_name,
            city=row.get('city'),
            postal_code=row.get('postal_code'),
            address_1=row.get('address_1'),
            address_2=row.get('address_2'),
            latitude=row.get('latitude'),
            longitude=row.get('longitude'),
            offset_latitude=row.get('offset_latitude'),
            offset_longitude=str(row.get('offset_longitude') or ''),
            formatted_address=row.get('formatted_address'),
            index=row.get('index'),
            user=row.get('user')
        )
        total_copied += 1

        current_time = time.time()
        if current_time - last_print_time >= 60:
            print(f"Background Progress: {total_copied} records copied so far...")
            last_print_time = current_time

    print(f"Background Task Complete! Total records copied: {total_copied}")
    return total_copied


@anvil.server.callable
def start_copy_entire_task():
    """Client callable to kick off the background task."""
    task = anvil.server.launch_background_task("copy_all_mapitems_task")
    return task