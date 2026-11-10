import math
import uuid
from datetime import datetime, timedelta
import anvil.email
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from country_state_city import City
from country_state_city import State
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import pycountry
import pycountry_convert as pc
import requests


REGION_ORDER = [
    'North America',
    'South America',
    'Europe',
    'Asia',
    'Africa',
    'Oceania',
]

CONTINENT_TO_REGION = {
    'NA': 'North America',
    'SA': 'South America',
    'EU': 'Europe',
    'AS': 'Asia',
    'AF': 'Africa',
    'OC': 'Oceania',
}


@anvil.server.callable
def test_ping():
  return 'pong'


@anvil.server.callable
def get_global_region(country_code):
  """Maps a 2-letter ISO country code to one of the 6 major global regions using pycountry-convert."""
  if not country_code:
    return 'Unassigned'
  try:
    continent_code = pc.country_alpha2_to_continent_code(
        country_code.strip().upper()
    )
    region_mapping = {
        'NA': 'North America',
        'SA': 'South America',
        'EU': 'Europe',
        'AS': 'Asia',
        'AF': 'Africa',
        'OC': 'Oceania',
    }
    return region_mapping.get(continent_code, 'Other / Unassigned')
  except Exception:
    return 'Other / Unassigned'


@anvil.server.callable
def get_country_list():
  """Fetches all countries, groups them by the 6 global regions,

  and returns them sorted strictly by REGION_ORDER, then alphabetically.
  """
  grouped_data = {region: [] for region in REGION_ORDER}
  grouped_data['Other'] = []

  for country in pycountry.countries:
    code = country.alpha_2
    try:
      continent_code = pc.country_alpha2_to_continent_code(code)
      region = CONTINENT_TO_REGION.get(continent_code, 'Other')
    except (KeyError, AttributeError):
      region = 'Other'

    if region in grouped_data:
      grouped_data[region].append({'name': country.name, 'code': code})

  for region in grouped_data:
    grouped_data[region].sort(key=lambda x: x['name'])

  dropdown_items = []
  for region in REGION_ORDER:
    for c in grouped_data[region]:
      dropdown_items.append((f'[{region}] {c["name"]}', c['code']))

  for c in grouped_data['Other']:
    dropdown_items.append((f'[Other] {c["name"]}', c['code']))

  return dropdown_items


@anvil.server.callable
def get_subdivisions_for_country(country_code):
  """Fetches states/provinces using country-state-city, storing both name and code."""
  try:
    if not country_code:
      return []

    states = State.get_states_of_country(country_code)
    if not states:
      return []

    sorted_states = sorted(
        [{'name': s.name} for s in states if s.name],
        key=lambda x: x['name'],
    )
    return [(s['name'], s['name']) for s in sorted_states]
  except Exception as e:
    print(f'Error loading states from country-state-city: {e}')
    return []


@anvil.server.callable
def get_cities_for_state(country_code, state_name):
  """Fetches cities from country-state-city and merges validated entries from ManualCity table."""
  try:
    if not country_code or not state_name:
      return []

    states = State.get_states_of_country(country_code)
    target_state_code = None
    for s in states:
      if s.name.lower() == state_name.lower():
        target_state_code = s.iso_code
        break

    city_names = []
    if target_state_code:
      cities = City.get_cities_of_state(country_code, target_state_code)
      if cities:
        city_names = [c.name for c in cities if hasattr(c, 'name') and c.name]

    # Merge custom validated cities from ManualCity table cache
    try:
      manual_rows = app_tables.manualcity.search(country_code=country_code)
      for row in manual_rows:
        r_state = (row.get('state') or '').strip()
        r_city = (row.get('city') or '').strip()
        if r_state.lower() == state_name.lower() and r_city:
          if r_city not in city_names:
            city_names.append(r_city)
    except Exception as me:
      print(f'Error reading ManualCity table: {me}')

    city_names = sorted(list(set(city_names)))
    return [(name, name) for name in city_names]
  except Exception as e:
    print(f'Error loading cities from country-state-city: {e}')
    return []


def calculate_distance_miles(lat1, lon1, lat2, lon2):
  if None in (lat1, lon1, lat2, lon2):
    return float('inf')

  R = 3958.8
  dlat = math.radians(lat2 - lat1)
  dlon = math.radians(lon2 - lon1)
  a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
      math.radians(lat2)
  ) * math.sin(dlon / 2) ** 2
  c = 2 * math.asin(math.sqrt(a))
  return R * c


