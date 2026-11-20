from ._anvil_designer import ConversionProcessesTemplate
import anvil
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil import alert

class ConversionProcesses(ConversionProcessesTemplate):
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

    def Sql_query_button_click(self, **event_args):
            """Sends the Data Table name and SQL query to the server and displays the reply in SQL_Reply."""
            table_name = self.Data_Table.text
            query_text = self.SQL_Query_Entry.text
        
            if not table_name or not table_name.strip():
                self.SQL_Reply.text = "Error: Please enter a Data Table name."
                return

            if not query_text or not query_text.strip():
                self.SQL_Reply.text = "Error: Please enter a SQL query before executing."
                return

            try:
                self.SQL_Reply.text = f"Executing query on '{table_name.strip()}'..."
            
                response = anvil.server.call(
                    'execute_raw_sql_query', 
                    table_name=table_name,
                    sql_query=query_text
                )
            
                self.SQL_Reply.text = str(response)
                
            except Exception as e:
                self.SQL_Reply.text = f"Client Error: {str(e)}"

    def Harvest_Address_click(self, **event_args):
        """Triggered when 'Harvest Address' button is clicked."""
        try:
            print("Launching individual postal code address harvest background task...")
            task = anvil.server.call('start_individual_harvest')
            alert("Address harvest background task started successfully!", title="Background Task Launched")
        except Exception as e:
            alert(f"Error starting address harvest: {e}", title="Error")


  
      
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
            self.Build_summary_tables.enabled = False
            if hasattr(self, 'status_label'):
                self.status_label.text = "Processing records and building the 5 summary tables..."
        
            try:
                result_message = anvil.server.call(
                    'populate_all_map_summaries', 
                    use_test_table=self.use_test_table
                )
            
                if hasattr(self, 'status_label'):
                    self.status_label.text = result_message
                anvil.alert(result_message, title="Migration Complete", large=False)
            
            except Exception as e:
                error_msg = f"Migration failed: {str(e)}"
                if hasattr(self, 'status_label'):
                    self.status_label.text = error_msg
                anvil.alert(error_msg, title="Error", large=False)
            
            finally:
                self.Build_summary_tables.enabled = True          
    
    def Build_map_user_lookup_click(self, **event_args):
            """Triggered when the backfill button is clicked to launch the background task."""
            try:
                use_test = getattr(self, 'use_test_table', True)
            
                result_message = anvil.server.call(
                    'populate_map_user_lookup', 
                    use_test_table=use_test
                )
                
                alert(content=result_message, title="Background Task Started", large=False)
            
            except Exception as e:
                alert(content=f"Error launching background task: {e}", title="Error", large=False)

    @anvil.handle("Get_local_data", "click")
    def get_local_data_click(self, **event_args):
        """This method is called when the button is clicked to start fresh harvesting."""
        task = anvil.server.call(
            'start_data_generation_task',
            start_country="MX",
            start_state_code="GUA",
            clear_tables=False
        )

    def button_harvest_north_america_click(self, **event_args):
        """Triggered when the 'Harvest All US, CA, MX' button is clicked."""
        try:
            print("Launching full North American postal code harvest background task...")
            task = anvil.server.call('start_full_north_america_harvest')
            alert("Full US, CA, and MX postal code harvest started successfully in the background!", title="Background Task Launched")
        except Exception as e:
            alert(f"Error starting North American harvest: {e}", title="Error")

    def audit_north_america_button_click(self, **event_args):
            """Triggered when the audit/search button is clicked."""
            try:
                print("Launching North American DataHub background audit...")
                task = anvil.server.call('start_north_america_datahub_audit')
                alert("North American DataHub regional audit started successfully in the background!", title="Task Launched")
            except Exception as e:
                alert(f"Error starting audit: {e}", title="Error")          

    def run_harvest_button_click(self, **event_args):
      """Launch the single-state (US - AL) test background task from a button click."""
      self.run_harvest_button.enabled = False
      try:
        task = anvil.server.call("start_first_state_test", "US", "AL")
        alert("Started background test harvest for US - AL. Watch the App Logs / Background Tasks for True: and False: output.")
      except Exception as e:
        alert(f"Error starting test harvest: {e}")
      finally:
        self.run_harvest_button.enabled = True

    @anvil.handle("import_geonames", "click")
    def import_geonames_click(self, **event_args):
      """This method is called when the button is clicked"""
      pass  # Write Code Here

    @anvil.handle("geonames_file_loader", "change")
    def geonames_file_loader_change(self, file, **event_args):
        """Run GeoNames TSV import when CA_Postal.txt is selected in geonames_file_loader."""
        print(f"[CLIENT] geonames_file_loader_change fired; file={file!r}")
        if not file:
          alert(
              "[CLIENT] No file selected. Please choose CA_Postal.txt in"
              " geonames_file_loader."
          )
          return

        if file.name != "CA_Postal.txt":
          print(
              f"[CLIENT] Warning: expected CA_Postal.txt, got {file.name!r};"
              " proceeding anyway."
          )

        try:
          print("[CLIENT] Launching background import task for CA_Postal.txt...")
          res = anvil.server.call(
              "import_geonames_file",
              file,
              start_row=0,
              max_rows=None,
              max_seconds=240.0,
              log_every=10,
              use_background_task=True,
          )
          print(f"[CLIENT] Server response for CA_Postal.txt: {res}")
          alert(f"Import response (CA_Postal.txt): {res}")
        except Exception as e:
          print(f"[CLIENT] ERROR importing CA_Postal.txt: {e!r}")
          alert(f"Error importing CA_Postal.txt: {e}")


    def load_test_addresses_click(self, **event_args):
          """Launch full US Overpass address harvest from the beginning (skipping CA/MX)."""
          btn = event_args.get("sender")
          if btn:
            btn.enabled = False

          try:
            task = anvil.server.call(
                "start_geonames_harvest_test",
                limit_records=None,
                skip_first_us=2860,
                target_country="US",
            )
            task_id = task.get_id() if task and hasattr(task, "get_id") else None

            msg = (
                "Started full US address harvest from the beginning (skipping CA and MX) "
                "in the background. Check the server console for progress."
            )
            if task_id:
              msg = (
                  f"Started full US address harvest (Task: {task_id}). "
                  "Check the server console for progress."
              )

            anvil.Notification(msg, title="Harvest Started", style="success").show()
          except Exception as e:
            anvil.alert(f"Error starting address harvest: {e}", title="Harvest Error")
          finally:
            if btn:
              btn.enabled = True

    