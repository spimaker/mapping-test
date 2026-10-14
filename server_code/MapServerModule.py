import anvil.email
import anvil.users
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
# to (Database Code, Clean State/Province Name for Nominatim)
REGION_MAPPINGS = {
  # --- US States ---
  "al": ("AL", "Alabama"), "alabama": ("AL", "Alabama"),
  "ak": ("AK", "Alaska"), "alaska": ("AK", "Alaska"),
  "az": ("AZ", "Arizona"), "arizona": ("AZ", "Arizona"),
  "ar": ("AR", "Arkansas"), "arkansas": ("AR", "Arkansas"),
  "ca": ("CA", "California"), "california": ("CA", "California"),
  "co": ("CO", "Colorado"), "colorado": ("CO", "Colorado"),
  "ct": ("CT", "Connecticut"), "connecticut": ("CT", "Connecticut"),
  "de": ("DE", "Delaware"), "delaware": ("DE", "Delaware"),
  "fl": ("FL", "Florida"), "florida": ("FL", "Florida"),
  "ga": ("GA", "Georgia"), "georgia": ("GA", "Georgia"),
  "hi": ("HI", "Hawaii"), "hawaii": ("HI", "Hawaii"),
  "id": ("ID", "Idaho"), "idaho": ("ID", "Idaho"),
  "il": ("IL", "Illinois"), "illinois": ("IL", "Illinois"),
  "in": ("IN", "Indiana"), "indiana": ("IN", "Indiana"),
  "ia": ("IA", "Iowa"), "iowa": ("IA", "Iowa"),
  "ks": ("KS", "Kansas"), "kansas": ("KS", "Kansas"),
  "ky": ("KY", "Kentucky"), "kentucky": ("KY", "Kentucky"),
  "la": ("LA", "Louisiana"), "louisiana": ("LA", "Louisiana"),
  "me": ("ME", "Maine"), "maine": ("ME", "Maine"),
  "md": ("MD", "Maryland"), "maryland": ("MD", "Maryland"),
  "ma": ("MA", "Massachusetts"), "massachusetts": ("MA", "Massachusetts"),
  "mi": ("MI", "Michigan"), "michigan": ("MI", "Michigan"),
  "mn": ("MN", "Minnesota"), "minnesota": ("MN", "Minnesota"),
  "ms": ("MS", "Mississippi"), "mississippi": ("MS", "Mississippi"),
  "mo": ("MO", "Missouri"), "missouri": ("MO", "Missouri"),
  "mt": ("MT", "Montana"), "montana": ("MT", "Montana"),
  "ne": ("NE", "Nebraska"), "nebraska": ("NE", "Nebraska"),
  "nv": ("NV", "Nevada"), "nevada": ("NV", "Nevada"),
  "nh": ("NH", "New Hampshire"), "new hampshire": ("NH", "New Hampshire"),
  "nj": ("NJ", "New Jersey"), "new jersey": ("NJ", "New Jersey"),
  "nm": ("NM", "New Mexico"), "new mexico": ("NM", "New Mexico"),
  "ny": ("NY", "New York"), "new york": ("NY", "New York"),
  "nc": ("NC", "North Carolina"), "north carolina": ("NC", "North Carolina"),
  "nd": ("ND", "North Dakota"), "north dakota": ("ND", "North Dakota"),
  "oh": ("OH", "Ohio"), "ohio": ("OH", "Ohio"),
  "ok": ("OK", "Oklahoma"), "oklahoma": ("OK", "Oklahoma"),
  "or": ("OR", "Oregon"), "oregon": ("OR", "Oregon"),
  "pa": ("PA", "Pennsylvania"), "pennsylvania": ("PA", "Pennsylvania"),
  "ri": ("RI", "Rhode Island"), "rhode island": ("RI", "Rhode Island"),
  "sc": ("SC", "South Carolina"), "south carolina": ("SC", "South Carolina"),
  "sd": ("SD", "South Dakota"), "south dakota": ("SD", "South Dakota"),
  "tn": ("TN", "Tennessee"), "tennessee": ("TN", "Tennessee"),
  "tx": ("TX", "Texas"), "texas": ("TX", "Texas"),
  "ut": ("UT", "Utah"), "utah": ("UT", "Utah"),
  "vt": ("VT", "Vermont"), "vermont": ("VT", "Vermont"),
  "va": ("VA", "Virginia"), "virginia": ("VA", "Virginia"),
  "wa": ("WA", "Washington"), "washington": ("WA", "Washington"),
  "wv": ("WV", "West Virginia"), "west virginia": ("WV", "West Virginia"),
  "wi": ("WI", "Wisconsin"), "wisconsin": ("WI", "Wisconsin"),
  "wy": ("WY", "Wyoming"), "wyoming": ("WY", "Wyoming"),
  "dc": ("DC", "District of Columbia"), "district of columbia": ("DC", "District of Columbia"),

  # --- Canadian Provinces & Territories ---
  "ab": ("AB", "Alberta"), "alberta": ("AB", "Alberta"),
  "bc": ("BC", "British Columbia"), "british columbia": ("BC", "British Columbia"),
  "mb": ("MB", "Manitoba"), "manitoba": ("MB", "Manitoba"),
  "nb": ("NB", "New Brunswick"), "new brunswick": ("NB", "New Brunswick"),
  "nl": ("NL", "Newfoundland and Labrador"), "newfoundland and labrador": ("NL", "Newfoundland and Labrador"),
  "ns": ("NS", "Nova Scotia"), "nova scotia": ("NS", "Nova Scotia"),
  "on": ("ON", "Ontario"), "ontario": ("ON", "Ontario"),
  "pe": ("PE", "Prince Edward Island"), "prince edward island": ("PE", "Prince Edward Island"),
  "qc": ("QC", "Quebec"), "quebec": ("QC", "Quebec"),
  "sk": ("SK", "Saskatchewan"), "saskatchewan": ("SK", "Saskatchewan"),
  "yt": ("YT", "Yukon"), "yukon": ("YT", "Yukon"),

  # --- Australian States & Territories ---
  "nsw": ("NSW", "New South Wales"), "new south wales": ("NSW", "New South Wales"),
  "vic": ("VIC", "Victoria"), "victoria": ("VIC", "Victoria"),
  "qld": ("QLD", "Queensland"), "queensland": ("QLD", "Queensland"),
  "sa": ("SA", "South Australia"), "south australia": ("SA", "South Australia"),
  "tas": ("TAS", "Tasmania"), "tasmania": ("TAS", "Tasmania"),
  "act": ("ACT", "Australian Capital Territory"), "australian capital territory": ("ACT", "Australian Capital Territory")
}

