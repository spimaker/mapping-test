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
    'postal_code': '#1E90FF', # Blue
    'city': '#FFD700',        # Yellow
    'state': '#FFA500',       # Orange
    'country': '#FF0000'      # Red
  }

  if cluster_type in ['postal_code', 'city', 'state', 'country']:
    field_mapping = {
      'postal_code': 'postal_code',
      'city': 'city',
      'state': 'state',
      'country': 'country_code'
    }
    type_code_mapping = {
      'postal_code': 'Post',
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
