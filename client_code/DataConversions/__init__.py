import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class dataconversions(dataconversionsTemplate):
    def __init__(self, **properties):
        # Set Form properties and Data Bindings
        self.init_components(**properties)

        # Any code you write here runs when the form opens

    def build_summary_tables_click(self, **event_args):
        """This method is called when the Build Summary Tables button is clicked."""
        
        # 1. Disable button and update status to prevent multiple rapid clicks
        self.build_summary_tables.enabled = False
        self.status_label.text = "Processing 103k+ records and building the 5 summary tables..."
        
        try:
            # 2. Call the server-side migration function
            result_message = anvil.server.call('populate_all_map_summaries')
            
            # 3. Success feedback
            self.status_label.text = result_message
            anvil.alert(result_message, title="Migration Complete", large=False)
            
        except Exception as e:
            # 4. Error handling feedback
            error_msg = f"Migration failed: {str(e)}"
            self.status_label.text = error_msg
            anvil.alert(error_msg, title="Error", large=False)
            
        finally:
            # 5. Re-enable the button
            self.build_summary_tables.enabled = True