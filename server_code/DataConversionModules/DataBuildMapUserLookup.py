import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables, query as q
from pycountry_convert import country_alpha2_to_continent_code
import time

def get_target_table(use_test_table):
    """Helper to return the correct Data Table based on the flag."""
    return app_tables.mapitems_test if use_test_table else app_tables.mapitems

def get_region_from_country_code(country_code):
    """Maps a country code to a global region using pycountry_convert."""
    if not country_code:
        return "Other"
    try:
        continent_code = country_alpha2_to_continent_code(country_code.strip().upper())
        continent_map = {
            "NA": "North America", "SA": "South America", "EU": "Europe",
            "AS": "Asia", "AF": "Africa", "OC": "Oceania"
        }
        return continent_map.get(continent_code, "Other")
    except Exception:
        return "Other"

@anvil.server.background_task
def _background_populate_lookup(use_test_table):
    """Background worker that processes records and prints progress to the console."""
    raw_table = get_target_table(use_test_table)
    lookup_table = app_tables.map_user_lookup
    
    print(f"Starting background backfill for table: {'mapitems_test' if use_test_table else 'mapitems'}")
    all_raw_rows = list(raw_table.search())
    total_rows = len(all_raw_rows)
    print(f"Found {total_rows} raw records to process.")
    
    updated_count = 0
    start_time = time.time()
    
    for i, row in enumerate(all_raw_rows, 1):
        record_id = row.get('id')
        if not record_id:
            continue
            
        user_name = row.get('user') or row.get('user_name')
        country = (row.get('country_code') or '').strip().upper()
        state = (row.get('state') or '').strip().upper()
        city = (row.get('city') or '').strip()
        postal_code = (row.get('postal_code') or '').strip()
        region = row.get('region') or get_region_from_country_code(country)
        
        lookup_data = {
            'id': record_id,
            'user': user_name,
            'region': region,
            'country_code': country,
            'state': state,
            'city': city,
            'postal_code': postal_code
        }
        
        existing = lookup_table.get(id=record_id)
        if existing:
            existing.update(**lookup_data)
        else:
            lookup_table.add_row(**lookup_data)
            
        updated_count += 1
        
        # Print progress update to console every 100 records
        if i % 100 == 0 or i == total_rows:
            elapsed = time.time() - start_time
            print(f"Progress: {i}/{total_rows} records processed ({updated_count} synced)... Elapsed: {elapsed:.1f}s")
            
    print(f"Backfill complete! Successfully processed {updated_count} records.")

@anvil.server.callable
def populate_map_user_lookup(use_test_table=True):
    """
    Launches the backfill as an asynchronous background task.
    """
    task = anvil.server.launch_background_task('_background_populate_lookup', use_test_table)
    return f"Background task launched successfully (Task ID: {task.get_id()}). Check your server console for live progress!"