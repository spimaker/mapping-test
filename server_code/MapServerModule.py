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

# Master region lookup: maps lowercase codes AND full names 
# to (Database Code, Nominatim Geocode String)
REGION_MAPPINGS = {
  # --- US States ---
  "al": ("AL", "Alabama, USA"), "alabama": ("AL", "Alabama, USA"),
  "ak": ("AK", "Alaska, USA"), "alaska": ("AK", "Alaska, USA"),
  "az": ("AZ", "Arizona, USA"), "arizona": ("AZ", "Arizona, USA"),
  "ar": ("AR", "Arkansas, USA"), "arkansas": ("AR", "Arkansas, USA"),
  "ca": ("CA", "California, USA"), "california": ("CA", "California, USA"),
  "co": ("CO", "Colorado, USA"), "colorado": ("CO", "Colorado, USA"),
  "ct": ("CT", "Connecticut, USA"), "connecticut": ("CT", "Connecticut, USA"),
  "de": ("DE", "Delaware, USA"), "delaware": ("DE", "Delaware, USA"),
  "fl": ("FL", "Florida, USA"), "florida": ("FL", "Florida, USA"),
  "ga": ("GA", "Georgia, USA"), "georgia": ("GA", "Georgia, USA"),
  "hi": ("HI", "Hawaii, USA"), "hawaii": ("HI", "Hawaii, USA"),
  "id": ("ID", "Idaho, USA"), "idaho": ("ID", "Idaho, USA"),
  "il": ("IL", "Illinois, USA"), "illinois": ("IL", "Illinois, USA"),
  "in": ("IN", "Indiana, USA"), "indiana": ("IN", "Indiana, USA"),
  "ia": ("IA", "Iowa, USA"), "iowa": ("IA", "Iowa, USA"),
  "ks": ("KS", "Kansas, USA"), "kansas": ("KS", "Kansas, USA"),
  "ky": ("KY", "Kentucky, USA"), "kentucky": ("KY", "Kentucky, USA"),
  "la": ("LA", "Louisiana, USA"), "louisiana": ("LA", "Louisiana, USA"),
  "me": ("ME", "Maine, USA"), "maine": ("ME", "Maine, USA"),
  "md": ("MD", "Maryland, USA"), "maryland": ("MD", "Maryland, USA"),
  "ma": ("MA", "Massachusetts, USA"), "massachusetts": ("MA", "Massachusetts, USA"),
  "mi": ("MI", "Michigan, USA"), "michigan": ("MI", "Michigan, USA"),
  "mn": ("MN", "Minnesota, USA"), "minnesota": ("MN", "Minnesota, USA"),
  "ms": ("MS", "Mississippi, USA"), "mississippi": ("MS", "Mississippi, USA"),
  "mo": ("MO", "Missouri, USA"), "missouri": ("MO", "Missouri, USA"),
  "mt": ("MT", "Montana, USA"), "montana": ("MT", "Montana, USA"),
  "ne": ("NE", "Nebraska, USA"), "nebraska": ("NE", "Nebraska, USA"),
  "nv": ("NV", "Nevada, USA"), "nevada": ("NV", "Nevada, USA"),
  "nh": ("NH", "New Hampshire, USA"), "new hampshire": ("NH", "New Hampshire, USA"),
  "nj": ("NJ", "New Jersey, USA"), "new jersey": ("NJ", "New Jersey, USA"),
  "nm": ("NM", "New Mexico, USA"), "new mexico": ("NM", "New Mexico, USA"),
  "ny": ("NY", "New York, USA"), "new york": ("NY", "New York, USA"),
  "nc": ("NC", "North Carolina, USA"), "north carolina": ("NC", "North Carolina, USA"),
  "nd": ("ND", "North Dakota, USA"), "north dakota": ("ND", "North Dakota, USA"),
  "oh": ("OH", "Ohio, USA"), "ohio": ("OH", "Ohio, USA"),
  "ok": ("OK", "Oklahoma, USA"), "oklahoma": ("OK", "Oklahoma, USA"),
  "or": ("OR", "Oregon, USA"), "oregon": ("OR", "Oregon, USA"),
  "pa": ("PA", "Pennsylvania, USA"), "pennsylvania": ("PA", "Pennsylvania, USA"),
  "ri": ("RI", "Rhode Island, USA"), "rhode island": ("RI", "Rhode Island, USA"),
  "sc": ("SC", "South Carolina, USA"), "south carolina": ("SC", "South Carolina, USA"),
  "sd": ("SD", "South Dakota, USA"), "south dakota": ("SD", "South Dakota, USA"),
  "tn": ("TN", "Tennessee, USA"), "tennessee": ("TN", "Tennessee, USA"),
  "tx": ("TX", "Texas, USA"), "texas": ("TX", "Texas, USA"),
  "ut": ("UT", "Utah, USA"), "utah": ("UT", "Utah, USA"),
  "vt": ("VT", "Vermont, USA"), "vermont": ("VT", "Vermont, USA"),
  "va": ("VA", "Virginia, USA"), "virginia": ("VA", "Virginia, USA"),
  "wa": ("WA", "Washington, USA"), "washington": ("WA", "Washington, USA"),
  "wv": ("WV", "West Virginia, USA"), "west virginia": ("WV", "West Virginia, USA"),
  "wi": ("WI", "Wisconsin, USA"), "wisconsin": ("WI", "Wisconsin, USA"),
  "wy": ("WY", "Wyoming, USA"), "wyoming": ("WY", "Wyoming, USA"),
  "dc": ("DC", "District of Columbia, USA"), "district of columbia": ("DC", "District of Columbia, USA"),

  # --- Canadian Provinces & Territories ---
  "ab": ("AB", "Alberta, Canada"), "alberta": ("AB", "Alberta, Canada"),
  "bc": ("BC", "British Columbia, Canada"), "british columbia": ("BC", "British Columbia, Canada"),
  "mb": ("MB", "Manitoba, Canada"), "manitoba": ("MB", "Manitoba, Canada"),
  "nb": ("NB", "New Brunswick, Canada"), "new brunswick": ("NB", "New Brunswick, Canada"),
  "nl": ("NL", "Newfoundland and Labrador, Canada"), "newfoundland and labrador": ("NL", "Newfoundland and Labrador, Canada"),
  "ns": ("NS", "Nova Scotia, Canada"), "nova scotia": ("NS", "Nova Scotia, Canada"),
  "on": ("ON", "Ontario, Canada"), "ontario": ("ON", "Ontario, Canada"),
  "pe": ("PE", "Prince Edward Island, Canada"), "prince edward island": ("PE", "Prince Edward Island, Canada"),
  "qc": ("QC", "Quebec, Canada"), "quebec": ("QC", "Quebec, Canada"),
  "sk": ("SK", "Saskatchewan, Canada"), "saskatchewan": ("SK", "Saskatchewan, Canada"),
  "yt": ("YT", "Yukon, Canada"), "yukon": ("YT", "Yukon, Canada"),

  # --- Australian States & Territories ---
  "nsw": ("NSW", "New South Wales, Australia"), "new south wales": ("NSW", "New South Wales, Australia"),
  "vic": ("VIC", "Victoria, Australia"), "victoria": ("VIC", "Victoria, Australia"),
  "qld": ("QLD", "Queensland, Australia"), "queensland": ("QLD", "Queensland, Australia"),
  "sa": ("SA", "South Australia, Australia"), "south australia": ("SA", "South Australia, Australia"),
  "tas": ("TAS", "Tasmania, Australia"), "tasmania": ("TAS", "Tasmania, Australia"),
  "act": ("ACT", "Australian Capital Territory, Australia"), "australian capital territory": ("ACT", "Australian Capital Territory, Australia")
}

