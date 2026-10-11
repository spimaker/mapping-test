# This is a server module. It runs on the Anvil server,
# rather than in the user's browser.
#
# To allow anvil.server.call() to call functions here, we mark
# them with @anvil.server.callable.
#
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import pycountry
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import uuid
import requests
import math


#
# get_country_list
#

@anvil.server.callable
def get_country_list():
  countries = [(country.name, country.alpha_2) for country in pycountry.countries]
  return sorted(countries, key=lambda x: x[0])

#
# save_map_item
#
  
@anvil.server.callable
def save_map_item(form_data):
  user_name = form_data.get('User_Name_Value')
  address_1 = form_data.get('Address1_Value')
  city = form_data.get('City_Value')
  postal_code = form_data.get('Postal_Code_Value')

  # Check for an existing record matching key identifiers
  existing_record = app_tables.mapitems.get(
    user_name=user_name,
    address_1=address_1,
    city=city
  )

  if existing_record:
    # If it's a duplicate, still fetch all items so they display on the map
    all_items = app_tables.mapitems.search()
    items_list = [{
      'id': row['id'],
      'latitude': row['latitude'],
      'longitude': row['longitude'],
      'formatted_address': row['formatted_address']
    } for row in all_items if row['latitude'] and row['longitude']]

    return {
      'status': 'duplicate',
      'id': existing_record['id'],
      'latitude': existing_record['latitude'],
      'longitude': existing_record['longitude'],
      'formatted_address': existing_record['formatted_address'],
      'all_items': items_list
    }

    # Construct full address string for geocoding
  address_parts = [
    address_1,
    form_data.get('Address2_Value', ''),
    city,
    form_data.get('State_Province_Region_Value', ''),
    postal_code,
    form_data.get('Country_Code_Value', '')
  ]
  full_address = ", ".join([p for p in address_parts if p])

  lat = form_data.get('Latitude_Value')
  lon = form_data.get('Longitude_Value')
  formatted_address = form_data.get('Formatted_Address_Value', full_address)

  if not lat or not lon:
    try:
      geolocator = Nominatim(user_agent="anvil_mapping_app")
      location = geolocator.geocode(full_address)
      if location:
        lat = location.latitude
        lon = location.longitude
        formatted_address = location.address
    except Exception as e:
      print(f"Geocoding error: {e}")

    # Generate a unique ID and save row
  record_id = str(uuid.uuid4())[:8].upper()

  app_tables.mapitems.add_row(
    id=record_id,
    user_name=user_name,
    address_1=address_1,
    address_2=form_data.get('Address2_Value'),
    city=city,
    state=form_data.get('State_Province_Region_Value'),
    postal_code=postal_code,
    country_code=form_data.get('Country_Code_Value'),
    latitude=lat,
    longitude=lon,
    formatted_address=formatted_address
  )

  # Fetch all items from the database to return to the client
  all_items = app_tables.mapitems.search()
  items_list = [{
    'id': row['id'],
    'latitude': row['latitude'],
    'longitude': row['longitude'],
    'formatted_address': row['formatted_address']
  } for row in all_items if row['latitude'] and row['longitude']]

  return {
    'status': 'saved',
    'id': record_id,
    'latitude': lat,
    'longitude': lon,
    'formatted_address': formatted_address,
    'all_items': items_list
  }
#
# get_clustered_data
#

