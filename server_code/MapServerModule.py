import anvil.email
import anvil.users
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

# Comprehensive dictionary for short-code regional expansion (US, Canada, Australia)
GLOBAL_REGIONS = {
  # --- US States ---
  "al": "Alabama, USA", "ak": "Alaska, USA", "az": "Arizona, USA", "ar": "Arkansas, USA",
  "ca": "California, USA", "co": "Colorado, USA", "ct": "Connecticut, USA", "de": "Delaware, USA",
  "fl": "Florida, USA", "ga": "Georgia, USA", "hi": "Hawaii, USA", "id": "Idaho, USA",
  "il": "Illinois, USA", "in": "Indiana, USA", "ia": "Iowa, USA", "ks": "Kansas, USA",
  "ky": "Kentucky, USA", "la": "Louisiana, USA", "me": "Maine, USA", "md": "Maryland, USA",
  "ma": "Massachusetts, USA", "mi": "Michigan, USA", "mn": "Minnesota, USA", "ms": "Mississippi, USA",
  "mo": "Missouri, USA", "mt": "Montana, USA", "ne": "Nebraska, USA", "nv": "Nevada, USA",
  "nh": "New Hampshire, USA", "nj": "New Jersey, USA", "nm": "New Mexico, USA", "ny": "New York, USA",
  "nc": "North Carolina, USA", "nd": "North Dakota, USA", "oh": "Ohio, USA", "ok": "Oklahoma, USA",
  "or": "Oregon, USA", "pa": "Pennsylvania, USA", "ri": "Rhode Island, USA", "sc": "South Carolina, USA",
  "sd": "South Dakota, USA", "tn": "Tennessee, USA", "tx": "Texas, USA", "ut": "Utah, USA",
  "vt": "Vermont, USA", "va": "Virginia, USA", "wa": "Washington, USA", "wv": "West Virginia, USA",
  "wi": "Wisconsin, USA", "wy": "Wyoming, USA", "dc": "District of Columbia, USA",

  # --- Canadian Provinces & Territories ---
  "ab": "Alberta, Canada",
  "bc": "British Columbia, Canada",
  "mb": "Manitoba, Canada",
  "nb": "New Brunswick, Canada",
  "nl": "Newfoundland and Labrador, Canada",
  "ns": "Nova Scotia, Canada",
  "on": "Ontario, Canada",
  "pe": "Prince Edward Island, Canada",
  "qc": "Quebec, Canada",
  "sk": "Saskatchewan, Canada",
  "yt": "Yukon, Canada",

  # --- Australian States & Territories ---
  "nsw": "New South Wales, Australia",
  "vic": "Victoria, Australia",
  "qld": "Queensland, Australia",
  "wa": "Western Australia, Australia",
  "sa": "South Australia, Australia",
  "tas": "Tasmania, Australia",
  "act": "Australian Capital Territory, Australia"
}

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
  state_input = form_data.get('State_Province_Region_Value', '')
  # Expand short code if applicable
  cleaned_state = state_input.strip().lower()
  if cleaned_state in GLOBAL_REGIONS:
    state_input = GLOBAL_REGIONS[cleaned_state]

  address_parts = [
    address_1,
    form_data.get('Address2_Value', ''),
    city,
    state_input,
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
def get_clustered_data(cluster_type='miles', threshold=25):
  """
    Returns clustered data globally based on cluster type and threshold,
    without filtering out distant records.
    """
  all_items = list(app_tables.mapitems.search())

  coord_map = {}
  for row in all_items:
    lat = row.get('latitude') or row.get('Latitude_Value')
    lon = row.get('longitude') or row.get('Longitude_Value')

    if lat is not None and lon is not None:
      key = (round(lat, 2), round(lon, 2)) if cluster_type in ['miles', 'kilometers'] else (round(lat, 4), round(lon, 4))

      if key not in coord_map:
        coord_map[key] = {
          'latitude': lat,
          'longitude': lon,
          'usernames': []
        }
      username = row.get('user_name') or row.get('User_Name_Value', 'Unknown User')
      if username not in coord_map[key]['usernames']:
        coord_map[key]['usernames'].append(username)

  clusters = []
  for key, data in coord_map.items():
    count = len(data['usernames'])
    clusters.append({
      'latitude': data['latitude'],
      'longitude': data['longitude'],
      'count': count,
      'color': '#34A853',
      'label': f"Area Cluster ({count} records)",
      'usernames': data['usernames'],
      'sub_label': None
    })

  return clusters


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
  """Geocodes an address string using OpenStreetMap Nominatim."""
  try:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'AnvilMapApp/1.0'}
    params = {'q': address_str, 'format': 'json', 'limit': 1}
    response = requests.get(url, params=params, headers=headers, timeout=5)
    data = response.json()
    if data:
      return float(data[0]['lat']), float(data[0]['lon'])
  except Exception:
    pass
  return None, None


