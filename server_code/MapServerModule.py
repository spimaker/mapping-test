import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables
import pycountry
from pycountry_convert import country_alpha2_to_continent_code
from country_state_city import Country, State, City

@anvil.server.callable
def get_map_markers_with_privacy_view(active_record_id=None, show_actuals=True):
    """Fetches markers: shows red actual + green offset ONLY for the just-entered record.
        All other records show standard blue offset markers, with labels showing only usernames."""
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
              'latitude': act_lat,
              'longitude': act_lon,
              'color': 'red',
              'user_name': username,
              'type': 'actual'
          })

        if is_latest:
          markers.append({
              'latitude': off_lat,
              'longitude': off_lon,
              'color': 'green',
              'user_name': username,
              'type': 'offset_latest'
          })
        else:
          markers.append({
              'latitude': off_lat,
              'longitude': off_lon,
              'color': 'blue',
              'user_name': username,
              'type': 'offset_standard'
          })

    return markers


@anvil.server.callable
def save_map_item(record_data):
    """Saves a new map entry record to the mapitems table and returns its unique ID."""
    new_row = app_tables.mapitems.add_row(
        user_name=record_data.get('user_name'),
        country_code=record_data.get('country_code'),
        state_province_region=record_data.get('state_province_region'),
        city=record_data.get('city'),
        custom_city=record_data.get('custom_city'),
        postal_code=record_data.get('postal_code'),
        address1=record_data.get('address1'),
        address2=record_data.get('address2'),
        latitude=record_data.get('latitude'),
        longitude=record_data.get('longitude'),
        formatted_address=record_data.get('formatted_address')
    )
    return new_row.get_id() if hasattr(new_row, 'get_id') else new_row


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
        
    # Append the manual entry trigger option at the very end
    city_list.append(("Enter City Manually", "MANUAL_ENTRY"))
    
    return city_list

@anvil.server.callable
def geocode_address(address_query):
    """Stub or implementation for geocoding address inputs."""
    return {
        'latitude': None,
        'longitude': None,
        'formatted_address': ''
    }