@anvil.server.callable
def get_clustered_data(cluster_type, threshold=None):
  rows = list(app_tables.mapitems.search())
  clusters = []

  COLOR_MAP = {
    'miles': '#90EE90',       # Light Green
    'kilometers': '#006400',  # Dark Green
    'postal': '#1E90FF',      # Blue (Updated from postal_code)
    'city': '#FFD700',        # Yellow
    'state': '#FFA500',       # Orange
    'country': '#FF0000'      # Red
  }

  # Fixed: Changed 'postal_code' to 'postal' to match client dropdown value
  if cluster_type in ['postal', 'city', 'state', 'country']:
    field_mapping = {
      'postal': 'postal_code',
      'city': 'city',
      'state': 'state',
      'country': 'country_code'
    }
    type_code_mapping = {
      'postal': 'Post',
      'city': 'City',
      'state': 'St',
      'country': 'Ctry'
    }

    key_field = field_mapping[cluster_type]
    sub_label_code = type_code_mapping[cluster_type]

    groups = {}
    for row in rows:
      val = row[key_field] or "Unknown"
      if val not in groups:
        groups[val] = []
      groups[val].append(row)

    for group_key, group_rows in groups.items():
      valid_rows = [r for r in group_rows if r['latitude'] and r['longitude']]
      if not valid_rows:
        continue

      # Centroid calculation (already correct in your code)
      avg_lat = sum(r['latitude'] for r in valid_rows) / len(valid_rows)
      avg_lon = sum(r['longitude'] for r in valid_rows) / len(valid_rows)

      clusters.append({
        'label': f"{cluster_type.capitalize()}: {group_key}",
        'latitude': avg_lat,
        'longitude': avg_lon,
        'count': len(valid_rows),
        'sub_label': sub_label_code,
        'usernames': [r['user_name'] for r in valid_rows if r['user_name']],
        'color': COLOR_MAP.get(cluster_type, '#0000FF')
      })

  elif cluster_type in ['miles', 'kilometers']:
    max_dist = float(threshold) if threshold else 25.0
    unit_label = "Mi" if cluster_type == 'miles' else "Km"
    perimeter_str = f"{int(max_dist)} {unit_label}"

    ungrouped = [r for r in rows if r['latitude'] and r['longitude']]

    while ungrouped:
      seed = ungrouped.pop(0)
      seed_coords = (seed['latitude'], seed['longitude'])
      cluster_rows = [seed]

      remaining = []
      for r in ungrouped:
        r_coords = (r['latitude'], r['longitude'])
        dist = geodesic(seed_coords, r_coords).miles if cluster_type == 'miles' else geodesic(seed_coords, r_coords).kilometers

        if dist <= max_dist:
          cluster_rows.append(r)
        else:
          remaining.append(r)
      ungrouped = remaining

      avg_lat = sum(r['latitude'] for r in cluster_rows) / len(cluster_rows)
      avg_lon = sum(r['longitude'] for r in cluster_rows) / len(cluster_rows)

      color_key = 'miles' if cluster_type == 'miles' else 'kilometers'
      clusters.append({
        'label': f"Radius Cluster ({perimeter_str})",
        'latitude': avg_lat,
        'longitude': avg_lon,
        'count': len(cluster_rows),
        'sub_label': perimeter_str,
        'usernames': [r['user_name'] for r in cluster_rows if r['user_name']],
        'color': COLOR_MAP.get(color_key, '#006400')
      })

  return clusters

import requests
import math

def calculate_distance_miles(lat1, lon1, lat2, lon2):
  """Calculate the great-circle distance between two points on the Earth in miles."""
  if None in (lat1, lon1, lat2, lon2):
    return float('inf')

  R = 3958.8  # Radius of the Earth in miles
  dlat = math.radians(lat2 - lat1)
  dlon = math.radians(lon2 - lon1)
  a = (math.sin(dlat / 2) ** 2 +
       math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
       math.sin(dlon / 2) ** 2)
  c = 2 * math.asin(math.sqrt(a))
  return R * c

def geocode_address_string(address_str):
  """Geocodes an address string using OpenStreetMap Nominatim (free, no API key required)."""
  try:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'AnvilMapApp/1.0'}
    params = {'q': address_str, 'format': 'json', 'limit': 1}
    response = requests.get(url, params=params, headers=headers, timeout=5)
    data = response.json()
    if data:
      return float(data[0]['lat']), float(data[0]['lon'])
  except Exception as e:
    print(f"Geocoding error: {e}")
  return None, None

