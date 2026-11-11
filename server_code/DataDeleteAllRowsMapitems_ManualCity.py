import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

@anvil.server.callable
def delete_all_map_data():
    """Deletes every row from both the MapItems and ManualCity data tables."""
    try:
        # Delete all records from mapitems
        map_count = 0
        for row in app_tables.mapitems.search():
            row.delete()
            map_count += 1

        # Delete all records from manualcity
        city_count = 0
        for row in app_tables.manualcity.search():
            row.delete()
            city_count += 1

        return f"Cleared tables: {map_count} rows removed from MapItems, {city_count} rows removed from ManualCity."
    except Exception as e:
        print(f"Error clearing database tables: {e}")
        raise e