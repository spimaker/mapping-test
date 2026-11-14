import time
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables
import pycountry
from country_state_city import Country, State

@anvil.server.background_task
def copy_all_mapitems_task():
    """Background task to copy the entire MapItems_Test to MapItems_Test2 with periodic updates."""
    source_rows = app_tables.mapitems_test.search()
    total_copied = 0
    start_time = time.time()
    last_print_time = start_time

    for row in source_rows:
        country_code = row.get('country_code')
        state_code = row.get('state')
        
        # 1. Resolve full country name using pycountry
        country_name = ""
        if country_code:
            try:
                code_str = str(country_code).strip()
                c_obj = None
                if len(code_str) == 2:
                    c_obj = pycountry.countries.get(alpha_2=code_str.upper())
                elif len(code_str) == 3:
                    c_obj = pycountry.countries.get(alpha_3=code_str.upper())
                
                if c_obj:
                    country_name = c_obj.name
            except Exception:
                pass

        # 2. Resolve full state name using country_state_city library
        state_name = ""
        if country_code and state_code:
            try:
                states_list = State.get_states_of_country(str(country_code).strip().upper())
                if states_list:
                    for s in states_list:
                        if s.iso_code.upper() == str(state_code).strip().upper() or s.name.upper() == str(state_code).strip().upper():
                            state_name = s.name
                            break
            except Exception:
                pass

        # 3. Insert record into MapItems_Test2
        app_tables.mapitems_test2.add_row(
            id=row.get('id'),
            created_time=row.get('created_time'),
            date_time=row.get('date_time'),
            region=row.get('region'),
            country_code=country_code,
            country_name=country_name,
            state=state_code,
            state_name=state_name,
            city=row.get('city'),
            postal_code=row.get('postal_code'),
            address_1=row.get('address_1'),
            address_2=row.get('address_2'),
            latitude=row.get('latitude'),
            longitude=row.get('longitude'),
            offset_latitude=row.get('offset_latitude'),
            offset_longitude=str(row.get('offset_longitude') or ''),
            formatted_address=row.get('formatted_address'),
            index=row.get('index'),
            user=row.get('user_name') or row.get('user')
        )
        total_copied += 1

        # Check if a minute (60 seconds) has passed since the last log print
        current_time = time.time()
        if current_time - last_print_time >= 60:
            print(f"Background Progress: {total_copied} records copied so far...")
            last_print_time = current_time

    print(f"Background Task Complete! Total records copied: {total_copied}")
    return total_copied


@anvil.server.callable
def start_copy_entire_table():
    """Client callable to kick off the background task."""
    task = anvil.server.launch_background_task("copy_all_mapitems_task")
    return task