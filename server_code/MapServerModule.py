import datetime
import uuid
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables
import pycountry
from pycountry_convert import country_alpha2_to_continent_code
from country_state_city import Country, State, City
from geopy.geocoders import Nominatim

# Initialize Nominatim geolocator with a unique user agent
geolocator = Nominatim(user_agent="NaturistMappingProject")


@anvil.server.callable
def get_map_markers_with_privacy_view(active_record_id=None, show_actuals=True):
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
                    'lat': float(act_lat),  # Ensure 'lat' instead of 'latitude' for Anvil Map
                    'lon': float(act_lon),  # Ensure 'lon' instead of 'longitude' for Anvil Map
                    'color': 'red',
                    'title': username
                })

            if is_latest:
                markers.append({
                    'lat': float(off_lat),
                    'lon': float(off_lon),
                    'color': 'green',
                    'title': username
                })
            else:
                markers.append({
                    'lat': float(off_lat),
                    'lon': float(off_lon),
                    'color': 'blue',
                    'title': username
                })

    return markers


@anvil.server.callable
def save_map_item(record_data):
    """Geocodes the address, saves to mapitems and manualcity with explicit IDs, and logs to console."""
    country = record_data.get('country_code')
    state = record_data.get('state')
    city = record_data.get('city')
    address_1 = record_data.get('address_1')
    address_2 = record_data.get('address_2')
    postal_code = record_data.get('postal_code')
    user_name = record_data.get('user_name')

    # Construct address query string for geocoding validation
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
        print(f"Geopy geocoding validation error before saving: {e}")

    current_time = datetime.datetime.now()
    generated_id = str(uuid.uuid4())

    # 1. Save to main map items table with an explicit unique record ID
    new_row = app_tables.mapitems.add_row(
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
    
    print(f"MapItems record successfully saved with ID: {generated_id}")
    
    # 2. Store newly entered manual cities in ManualCity table with an explicit unique ID
    if country and state and city and city != "MANUAL_ENTRY":
        existing_manual = app_tables.manualcity.get(
            country_code=country, 
            state=state, 
            city=city
        )
        if not existing_manual:
            try:
                city_row_id = str(uuid.uuid4())
                app_tables.manualcity.add_row(
                    id=city_row_id,
                    country_code=country,
                    state=state,
                    city=city,
                    latitude=lat,
                    longitude=lon,
                    date_time=current_time
                )
                print(f"Console Message: Successfully saved new manual city '{city}' to ManualCity with ID: {city_row_id}")
            except Exception as e:
                print(f"Error saving new manual city: {e}")
        else:
            print(f"Manual city '{city}' already exists in ManualCity table.")

    return generated_id


@anvil.server.callable
def get_country_list():
    """Returns countries grouped and ordered by global region using pycountry and pycountry_convert."""
    region_order = [
        "North America",
        "South America",
        "Europe",
        "Asia",
        "Africa",
        "Oceania",
        "Other"
    ]
    
    continent_code_mapping = {
        "NA": "North America",
        "SA": "South America",
        "EU": "Europe",
        "AS": "Asia",
        "AF": "Africa",
        "OC": "Oceania"
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
                    display_label = f"[{region}] {name}"
                    country_list.append((display_label, code))
                    
    except Exception as e:
        print(f"Error fetching countries with region grouping: {e}")
        
    return country_list


@anvil.server.callable
def get_states_for_country(country_code):
    """Returns states/subdivisions for a given country code using CountryStateCity with default prompt."""
    state_list = [("<Select State>", None)]
    if not country_code:
        return state_list
        
    try:
        states = State.get_states_of_country(country_code)
        if states:
            sorted_states = sorted(
                [(s.name, s.iso_code) for s in states],
                key=lambda x: x[0]
            )
            for state_name, state_code in sorted_states:
                state_list.append((state_name, state_code))
    except Exception as e:
        print(f"Error fetching states for {country_code}: {e}")
    return state_list


@anvil.server.callable
def get_cities_for_state(country_code, state_code):
    """Returns cities merged with manually entered cities from ManualCity table, ending with 'Enter City Manually'."""
    city_list = [("<Select City>", None)]
    if not country_code or not state_code:
        return city_list
        
    seen_cities = set()
    
    try:
        cities = City.get_cities_of_state(country_code, state_code)
        if cities:
            sorted_cities = sorted([c.name for c in cities])
            for c_name in sorted_cities:
                if c_name not in seen_cities:
                    seen_cities.add(c_name)
                    city_list.append((c_name, c_name))
    except Exception as e:
        print(f"Error fetching cities from package: {e}")
        
    try:
        manual_rows = app_tables.manualcity.search(
            tables.order_by("city"),
            country_code=country_code,
            state=state_code
        )
        for row in manual_rows:
            c_name = row.get('city')
            if c_name and c_name not in seen_cities:
                seen_cities.add(c_name)
                city_list.append((c_name, c_name))
    except Exception as e:
        print(f"Error fetching manual cities: {e}")
        
    city_list.append(("Enter City Manually", "MANUAL_ENTRY"))
    
    return city_list


@anvil.server.callable
def geocode_address(address_query):
    """On-demand geocoding preview using geopy/Nominatim."""
    parts = [
        address_query.get('address_1'),
        address_query.get('address_2'),
        address_query.get('city'),
        address_query.get('state'),
        address_query.get('country'),
        address_query.get('postal_code')
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
        print(f"Geocoding preview error: {e}")
        
    return {
        'latitude': None,
        'longitude': None,
        'formatted_address': ''
    }