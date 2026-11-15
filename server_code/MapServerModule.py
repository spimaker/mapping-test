import datetime
import uuid
import math
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables, query as q
import pycountry
from pycountry_convert import country_alpha2_to_continent_code
from country_state_city import Country, State, City
from geopy.geocoders import Nominatim

# Initialize Nominatim geolocator with a unique user agent
geolocator = Nominatim(user_agent="NaturistMappingProject")


def get_target_table(use_test_table):
    """Helper to return the correct Data Table based on the flag."""
    return app_tables.mapitems_test if use_test_table else app_tables.mapitems


def get_region_from_country_code(country_code):
    """Maps a country code to a global region using pycountry_convert."""
    if not country_code:
        return "Other"
    try:
        continent_code = country_alpha2_to_continent_code(country_code.strip().upper())
        continent_map = {
            "NA": "North America",
            "SA": "South America",
            "EU": "Europe",
            "AS": "Asia",
            "AF": "Africa",
            "OC": "Oceania"
        }
        return continent_map.get(continent_code, "Other")
    except Exception:
        return "Other"


def calculate_haversine_distance_km(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_marker_color(count):
    """Determines marker hex color based on record/user count tiers."""
    if count <= 999:
        return '#ADD8E6'      # Light Blue
    elif count <= 9999:
        return '#87CEEB'      # Sky Blue
    elif count <= 99999:
        return '#1E90FF'      # Dodger Blue
    elif count <= 249999:
        return '#4169E1'      # Royal Blue
    elif count <= 999999:
        return '#0000CD'      # Medium Blue
    else:
        return '#000080'      # Navy Blue


def get_marker_scale(count):
    """Determines marker symbol scale based on record/user count tiers."""
    if count <= 999:
        return 8
    elif count <= 9999:
        return 10
    elif count <= 99999:
        return 12
    elif count <= 249999:
        return 16
    elif count <= 999999:
        return 18
    else:
        return 20


@anvil.server.callable
def get_map_markers_with_privacy_view(active_record_id=None, show_actuals=True, use_test_table=False):
    table = get_target_table(use_test_table)
    all_items = list(table.search(q.fetch_only('id', 'latitude', 'longitude', 'offset_latitude', 'offset_longitude', 'user')))
    markers = []

    for row in all_items:
        record_id = row.get('id')
        act_lat = row.get('latitude')
        act_lon = row.get('longitude')
        off_lat = row.get('offset_latitude') or act_lat
        off_lon = row.get('offset_longitude') or act_lon
        username = row.get('user') or row.get('user_name', 'Unknown User')

        is_latest = (record_id == active_record_id)

        if act_lat is not None and act_lon is not None:
            if is_latest and show_actuals:
                markers.append({
                    'lat': float(act_lat),
                    'lon': float(act_lon),
                    'color': '#FF0000',
                    'scale': 10,
                    'user_name': username,
                    'title': username
                })

            if is_latest:
                markers.append({
                    'lat': float(off_lat),
                    'lon': float(off_lon),
                    'color': '#008000',
                    'scale': 10,
                    'user_name': username,
                    'title': username
                })
            else:
                markers.append({
                    'lat': float(off_lat),
                    'lon': float(off_lon),
                    'color': '#ADD8E6',
                    'scale': 8,
                    'user_name': username,
                    'title': username
                })

    return markers


@anvil.server.callable
def get_clustered_map_markers(cluster_type='region', distance_value=None, distance_unit='miles', active_record_id=None, use_test_table=False, bounds=None, zoom_level=None):
    """
    Queries pre-aggregated summary tables using indexed bounding box coordinates 
    for sub-second viewport culling, or falls back to radial distance / privacy views.
    """
    cluster_type = (cluster_type or 'region').lower()

    # --- 1. Administrative Grouping via Pre-Aggregated Summary Tables ---
    if cluster_type in ['country', 'state', 'city', 'region', 'postal code', 'postal']:
        # Select summary table based on cluster_type or zoom_level
        if cluster_type == 'region' or (zoom_level is not None and zoom_level < 4):
            table = app_tables.map_region_summary
            fetch_cols = ('region', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'region'
        elif cluster_type == 'country' or (zoom_level is not None and zoom_level < 7):
            table = app_tables.map_country_summary
            fetch_cols = ('country_code', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'country_code'
        elif cluster_type == 'state' or (zoom_level is not None and zoom_level < 10):
            table = app_tables.map_state_summary
            fetch_cols = ('country_code', 'state', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'state'
        elif cluster_type == 'city' or (zoom_level is not None and zoom_level < 13):
            table = app_tables.map_city_summary
            fetch_cols = ('country_code', 'state', 'city', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'city'
        else:
            table = app_tables.map_postal_summary
            fetch_cols = ('country_code', 'postal_code', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'postal_code'

        # Instant database-level viewport culling using indexed bounding box columns
        if bounds:
            south = bounds.get('south')
            north = bounds.get('north')
            west = bounds.get('west')
            east = bounds.get('east')

            try:
                summary_rows = list(table.search(
                    q.fetch_only(*fetch_cols),
                    min_lat=q.less_than_or_equal_to(north),
                    max_lat=q.greater_than_or_equal_to(south),
                    min_lon=q.less_than_or_equal_to(east),
                    max_lon=q.greater_than_or_equal_to(west)
                ))[:2000]
            except Exception:
                summary_rows = list(table.search(q.fetch_only(*fetch_cols)))[:2000]
        else:
            summary_rows = list(table.search(q.fetch_only(*fetch_cols)))[:2000]

        markers = []
        for row in summary_rows:
            lat = row.get('center_lat')
            lon = row.get('center_lon')
            count = row.get('user_count', 0)
            if lat is None or lon is None:
                continue

            # Determine title label from primary key
            name = row.get(label_key) or 'Cluster'
            
            markers.append({
                'lat': float(lat),
                'lon': float(lon),
                'color': get_marker_color(count),
                'scale': get_marker_scale(count),
                'title': f"{str(name).title()} ({count} users)",
                'user_count': count,
                'keys': {k: row[k] for k in fetch_cols if k in row and k not in ['center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count']}
            })
        return markers

    # --- 2. Radial Distance Grouping ---
    elif cluster_type in ['miles', 'kilometers', 'mi', 'km']:
        raw_table = get_target_table(use_test_table)
        all_items = list(raw_table.search(q.fetch_only('latitude', 'longitude', 'user', 'user_name')))
        
        try:
            radius = float(distance_value or 10)
        except (TypeError, ValueError):
            radius = 10.0
            
        radius_km = radius * 1.60934 if cluster_type in ['miles', 'mi'] else radius
        clusters = []
        
        for row in all_items:
            lat = row.get('latitude')
            lon = row.get('longitude')
            username = row.get('user') or row.get('user_name', 'Unknown User')
            
            if lat is None or lon is None:
                continue
                
            lat, lon = float(lat), float(lon)
            added_to_cluster = False
            
            for cluster in clusters:
                dist = calculate_haversine_distance_km(cluster['lat'], cluster['lon'], lat, lon)
                if dist <= radius_km:
                    cluster['users'].add(username)
                    cluster['lats'].append(lat)
                    cluster['lons'].append(lon)
                    cluster['lat'] = sum(cluster['lats']) / len(cluster['lats'])
                    cluster['lon'] = sum(cluster['lons']) / len(cluster['lons'])
                    added_to_cluster = True
                    break
            
            if not added_to_cluster:
                clusters.append({
                    'lat': lat,
                    'lon': lon,
                    'lats': [lat],
                    'lons': [lon],
                    'users': {username}
                })
                
        markers = []
        unit_label = 'miles' if cluster_type in ['miles', 'mi'] else 'km'
        for i, cluster in enumerate(clusters, 1):
            user_list = list(cluster['users'])
            count = len(user_list)
            markers.append({
                'lat': cluster['lat'],
                'lon': cluster['lon'],
                'color': get_marker_color(count),
                'scale': get_marker_scale(count),
                'title': f"Cluster {i} ({count} users within {radius} {unit_label})",
                'users': user_list
            })
        return markers

    else:
        return get_map_markers_with_privacy_view(active_record_id=active_record_id, use_test_table=use_test_table)


@anvil.server.callable
def save_map_item(item_id, item_data, use_test_table=True):
    """
    Saves/updates a map item and updates all 5 summary tables in real-time.
    """
    table = get_target_table(use_test_table)
    
    country = (item_data.get('country_code') or '').strip().upper()
    state = (item_data.get('state') or '').strip().upper()
    city = (item_data.get('city') or '').strip()
    postal_code = (item_data.get('postal_code') or '').strip()
    address_1 = item_data.get('address_1')
    address_2 = item_data.get('address_2')
    user_name = item_data.get('user') or item_data.get('user_name')

    region = item_data.get('region') or get_region_from_country_code(country)
    item_data['region'] = region

    query_parts = [address_1, address_2, city, state, country, postal_code]
    query_string = ", ".join([str(p) for p in query_parts if p])

    lat = item_data.get('latitude')
    lon = item_data.get('longitude')
    formatted_address = item_data.get('formatted_address', '')

    try:
        if query_string.strip() and (lat is None or lon is None):
            location = geolocator.geocode(query_string)
            if location:
                lat = location.latitude
                lon = location.longitude
                formatted_address = location.address
                item_data['latitude'] = lat
                item_data['longitude'] = lon
                item_data['formatted_address'] = formatted_address
    except Exception:
        pass

    current_time = datetime.datetime.now()
    if 'date_time' not in item_data or not item_data['date_time']:
        item_data['date_time'] = current_time

    if item_id:
        row = table.get_by_id(item_id)
        if row:
            row.update(**item_data)
            generated_id = item_id
        else:
            generated_id = str(uuid.uuid4())
            item_data['id'] = generated_id
            row = table.add_row(**item_data)
    else:
        generated_id = str(uuid.uuid4())
        item_data['id'] = generated_id
        row = table.add_row(**item_data)

    # Real-time summary table updates
    if lat is not None and lon is not None:
        lat_f, lon_f = float(lat), float(lon)
        update_summary_tier(app_tables.map_region_summary, {'region': region}, lat_f, lon_f, user_name, table, region=region)
        update_summary_tier(app_tables.map_country_summary, {'country_code': country}, lat_f, lon_f, user_name, table, country_code=country)
        update_summary_tier(app_tables.map_state_summary, {'country_code': country, 'state': state}, lat_f, lon_f, user_name, table, country_code=country, state=state)
        update_summary_tier(app_tables.map_city_summary, {'country_code': country, 'state': state, 'city': city}, lat_f, lon_f, user_name, table, country_code=country, state=state, city=city)
        update_summary_tier(app_tables.map_postal_summary, {'country_code': country, 'postal_code': postal_code}, lat_f, lon_f, user_name, table, country_code=country, postal_code=postal_code)

    return generated_id


def update_summary_tier(summary_table, query_dict, lat, lon, user, raw_table, **raw_filters):
    """Helper to recalculate bounding box and user count for a specific summary bucket."""
    summary_row = summary_table.get(**query_dict)
    
    bucket_rows = list(raw_table.search(**raw_filters))
    if not bucket_rows:
        if summary_row:
            summary_row.delete()
        return

    lats = [float(r['latitude']) for r in bucket_rows if r.get('latitude') is not None]
    lons = [float(r['longitude']) for r in bucket_rows if r.get('longitude') is not None]
    users = set(r.get('user') or r.get('user_name') for r in bucket_rows if r.get('user') or r.get('user_name'))

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

    if summary_row:
        summary_row.update(**metrics)
    else:
        summary_table.add_row(**query_dict, **metrics)



@anvil.server.callable
def get_country_list():
    region_order = ["North America", "South America", "Europe", "Asia", "Africa", "Oceania", "Other"]
    continent_code_mapping = {
        "NA": "North America", "SA": "South America", "EU": "Europe",
        "AS": "Asia", "AF": "Africa", "OC": "Oceania"
    }
    country_list = [("<Select Country>", None)]
    try:
        countries = list(pycountry.countries)
        if countries:
            grouped_countries = {region: [] for region in region_order}
            for c in countries:
                region_name = "Other"
                try:
                    continent_code = country_alpha2_to_continent_code(c.alpha_2)
                    region_name = continent_code_mapping.get(continent_code, "Other")
                except Exception:
                    region_name = "Other"
                grouped_countries[region_name].append((c.name, c.alpha_2))
            
            for region in region_order:
                sorted_region_countries = sorted(grouped_countries[region], key=lambda x: x[0])
                for name, code in sorted_region_countries:
                    country_list.append((f"[{region}] {name}", code))
    except Exception as e:
        pass
    return country_list


@anvil.server.callable
def get_states_for_country(country_code):
    state_list = [("<Select State>", None)]
    if not country_code:
        return state_list
    try:
        states = State.get_states_of_country(country_code)
        if states:
            sorted_states = sorted([(s.name, s.iso_code) for s in states], key=lambda x: x[0])
            for state_name, state_code in sorted_states:
                state_list.append((state_name, state_code))
    except Exception as e:
        pass
    return state_list


@anvil.server.callable
def get_cities_for_state(country_code, state_code):
    city_list = [("<Select City>", None)]
    if not country_code or not state_code:
        return city_list
    seen_cities = set()
    try:
        cities = City.get_cities_of_state(country_code, state_code)
        if cities:
            for c_name in sorted([c.name for c in cities]):
                if c_name not in seen_cities:
                    seen_cities.add(c_name)
                    city_list.append((c_name, c_name))
    except Exception as e:
        pass
    city_list.append(("Enter City Manually", "MANUAL_ENTRY"))
    return city_list


@anvil.server.callable
def geocode_address(address_query):
    parts = [
        address_query.get('address_1'), address_query.get('address_2'),
        address_query.get('city'), address_query.get('state'),
        address_query.get('country'), address_query.get('postal_code')
    ]
    query_string = ", ".join([str(p) for p in parts if p])
    try:
        if query_string.strip():
            location = geolocator.geocode(query_string)
            if location:
                return {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'formatted_address': location.address
                }
    except Exception as e:
        pass
    return {'latitude': None, 'longitude': None, 'formatted_address': ''}