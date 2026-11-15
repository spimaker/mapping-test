import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

@anvil.server.callable
def populate_all_map_summaries(use_test_table=True):
    """
    Reads all records from MapItems_Test and populates 
    the 5 summary tables with centerpoints, bounding boxes, and unique user counts.
    """
    table = app_tables.mapitems_test if use_test_table else app_tables.mapitems
    print("Fetching all records from MapItems table...")
    
    all_rows = list(table.search(
        tables.fetch_only('region', 'country_code', 'state', 'city', 'postal_code', 'latitude', 'longitude', 'user')
    ))
    print(f"Processing {len(all_rows)} records...")

    regions = {}    # key: (region,)
    countries = {}    # key: (country_code,)
    states = {}       # key: (country_code, state)
    cities = {}       # key: (country_code, state, city)
    postals = {}      # key: (country_code, postal_code)

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

    # 1. Aggregate raw records into memory buckets
    for row in all_rows:
        lat = row.get('latitude')
        lon = row.get('longitude')
        if lat is None or lon is None:
            continue
        lat, lon = float(lat), float(lon)
        
        region = (row.get('region') or '').strip()
        country = (row.get('country_code') or '').strip().upper()
        state = (row.get('state') or '').strip().upper()
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

    def compute_metrics(data):
        lats = data['lats']
        lons = data['lons']
        return {
            'center_lat': sum(lats) / len(lats),
            'center_lon': sum(lons) / len(lons),
            'min_lat': min(lats),
            'max_lat': max(lats),
            'min_lon': min(lons),
            'max_lon': max(lons),
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
    for (cc, st), data in states.items():
        metrics = compute_metrics(data)
        app_tables.map_state_summary.add_row(country_code=cc, state=st, **metrics)

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

def copy_all_mapitems_task():
    """Background task to copy the entire MapItems_Test to MapItems_Test2 with periodic updates."""
    source_rows = app_tables.mapitems_test.search()
    total_copied = 0
    start_time = time.time()
    last_print_time = start_time

    for row in source_rows:
        country_code = row.get('country_code')
        state_code = row.get('state')

        # 1. Resolve full country name using pycountry
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

        # 2. Resolve full state name using country_state_city library
        state_name = ""
        if country_code and state_code:
            try:
                states_list = State.get_states_of_country(str(country_code).strip().upper())
                if states_list:
                    for s in states_list:
                        if s.iso_code.upper() == str(state_code).strip().upper() or s.name.upper() == str(state_code).strip().upper():
                            state_name = s.name
                            break
            except Exception:
                pass

        # 3. Insert record into MapItems_Test2 (using 'user' instead of 'user_name')
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

        # Check if a minute (60 seconds) has passed since the last log print
        current_time = time.time()
        if current_time - last_print_time >= 60:
            print(f"Background Progress: {total_copied} records copied so far...")
            last_print_time = current_time

    print(f"Background Task Complete! Total records copied: {total_copied}")
    return total_copied


@anvil.server.callable
def start_copy_entire_table():
    """Client callable to kick off the background task from the DataConversions form."""
    task = anvil.server.launch_background_task("copy_all_mapitems_task")
    return task