def geocode_multiple_addresses(address_str):
  """Geocodes an address string and returns up to 5 matching options with details."""
  try:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'AnvilMapApp/1.0'}
    params = {'q': address_str, 'format': 'json', 'addressdetails': 1, 'limit': 5}
    response = requests.get(url, params=params, headers=headers, timeout=5)
    data = response.json()
    results = []
    for item in data:
      addr = item.get('address', {})
      city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county') or ''
      state = addr.get('state', '')
      country = addr.get('country', '')
      results.append({
        'display_name': item.get('display_name'),
        'city': city,
        'state': state,
        'country': country,
        'latitude': float(item['lat']),
        'longitude': float(item['lon'])
      })
    return results
  except Exception:
    return []


@anvil.server.callable
def search_map_items_by_fields(search_data):
  addr1 = (search_data.get('Address1_Value') or '').strip()
  city = (search_data.get('City_Value') or '').strip()
  state_raw = (search_data.get('State_Province_Region_Value') or '').strip()
  postal = (search_data.get('Postal_Code_Value') or '').strip()
  country = (search_data.get('Country_Code_Value') or '').strip()

  # Automatically expand short-codes (like 'ok' -> 'Oklahoma, USA')
  cleaned_state = state_raw.lower()
  state = GLOBAL_REGIONS.get(cleaned_state, state_raw)

  # Check if the user already picked a specific location from the disambiguation dialog
  sel_lat = search_data.get('Selected_Latitude')
  sel_lon = search_data.get('Selected_Longitude')

  matching_rows = []
  center_lat = None
  center_lon = None
  zoom = 11

  if sel_lat and sel_lon:
    center_lat = sel_lat
    center_lon = sel_lon
    zoom = 12
  else:
    # Step 1: Try direct text search first
    search_args = {}
    if addr1:
      search_args['address_1'] = q.ilike(f"%{addr1}%")
    if city:
      search_args['city'] = q.ilike(f"%{city}%")
    if state_raw:
      # Search against both raw input and expanded state name in database
      search_args['state'] = q.any_of(q.ilike(f"%{state_raw}%"), q.ilike(f"%{state}%"))
    if postal:
      search_args['postal_code'] = q.ilike(f"%{postal}%")
    if country:
      search_args['country_code'] = country

    matching_rows = list(app_tables.mapitems.search(**search_args)) if search_args else []

    # Determine zoom level
    if addr1:
      zoom = 15
    elif city or postal:
      zoom = 12
    elif state_raw:
      zoom = 8
    elif country:
      zoom = 5

    # Step 2: Geocoding fallback if direct text search found nothing
    if not matching_rows and any([addr1, city, state_raw, postal, country]):
      address_parts = [p for p in [addr1, city, state, postal, country] if p]
      full_query = ", ".join(address_parts)

      geocoded_results = geocode_multiple_addresses(full_query)

      if len(geocoded_results) > 1 and not country:
        return {
          'status': 'disambiguation_needed',
          'options': geocoded_results
        }

      if not geocoded_results and not country and (city or state_raw):
        raise Exception("Could not locate this city and state automatically. Please select a country and try again.")

      if geocoded_results:
        center_lat = geocoded_results[0]['latitude']
        center_lon = geocoded_results[0]['longitude']

  # If we have center coordinates, find records within 10 miles
  if center_lat and center_lon and (addr1 or city or postal or sel_lat):
    all_items = app_tables.mapitems.search()
    for row in all_items:
      r_lat = row.get('latitude') or row.get('Latitude_Value')
      r_lon = row.get('longitude') or row.get('Longitude_Value')
      if r_lat and r_lon:
        dist = calculate_distance_miles(center_lat, center_lon, r_lat, r_lon)
        if dist <= 10:
          if row not in matching_rows:
            matching_rows.append(row)

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

  if not center_lat and valid_coords:
    center_lat = sum(lat for lat, lon in valid_coords) / len(valid_coords)
    center_lon = sum(lon for lat, lon in valid_coords) / len(valid_coords)

  return {
    'status': 'success',
    'clusters': clusters,
    'latitude': center_lat,
    'longitude': center_lon,
    'zoom': zoom
  }