def standardize_region(raw_input):
  """
    Takes any user state input (e.g. 'ok', 'OK', 'Oklahoma'), 
    returns a tuple: (db_stored_code, nominatim_geocode_string).
    """
  if not raw_input:
    return "", ""

  cleaned = raw_input.strip().lower()
  if cleaned in REGION_MAPPINGS:
    return REGION_MAPPINGS[cleaned]

  fallback_code = raw_input.strip().upper() if len(raw_input.strip()) <= 3 else raw_input.strip().title()
  return fallback_code, raw_input.strip()


@anvil.server.callable
def get_country_list():
  countries = [(country.name, country.alpha_2) for country in pycountry.countries]
  return sorted(countries, key=lambda x: x[0])


@anvil.server.callable
def save_map_item(form_data):
  user_name = form_data.get('User_Name_Value')
  address_1 = form_data.get('Address1_Value')
  city = form_data.get('City_Value')
  postal_code = form_data.get('Postal_Code_Value')
  country_code = form_data.get('Country_Code_Value')

  raw_state = form_data.get('State_Province_Region_Value', '')
  db_state, geocode_state = standardize_region(raw_state)

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

  lat = form_data.get('Latitude_Value')
  lon = form_data.get('Longitude_Value')
  formatted_address = form_data.get('Formatted_Address_Value', '')

  if not lat or not lon:
    try:
      geolocated_list = geocode_multiple_addresses(
        addr1=address_1,
        city=city,
        state_str=geocode_state,
        postal=postal_code,
        country_code=country_code
      )
      if geolocated_list:
        lat = geolocated_list[0]['latitude']
        lon = geolocated_list[0]['longitude']
        formatted_address = geolocated_list[0]['display_name']
    except Exception as e:
      print(f"Structured saving geocoding error: {e}")

  record_id = str(uuid.uuid4())[:8].upper()

  app_tables.mapitems.add_row(
    id=record_id,
    user_name=user_name,
    address_1=address_1,
    address_2=form_data.get('Address2_Value'),
    city=city,
    state=db_state,
    postal_code=postal_code,
    country_code=country_code,
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


@anvil.server.callable
def get_clustered_data(cluster_type='miles', threshold=25):
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
  if None in (lat1, lon1, lat2, lon2):
    return float('inf')

  R = 3958.8  
  dlat = math.radians(lat2 - lat1)
  dlon = math.radians(lon2 - lon1)
  a = (math.sin(dlat / 2) ** 2 +
       math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
       math.sin(dlon / 2) ** 2)
  c = 2 * math.asin(math.sqrt(a))
  return R * c


def geocode_multiple_addresses(addr1="", city="", state_str="", postal="", country_code=""):
  """
  Geocodes using Nominatim's structured parameters (street, city, state, postalcode) 
  instead of free-form strings, completely eliminating business and POI matches.
  """
  try:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'AnvilMapApp/1.0'}

    params = {
      'format': 'json',
      'addressdetails': 1,
      'limit': 5
    }

    if addr1:
      params['street'] = addr1
    if city:
      params['city'] = city
    if state_str:
      params['state'] = state_str
    if postal:
      params['postalcode'] = postal

    if country_code:
      params['countrycodes'] = country_code.lower()

    response = requests.get(url, params=params, headers=headers, timeout=5)
    data = response.json()

    results = []
    for item in data:
      addr = item.get('address', {})
      res_city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county') or ''
      res_state = addr.get('state', '')
      res_country = addr.get('country', '')

      results.append({
        'display_name': item.get('display_name'),
        'city': res_city,
        'state': res_state,
        'country': res_country,
        'latitude': float(item['lat']),
        'longitude': float(item['lon'])
      })

    return results
  except Exception as e:
    print(f"Structured geocoding error: {e}")
    return []


