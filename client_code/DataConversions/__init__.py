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
    # Create input text boxes with explicit widths so they render correctly in the alert
    country_box = anvil.TextBox(placeholder="e.g. AU", width="100%")
    state_box = anvil.TextBox(placeholder="e.g. NSW", width="100%")
    pcode_box = anvil.TextBox(placeholder="e.g. 2298", width="100%")
    
    # Build the container panel
    prompt_content = anvil.ColumnPanel()
    prompt_content.add_component(anvil.Label(text="Enter starting point to resume (leave blank to start from the top):", bold=True))
    prompt_content.add_component(anvil.Label(text="Country Code:"))
    prompt_content.add_component(country_box)
    prompt_content.add_component(anvil.Label(text="State / Region:"))
    prompt_content.add_component(state_box)
    prompt_content.add_component(anvil.Label(text="Postal Code:"))
    prompt_content.add_component(pcode_box)
    
    # Trigger the alert popup
    result = anvil.alert(
        content=prompt_content, 
        title="Harvester Resumption Setup", 
        buttons=[("Start Harvest", True), ("Cancel", False)],
        large=False
    )
    
    # If the user clicked "Start Harvest"
    if result is True:
      c_val = country_box.text.strip().upper() or None
      s_val = state_box.text.strip().upper() or None
      p_val = pcode_box.text.strip() or None
      
      # Call the server background task with the chosen starting coordinates
      anvil.server.call(
          'start_test_address_load', 
          start_country=c_val, 
          start_state=s_val, 
          start_pcode=p_val
      )
      anvil.alert("Background harvesting task started successfully!")

  