def cluster_rows(rows, cluster_type='miles', threshold=25):
  """Aggregates database rows into clusters based on the selected cluster type."""
  if not rows:
    return []

  if cluster_type in ['miles', 'kilometers']:
    clusters = []
    threshold_miles = (
        threshold if cluster_type == 'miles' else threshold / 1.60934
    )

    for row in rows:
      lat = row.get('latitude') or row.get('Latitude_Value')
      lon = row.get('longitude') or row.get('Longitude_Value')
      if lat is None or lon is None:
        continue
      username = row.get('user_name') or row.get(
          'User_Name_Value', 'Unknown User'
      )

      assigned = False
      for cluster in clusters:
        dist = calculate_distance_miles(
            cluster['latitude'], cluster['longitude'], lat, lon
        )
        if dist <= threshold_miles:
          cluster['lats'].append(lat)
          cluster['lons'].append(lon)
          cluster['latitude'] = sum(cluster['lats']) / len(cluster['lats'])
          cluster['longitude'] = sum(cluster['lons']) / len(cluster['lons'])
          if username not in cluster['usernames']:
            cluster['usernames'].append(username)
          assigned = True
          break

      if not assigned:
        clusters.append({
            'latitude': lat,
            'longitude': lon,
            'lats': [lat],
            'lons': [lon],
            'usernames': [username],
        })

    formatted_clusters = []
    for c in clusters:
      count = len(c['usernames'])
      formatted_clusters.append({
          'latitude': c['latitude'],
          'longitude': c['longitude'],
          'count': count,
          'color': '#34A853',
          'label': f'Perimeter Cluster ({count} records)',
          'usernames': c['usernames'],
          'sub_label': None,
      })
    return formatted_clusters

  groups = {}
  for row in rows:
    lat = row.get('latitude') or row.get('Latitude_Value')
    lon = row.get('longitude') or row.get('Longitude_Value')
    if lat is None or lon is None:
      continue

    username = row.get('user_name') or row.get('User_Name_Value', 'Unknown User')

    if cluster_type == 'global_region':
      country_code = (row.get('country_code') or '').strip()
      region_name = get_global_region(country_code)
      key = region_name
      label_name = region_name
    elif cluster_type == 'country':
      country = (row.get('country_code') or '').strip().upper()
      key = country if country else (round(lat, 0), round(lon, 0))
      label_name = country or 'Country Cluster'
    elif cluster_type == 'state':
      state = (row.get('state') or '').strip().upper()
      country = (row.get('country_code') or '').strip().upper()
      key = (country, state) if state else (round(lat, 1), round(lon, 1))
      label_name = state or 'State Cluster'
    elif cluster_type == 'postal':
      postal = (row.get('postal_code') or '').strip().upper()
      country = (row.get('country_code') or '').strip().upper()
      key = (country, postal) if postal else (round(lat, 2), round(lon, 2))
      label_name = postal or 'Postal Cluster'
    elif cluster_type == 'city':
      city = (row.get('city') or '').strip().title()
      state = (row.get('state') or '').strip().upper()
      country = (row.get('country_code') or '').strip().upper()
      key = (country, state, city) if city else (round(lat, 2), round(lon, 2))
      label_name = (
          f'{city}, {state}' if city and state else (city or 'City Cluster')
      )
    else:
      key = (round(lat, 2), round(lon, 2))
      label_name = 'Area Cluster'

    if key not in groups:
      groups[key] = {
          'lats': [],
          'lons': [],
          'usernames': [],
          'label_name': label_name,
      }
    groups[key]['lats'].append(lat)
    groups[key]['lons'].append(lon)
    if username not in groups[key]['usernames']:
      groups[key]['usernames'].append(username)

  clusters = []
  for key, data in groups.items():
    avg_lat = sum(data['lats']) / len(data['lats'])
    avg_lon = sum(data['lons']) / len(data['lons'])
    count = len(data['usernames'])

    clusters.append({
        'latitude': avg_lat,
        'longitude': avg_lon,
        'count': count,
        'color': '#34A853',
        'label': f"{data['label_name']} ({count} records)",
        'usernames': data['usernames'],
        'sub_label': None,
    })

  return clusters


@anvil.server.callable
def get_clustered_data(cluster_type='miles', threshold=25):
  all_items = list(app_tables.mapitems.search())
  return cluster_rows(all_items, cluster_type=cluster_type, threshold=threshold)


