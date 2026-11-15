import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

@anvil.server.callable
def populate_all_map_summaries():
    """
    Reads all records from MapItems_Test and populates 
    the 5 summary tables with centerpoints, bounding boxes, and unique user counts.
    """
    print("Fetching all records from MapItems_Test...")
    all_rows = list(app_tables.mapitems_test.search(
        tables.fetch_only('region', 'country_code', 'state', 'city', 'postal_code', 'latitude', 'longitude', 'user')
    ))
    print(f"Processing {len(all_rows)} records...")

    # Dictionaries to accumulate data for each tier
    # Keys will be tuples matching the hierarchical scope
    regions = {}      # key: (region,)
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

    # Helper function to compute geometry metrics
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

    return "Migration completed successfully across all 5 summary tiers!"