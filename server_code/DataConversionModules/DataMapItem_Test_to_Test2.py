import time
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables
import pycountry
from country_state_city import Country, State


@anvil.server.callable
def start_copy_entire_table2():
    """Client callable to kick off the background task."""
    task = anvil.server.launch_background_task("copy_all_mapitems_task")
    return task

  