@anvil.server.callable
def search_map_items_by_fields(search_data):
  addr1 = (search_data.get('Address1_Value') or '').strip()
  city = (search_data.get('City_Value') or '').strip()
  raw_state = (search_data.get('State_Province_Region_Value') or '').strip()
  postal = (search_data.get('Postal_Code_Value') or '').strip()
  country = (search_data.get('Country_Code_Value') or '').strip()

  db_state_code, geocode_state_str = standardize_region(raw_state)

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
    search_args = {}
    if addr1:
      search_args['address_1'] = q.ilike(f"%{addr1}%")
    if city:
      search_args['city'] = q.ilike(f"%{city}%")
    if raw_state:
      search_args['state'] = q.any_of(
        q.ilike(f"%{db_state_code}%"), 
        q.ilike(f"%{raw_state}%")
      )
    if postal:
      search_args['postal_code'] = q.ilike(f"%{postal}%")
    if country:
      search_args['country_code'] = country

    matching_rows = list(app_tables.mapitems.search(**search_args)) if search_args else []

    if addr1:
      zoom = 15
    elif city or postal:
      zoom = 12
    elif raw_state:
      zoom = 8
    elif country:
      zoom = 5

    if not matching_rows and any([addr1, city, raw_state, postal, country]):
      geocoded_results = geocode_multiple_addresses(
        addr1=addr1,
        city=city,
        state_str=geocode_state_str,
        postal=postal,
        country_code=country
      )

      if len(geocoded_results) > 1:
        return {
          'status': 'disambiguation_needed',
          'options': geocoded_results
        }

      if not geocoded_results and (city or raw_state or addr1):
        raise Exception("Could not locate this location automatically within the selected country.")

      if geocoded_results:
        center_lat = geocoded_results[0]['latitude']
        center_lon = geocoded_results[0]['longitude']

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