def standardize_region(raw_input):
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
  Geocodes using structured parameters first. If structured returns nothing 
  (e.g., for counties like Merseyside or regions like Britain), it falls back 
  to a robust free-form query restricted by country code.
  """
  try:
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'AnvilMapApp/1.0'}

    # --- ATTEMPT 1: Structured Query ---
    params = {
      'format': 'json',
      'addressdetails': 1,
      'limit': 5
    }
    if addr1: params['street'] = addr1
    if city: params['city'] = city
    if state_str: params['state'] = state_str
    if postal: params['postalcode'] = postal
    if country_code: params['countrycodes'] = country_code.lower()

    response = requests.get(url, params=params, headers=headers, timeout=5)
    data = response.json()

    # --- ATTEMPT 2: Free-form Fallback if Structured yields 0 results ---
    if not data and (city or state_str or postal or addr1):
      query_parts = [p for p in [addr1, city, state_str, postal] if p]
      free_query = ", ".join(query_parts)
      fallback_params = {
        'q': free_query,
        'format': 'json',
        'addressdetails': 1,
        'layer': 'address',
        'limit': 5
      }
      if country_code:
        fallback_params['countrycodes'] = country_code.lower()

      response = requests.get(url, params=fallback_params, headers=headers, timeout=5)
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
    print(f"Geocoding error: {e}")
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