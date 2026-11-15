from ._anvil_designer import DataConversionsTemplate
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil import alert

class DataConversions(DataConversionsTemplate):
    def __init__(self, **properties):
        # Set Form properties and Data Bindings
        self.init_components(**properties)
        self.use_test_table = True

    def sync_countries_button_click(self, **event_args):
        """Triggered when 'DataHub Countries' button is clicked."""
        try:
            print("Calling server function to populate DataHub countries...")
            result = anvil.server.call('populate_datahub_countries')
            alert(result, title="DataHub Countries")
        except Exception as e:
            alert(f"Error populating countries: {e}", title="Error")

    def button_1_click(self, **event_args):
        """Triggered when 'Harvest Postal Codes' button is clicked."""
        target_code = self.Country_Code.text.strip().upper() if self.Country_Code.text else ""
        state_code = self.State_Code.text.strip().upper() if self.State_Code.text else None

        if not target_code:
            alert("Please enter a valid Country Code in the input box.", title="Validation Error")
            return

        try:
            print(f"Launching background postal code harvest for Country: {target_code}, State: {state_code}")
            task = anvil.server.call('start_harvest_background', target_code=target_code, state_code=state_code)
            alert(f"Postal code harvest background task started successfully for {target_code}!", title="Background Task Launched")
        except Exception as e:
            alert(f"Error starting postal code harvest: {e}", title="Error")

    def SQL_Query_click(self, **event_args):
        """Triggered when 'SQL Query' button is clicked."""
        try:
            print("Executing table count query...")
            count = anvil.server.call('get_table_count')
            if hasattr(self, 'SQL_Reply'):
                self.SQL_Reply.text = f"Total records found: {count}"
            alert(f"Total records found: {count}", title="SQL Query Result")
        except Exception as e:
            alert(f"Query error: {e}", title="Error")

    def Harvest_Address_click(self, **event_args):
        """Triggered when 'Harvest Address' button is clicked."""
        try:
            print("Launching individual postal code address harvest background task...")
            task = anvil.server.call('start_individual_harvest')
            alert("Address harvest background task started successfully!", title="Background Task Launched")
        except Exception as e:
            alert(f"Error starting address harvest: {e}", title="Error")

    def Load_Test_Addresses_click(self, **event_args):
        """Triggered when 'Load Test Addresses' button is clicked."""
        try:
            print("Launching test address loading background task...")
            task = anvil.server.call('start_test_address_load')
            alert("Test address load background task started successfully!", title="Background Task Launched")
        except Exception as e:
            alert(f"Error starting test address load: {e}", title="Error")

    def Copy_to_MapItem_Test2_click(self, **event_args):
        """Triggered when 'Copy to MapItem_Test2' button is clicked."""
        try:
            print("Launching entire table copy background task...")
            task = anvil.server.call('start_copy_entire_table')
            alert("Copy background task started successfully!", title="Background Task Launched")
        except Exception as e:
            alert(f"Error starting table copy: {e}", title="Error")

    def Build_summary_tables_click(self, **event_args):
        """Triggered when 'Build Summary Tables' button is clicked."""
        # 1. Disable button and update status to prevent multiple rapid clicks
        self.Build_summary_tables.enabled = False
        if hasattr(self, 'status_label'):
            self.status_label.text = "Processing records and building the 5 summary tables..."
        
        try:
            # 2. Call the server-side migration function
            result_message = anvil.server.call('populate_all_map_summaries')
            
            # 3. Success feedback
            if hasattr(self, 'status_label'):
                self.status_label.text = result_message
            anvil.alert(result_message, title="Migration Complete", large=False)
            
        except Exception as e:
            # 4. Error handling feedback
            error_msg = f"Migration failed: {str(e)}"
            if hasattr(self, 'status_label'):
                self.status_label.text = error_msg
            anvil.alert(error_msg, title="Error", large=False)
            
        finally:
            # 5. Re-enable the button
            self.Build_summary_tables.enabled = True

          
    def Build_map_user_lookup_click(self, **event_args):
            """Triggered when the backfill button is clicked to launch the background task."""
            try:
                use_test = getattr(self, 'use_test_table', True)
            
                # Launch background task and get immediate response
                result_message = anvil.server.call(
                    'populate_map_user_lookup', 
                    use_test_table=use_test
                )
                
                alert(content=result_message, title="Background Task Started", large=False)
            
            except Exception as e:
                alert(content=f"Error launching background task: {e}", title="Error", large=False)