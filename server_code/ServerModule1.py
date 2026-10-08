#import anvil.tables as tables
#import anvil.tables.query as q
#from anvil.tables import app_tables
#import anvil.server

# This is a server module. It runs on the Anvil server,
# rather than in the user's browser.
#
# To allow anvil.server.call() to call functions here, we mark
# them with @anvil.server.callable.
# Here is an example - you can replace it with your own:
#
# @anvil.server.callable
# def say_hello(name):
#   print("Hello, " + name + "!")
#   return 42
#
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import pycountry
from geopy.geocoders import Nominatim
import uuid

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