@anvil.server.callable
def save_map_item(form_data):
  user_name = form_data.get('User_Name_Value')
  address_1 = (form_data.get('Address1_Value') or '').strip()
  
  city = (form_data.get('Custom_City_Value') or form_data.get('City_Value') or '').strip()
  postal_code = (form_data.get('Postal_Code_Value') or '').strip()
  country_code = (form_data.get('Country_Code_Value') or '').strip()
  db_state = (form_data.get('State_Province_Region_Value') or '').strip()
  is_custom_entry = form_data.get('Is_Custom_City', False)

  if not city:
    return {'status': 'error', 'message': 'City is required.'}

  # --- Strict Geocoding & Spurious Data Verification ---
  geolocated_list = geocode_multiple_addresses(
      addr1=address_1,
      city=city,
      state_str=db_state,
      postal=postal_code,
      country_code=country_code,
  )

  if not geolocated_list:
    return {
        'status': 'error',
        'message': f'Could not verify the location "{address_1}, {city}, {db_state} {postal_code}" as provided. It may be invalid data.'
    }

  best_match = geolocated_list[0]
  lat = best_match.get('latitude')
  lon = best_match.get('longitude')
  formatted_address = best_match.get('display_name', '')

  if lat is None or lon is None:
    return {
        'status': 'error',
        'message': f'Could not verify the location "{address_1}, {city}, {db_state} {postal_code}" as provided. It may be invalid data.'
    }

  # --- Strict Postal Code Validation ---
  if postal_code and best_match.get('postal'):
    res_postal = best_match.get('postal').strip().replace(' ', '')
    user_postal = postal_code.strip().replace(' ', '')
    
    if not res_postal.startswith(user_postal) and not user_postal.startswith(res_postal):
      return {
          'status': 'error',
          'message': f'Postal code mismatch: The postal code "{postal_code}" does not match the geocoded location\'s postal code ("{best_match.get("postal")}").'
      }

  # --- State Validation ---
  res_state = best_match.get('state', '').lower()
  if db_state and res_state and db_state.lower() not in res_state and res_state not in db_state.lower():
    return {
        'status': 'error',
        'message': f'Location mismatch: The address resolves to "{formatted_address}", which does not match your selected state/province.'
    }

  existing_record = app_tables.mapitems.get(
      user_name=user_name, address_1=address_1, city=city
  )

  if existing_record:
    all_items = app_tables.mapitems.search()
    items_list = [{
        'id': row['id'],
        'latitude': row['latitude'],
        'longitude': row['longitude'],
        'formatted_address': row['formatted_address'],
    } for row in all_items if row['latitude'] and row['longitude']]

    return {
        'status': 'duplicate',
        'id': existing_record['id'],
        'latitude': existing_record['latitude'],
        'longitude': existing_record['longitude'],
        'formatted_address': existing_record['formatted_address'],
        'all_items': items_list,
    }

  record_id = str(uuid.uuid4())[:8].upper()

  # Save to main map items table
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
      formatted_address=formatted_address,
      date_time=datetime.utcnow(),
  )

  # Save to ManualCity cache table if it was a validated custom city entry
  if is_custom_entry:
    existing_manual = app_tables.manualcity.get(
        country_code=country_code, state=db_state, city=city
    )
    if not existing_manual:
      max_id = max([r['id'] for r in app_tables.manualcity.search() if r['id'] is not None], default=0)
      new_manual_id = max_id + 1

      app_tables.manualcity.add_row(
          id=new_manual_id,
          country_code=country_code,
          state=db_state,
          city=city,
          latitude=lat,
          longitude=lon,
          date_time=datetime.utcnow()
      )

  all_items = app_tables.mapitems.search()
  items_list = [{
      'id': row['id'],
      'latitude': row['latitude'],
      'longitude': row['longitude'],
      'formatted_address': row['formatted_address'],
  } for row in all_items if row['latitude'] and row['longitude']]

  return {
      'status': 'saved',
      'id': record_id,
      'latitude': lat,
      'longitude': lon,
      'formatted_address': formatted_address,
      'all_items': items_list,
  }


def geocode_multiple_addresses(
    addr1='', city='', state_str='', postal='', country_code=''
):
  try:
    url = 'https://nominatim.openstreetmap.org/search'
    headers = {'User-Agent': 'AnvilMapApp/1.0'}

    params = {'format': 'json', 'addressdetails': 1, 'limit': 5}
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

    response = requests.get(url, params=params, headers=headers, timeout=12)
    data = response.json()

    if not data and (city or state_str or postal or addr1):
      query_parts = [p for p in [addr1, city, state_str, postal] if p]
      free_query = ', '.join(query_parts)
      fallback_params = {
          'q': free_query,
          'format': 'json',
          'addressdetails': 1,
          'layer': 'address',
          'limit': 5,
      }
      if country_code:
        fallback_params['countrycodes'] = country_code.lower()

      response = requests.get(
          url, params=fallback_params, headers=headers, timeout=12
      )
      data = response.json()

    results = []
    for item in data:
      addr = item.get('address', {})
      res_city = (
          addr.get('city')
          or addr.get('town')
          or addr.get('village')
          or addr.get('county')
          or ''
      )
      res_state = addr.get('state', '')
      res_country = addr.get('country', '')
      res_postal = addr.get('postcode', '')

      results.append({
          'display_name': item.get('display_name'),
          'city': res_city,
          'state': res_state,
          'country': res_country,
          'postal': res_postal,
          'latitude': float(item['lat']),
          'longitude': float(item['lon']),
      })

    return results
  except requests.exceptions.Timeout:
    print('Geocoding error: Nominatim request timed out.')
    return []
  except Exception as e:
    print(f'Geocoding error: {e}')
    return []