@anvil.server.callable
def search_map_items_by_fields(search_data):
  """
    1. Tries exact/partial text match.
    2. If 0 results are found, geocodes the input and returns all records within 10 miles.
    """
  print("--- SEARCH DEBUG ---")
  print("Received search_data:", search_data)

  addr1 = search_data.get('Address1_Value', '').strip()
  city = search_data.get('City_Value', '').strip()
  state = search_data.get('State_Province_Region_Value', '').strip()
  postal = search_data.get('Postal_Code_Value', '').strip()
  country = search_data.get('Country_Code_Value', '').strip()

  # Step 1: Try direct text search first
  search_args = {}
  if addr1:
    search_args['address_1'] = q.ilike(f"%{addr1}%")
  if city:
    search_args['city'] = q.ilike(f"%{city}%")
  if state:
    search_args['state'] = q.ilike(f"%{state}%")
  if postal:
    search_args['postal_code'] = q.ilike(f"%{postal}%")
  if country:
    search_args['country_code'] = country

  matching_rows = list(app_tables.mapitems.search(**search_args)) if search_args else []
  print(f"Direct text search found {len(matching_rows)} matching rows.")

  center_lat = None
  center_lon = None
  zoom = 11

  # Step 2: Fallback to 10-mile radius search if direct text search found nothing and we have address info
  if not matching_rows and (addr1 or city):
    # Build full address string to geocode
    address_parts = [p for p in [addr1, city, state, postal, country] if p]
    full_query = ", ".join(address_parts)
    print(f"Direct match failed. Geocoding query: '{full_query}'")

    center_lat, center_lon = geocode_address_string(full_query)

    if center_lat and center_lon:
      print(f"Geocoded successfully to: {center_lat}, {center_lon}")
      # Scan all table items and find those within 10 miles
      all_items = app_tables.mapitems.search()
      for row in all_items:
        r_lat = row.get('latitude') or row.get('Latitude_Value')
        r_lon = row.get('longitude') or row.get('Longitude_Value')
        if r_lat and r_lon:
          dist = calculate_distance_miles(center_lat, center_lon, r_lat, r_lon)
          if dist <= 10:  # Within 10-mile radius
            matching_rows.append(row)
      print(f"Radius search found {len(matching_rows)} records within 10 miles.")
      zoom = 12
    else:
      print("Geocoding failed to return coordinates.")

    # Format results into clusters
  clusters = []
  valid_coords = []
  coord_map = {}

  for row in matching_rows:
    lat = row.get('latitude') or row.get('Latitude_Value')
    lon = row.get('longitude') or row.get('Longitude_Value')

    if lat is not None and lon is not None:
      valid_coords.append((lat, lon))
      key = (round(lat, 5), round(lon, 5))
      if key not in coord_map:
        coord_map[key] = {
          'latitude': lat,
          'longitude': lon,
          'usernames': []
        }
      username = row.get('user_name') or row.get('User_Name_Value', 'Unknown User')
      if username not in coord_map[key]['usernames']:
        coord_map[key]['usernames'].append(username)

  for key, data in coord_map.items():
    count = len(data['usernames'])
    clusters.append({
      'latitude': data['latitude'],
      'longitude': data['longitude'],
      'count': count,
      'color': '#34A853',
      'label': f"Search Match ({count} records)",
      'usernames': data['usernames'],
      'sub_label': None
    })

    # If we didn't get center_lat from geocoding, calculate average from results
  if not center_lat and valid_coords:
    center_lat = sum(lat for lat, lon in valid_coords) / len(valid_coords)
    center_lon = sum(lon for lat, lon in valid_coords) / len(valid_coords)
    if addr1:
      zoom = 15
    elif city or postal:
      zoom = 12

  return {
    'clusters': clusters,
    'latitude': center_lat,
    'longitude': center_lon,
    'zoom': zoom
  }