import anvil.server
from anvil.tables import app_tables

@anvil.server.callable
def get_postal_code_count():
    #return len(app_tables.datahub_postal_codes.search())
    return len(app_tables.mapitems_test.search())