@anvil.server.callable
def search_map_items_by_fields(search_data):
  addr1 = (search_data.get('Address1_Value') or '').strip()
  city = (search_data.get('City_Value') or '').strip()
  db_state = (search_data.get('State_Province_Region_Value') or '').strip()
  postal = (search_data.get('Postal_Code_Value') or '').strip()
  country = (search_data.get('Country_Code_Value') or '').strip()
  cluster_type = search_data.get('cluster_type', 'miles')
  threshold = search_data.get('threshold', 25)

  sel_lat = search_data.get('Selected_Latitude')
  sel_lon = search_data.get('Selected_Longitude')

  center_lat = None
  center_lon = None
  zoom = 11

  if sel_lat and sel_lon:
    center_lat = sel_lat
    center_lon = sel_lon
    zoom = 12
  else:
    if addr1:
      zoom = 15
    elif city or postal:
      zoom = 12
    elif db_state:
      zoom = 8
    elif country:
      zoom = 5

    if any([addr1, city, db_state, postal, country]):
      geocoded_results = geocode_multiple_addresses(
          addr1=addr1,
          city=city,
          state_str=db_state,
          postal=postal,
          country_code=country,
      )

      if len(geocoded_results) > 1:
        return {'status': 'disambiguation_needed', 'options': geocoded_results}

      if geocoded_results:
        center_lat = geocoded_results[0]['latitude']
        center_lon = geocoded_results[0]['longitude']

  all_items = list(app_tables.mapitems.search())
  clusters = cluster_rows(
      all_items, cluster_type=cluster_type, threshold=threshold
  )

  if not center_lat and clusters:
    center_lat = clusters[0]['latitude']
    center_lon = clusters[0]['longitude']

  return {
      'status': 'success',
      'clusters': clusters,
      'latitude': center_lat,
      'longitude': center_lon,
      'zoom': zoom,
  }


@anvil.server.callable
def get_scorecard_hierarchy_data():
  """Fetches map items and aggregates them into Global Region -> Country -> City."""
  all_items = list(app_tables.mapitems.search())

  hierarchy = {}

  for row in all_items:
    country_code = (row.get('country_code') or '').strip()
    region_name = get_global_region(country_code)
    country_obj = pycountry.countries.get(alpha_2=country_code.upper())
    country_str = (
        country_obj.name if country_obj else (country_code or 'Unknown')
    )
    city_str = (row.get('city') or 'Unknown City').strip().title()

    if region_name not in hierarchy:
      hierarchy[region_name] = {}
    if country_str not in hierarchy[region_name]:
      hierarchy[region_name][country_str] = {}
    if city_str not in hierarchy[region_name][country_str]:
      hierarchy[region_name][country_str][city_str] = 0

    hierarchy[region_name][country_str][city_str] += 1

  return hierarchy

@anvil.server.callable
def get_map_markers_with_privacy_view(active_record_id=None, show_actuals=True):
  """Fetches markers: shows red actual + green offset ONLY for the just-entered record.
     All other records show standard blue offset markers."""
  all_items = list(app_tables.mapitems.search())
  markers = []

  for row in all_items:
    record_id = row.get('id')
    act_lat = row.get('latitude')
    act_lon = row.get('longitude')
    off_lat = row.get('offset_latitude') or act_lat
    off_lon = row.get('offset_longitude') or act_lon
    username = row.get('user_name', 'Unknown User')
    address = row.get('formatted_address', '')

    is_latest = (record_id == active_record_id)

    if act_lat is not None and act_lon is not None:
      # 1. Actual Location Marker (Only shown for the just-entered record if switch is ON)
      if is_latest and show_actuals:
        markers.append({
            'latitude': act_lat,
            'longitude': act_lon,
            'color': 'red',
            'label': f'[ACTUAL - Just Entered] {username} - {address}',
            'type': 'actual'
        })

      # 2. Offset Location Marker
      if is_latest:
        # Specially colored offset for the record just entered
        markers.append({
            'latitude': off_lat,
            'longitude': off_lon,
            'color': 'green',
            'label': f'[OFFSET - Just Entered] {username} - {address}',
            'type': 'offset_latest'
        })
      else:
        # Standard offset marker in blue for all other historical records
        markers.append({
            'latitude': off_lat,
            'longitude': off_lon,
            'color': 'blue',
            'label': f'[OFFSET] {username} - {address}',
            'type': 'offset_standard'
        })

  return markers