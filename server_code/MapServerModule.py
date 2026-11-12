import datetime
import uuid
import math
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables
import pycountry
from pycountry_convert import country_alpha2_to_continent_code
from country_state_city import Country, State, City
from geopy.geocoders import Nominatim

# Initialize Nominatim geolocator with a unique user agent
geolocator = Nominatim(user_agent="NaturistMappingProject")


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
def get_map_markers_with_privacy_view(active_record_id=None, show_actuals=True):
    """Fetches markers: shows red actual + green offset ONLY for the just-entered record."""
    all_items = list(app_tables.mapitems.search())
    markers = []

    for row in all_items:
        record_id = row.get('id')
        act_lat = row.get('latitude')
        act_lon = row.get('longitude')
        off_lat = row.get('offset_latitude') or act_lat
        off_lon = row.get('offset_longitude') or act_lon
        username = row.get('user_name', 'Unknown User')

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
def get_clustered_map_markers(cluster_type='region', distance_value=None, distance_unit='miles', active_record_id=None):
    """Aggregates map records based on administrative boundaries, radial distance, or individual view."""
    all_items = list(app_tables.mapitems.search())
    cluster_type = (cluster_type or 'region').lower()

    # --- 1. Administrative Grouping (Country, State, City, Region, Postal Code) ---
    if cluster_type in ['country', 'state', 'city', 'region', 'postal code']:
        groups = {}
        
        for row in all_items:
            lat = row.get('latitude')
            lon = row.get('longitude')
            username = row.get('user_name', 'Unknown User')
            
            if lat is None or lon is None:
                continue

            lat, lon = float(lat), float(lon)

            if cluster_type == 'region':
                c_code = row.get('country_code')
                key_val = 'Unassigned Region'
                if c_code:
                    try:
                        continent_code = country_alpha2_to_continent_code(c_code)
                        continent_map = {
                            "NA": "North America", "SA": "South America", 
                            "EU": "Europe", "AS": "Asia", "AF": "Africa", "OC": "Oceania"
                        }
                        key_val = continent_map.get(continent_code, "Other")
                    except Exception:
                        key_val = "Other"
            elif cluster_type == 'country':
                key_val = (row.get('country_code') or 'Unassigned Country').strip().upper()
            elif cluster_type == 'state':
                state_val = (row.get('state') or '').strip()
                country_val = (row.get('country_code') or '').strip().upper()
                key_val = f"{state_val}, {country_val}" if state_val else 'Unassigned State'
            elif cluster_type == 'city':
                city_val = (row.get('city') or '').strip()
                state_val = (row.get('state') or '').strip()
                country_val = (row.get('country_code') or '').strip().upper()
                key_val = f"{city_val}, {state_val}, {country_val}" if city_val else 'Unassigned City'
            elif cluster_type == 'postal code':
                postal_val = (row.get('postal_code') or '').strip()
                key_val = postal_val if postal_val else 'Unassigned Postal Code'
            else:
                key_val = 'Unassigned'

            if key_val not in groups:
                groups[key_val] = {'lats': [], 'lons': [], 'users': []}
            
            groups[key_val]['lats'].append(lat)
            groups[key_val]['lons'].append(lon)
            
            if username not in groups[key_val]['users']:
                groups[key_val]['users'].append(username)
                
        markers = []
        for name, data in groups.items():
            if data['lats'] and data['lons']:
                avg_lat = sum(data['lats']) / len(data['lats'])
                avg_lon = sum(data['lons']) / len(data['lons'])
                user_list = data['users']
                count = len(user_list)
                
                markers.append({
                    'lat': avg_lat,
                    'lon': avg_lon,
                    'color': get_marker_color(count),
                    'scale': get_marker_scale(count),
                    'title': f"{str(name).title()} ({count} users)",
                    'users': user_list
                })
        return markers

    # --- 2. Radial Distance Grouping (Miles or Kilometers) ---
    elif cluster_type in ['miles', 'kilometers', 'mi', 'km']:
        try:
            radius = float(distance_value or 10)
        except (TypeError, ValueError):
            radius = 10.0
            
        radius_km = radius * 1.60934 if cluster_type in ['miles', 'mi'] else radius
        clusters = []
        
        for row in all_items:
            lat = row.get('latitude')
            lon = row.get('longitude')
            username = row.get('user_name', 'Unknown User')
            
            if lat is None or lon is None:
                continue
                
            lat, lon = float(lat), float(lon)
            added_to_cluster = False
            
            for cluster in clusters:
                dist = calculate_haversine_distance_km(cluster['lat'], cluster['lon'], lat, lon)
                if dist <= radius_km:
                    if username not in cluster['users']:
                        cluster['users'].append(username)
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
                    'users': [username]
                })
                
        markers = []
        unit_label = 'miles' if cluster_type in ['miles', 'mi'] else 'km'
        for i, cluster in enumerate(clusters, 1):
            user_list = cluster['users']
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
        return get_map_markers_with_privacy_view(active_record_id=active_record_id)


@anvil.server.callable
def save_map_item(record_data):
    country = record_data.get('country_code')
    state = record_data.get('state')
    city = record_data.get('city')
    address_1 = record_data.get('address_1')
    address_2 = record_data.get('address_2')
    postal_code = record_data.get('postal_code')
    user_name = record_data.get('user_name')

    query_parts = [address_1, address_2, city, state, country, postal_code]
    query_string = ", ".join([str(p) for p in query_parts if p])

    lat = record_data.get('latitude')
    lon = record_data.get('longitude')
    formatted_address = record_data.get('formatted_address', '')

    try:
        if query_string.strip():
            location = geolocator.geocode(query_string)
            if location:
                lat = location.latitude
                lon = location.longitude
                formatted_address = location.address
    except Exception as e:
        pass

    current_time = datetime.datetime.now()
    generated_id = str(uuid.uuid4())

    app_tables.mapitems.add_row(
        id=generated_id,
        user_name=user_name,
        country_code=country,
        state=state,
        city=city,
        postal_code=postal_code,
        address_1=address_1,
        address_2=address_2,
        latitude=lat,
        longitude=lon,
        formatted_address=formatted_address,
        date_time=current_time
    )
    return generated_id


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



