from ._anvil_designer import DataConversionsTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class DataConversions(DataConversionsTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    # Any code you write here will run before the form opens.
  def sync_countries_button_click(self, **event_args):
    with Notification('Syncing countries from DataHub...'):
      result = anvil.server.call('populate_datahub_countries')
    print(result)


  def button_1_click(self, **event_args):
    """Called when the harvest button is clicked"""
    target_code = self.Country_Code.text.strip().upper()
    state_code = self.State_Code.text.strip().upper()
  
    print(f"CLIENT SENDING -> Country: '{target_code}', State: '{state_code}'")
  
    if not target_code:
      alert("Please enter a country code (e.g., 'AU').")
      return

    # Trigger the background task passing both fields
    anvil.server.call(
        'start_harvest_background',
        target_code=target_code,
        state_code=state_code if state_code else None
    )
  
    alert(f"Harvest started for Country: {target_code}, State: {state_code or 'All'}!")

  @handle("SQL_Query", "click")
  def SQL_Query_click(self, **event_args):
      """This method is called when the button is clicked"""
      # Call the server function securely
      count = anvil.server.call('get_postal_code_count')
    
      # Example: Display the result in a Label on your form
      self.SQL_Reply.text = f"Total records: {count}"

    
  def Harvest_Address_click(self, **event_args):
    """Called when the Harvest Address button is clicked"""
    print("Launching individual address harvesting task for 90272...")
  
    # This must match the name of your @anvil.server.callable function
    anvil.server.call('start_individual_harvest')
  
    alert("Individual address harvest background task launched! Check your server logs.")


  def Load_Test_Addresses_click(self, **event_args):
    """Called when the Load Test Addresses button is clicked"""
    print("Launching live test address harvest task into MapItems_Test...")
    anvil.server.call('start_test_address_load')
    alert("Live harvesting task launched! Check your server logs for real-time progress.")