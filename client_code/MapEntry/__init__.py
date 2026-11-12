from ._anvil_designer import MapEntryTemplate
import anvil.server
from anvil import alert


class MapEntry(MapEntryTemplate):
  def __init__(self, **properties):
      self.init_components(**properties)
      self.last_saved_record_id = None

      # Toggle between MapItems_Test (True) and MapItems (False)
      self.use_test_table = True

      # set border on Info_Link
      self.Info_Link.role = 'input-border'

      # Hide radius controls by default on startup
      self.Threshold_Label.visible = False
      self.Threshold_Dropdown.visible = False
     
      try:
        self.Country_Code_Value.items = anvil.server.call('get_country_list')
      except Exception as e:
        pass

      # Set default cluster type to Country and load map display
      if hasattr(self, 'Cluster_Type_Dropdown'):
        self.Cluster_Type_Dropdown.selected_value = 'Country'

      self.refresh_map_display(cluster_type='Country')

      self.repeating_panel_1.items = [
              {'range': '1 – 999 records', 'role': 'swatch-8'},
              {'range': '1,000 – 9,999 records', 'role': 'swatch-10'},
              {'range': '10,000 – 99,999 records', 'role': 'swatch-12'},
              {'range': '100,000 – 249,999 records', 'role': 'swatch-16'},
              {'range': '250,000 – 999,999 records', 'role': 'swatch-18'},
              {'range': '1,000,000+ records', 'role': 'swatch-20'},
          ]
    
  def clear_button_click(self, **event_args):
    self.User_Name_Value.text = ""
    self.Country_Code_Value.selected_value = None
    self.State_Province_Region_Value.selected_value = None
    self.City_Value.selected_value = None
    self.City_Value.items = [("<Select City>", None)]
  
    self.Custom_City_Label.visible = False
    self.Custom_City_TextBox.visible = False
    self.Custom_City_TextBox.text = ""
  
    self.Postal_Code_Value.text = ""
    self.Address1_Value.text = ""
    self.Address2_Value.text = ""
    self.Latitude_Value.text = ""
    self.Longitude_Value.text = ""
    self.Formatted_Address_Value.text = ""

  def save_button_click(self, **event_args):
      try:
        selected_city = self.City_Value.selected_value
        final_city = (
            self.Custom_City_TextBox.text 
            if selected_city == "MANUAL_ENTRY" 
            else selected_city
        )

        record_data = {
            'user_name': self.User_Name_Value.text,
            'country_code': self.Country_Code_Value.selected_value,
            'state': self.State_Province_Region_Value.selected_value,
            'city': final_city,
            'postal_code': self.Postal_Code_Value.text,
            'address_1': self.Address1_Value.text,
            'address_2': self.Address2_Value.text,
            'latitude': float(self.Latitude_Value.text) if self.Latitude_Value.text else None,
            'longitude': float(self.Longitude_Value.text) if self.Longitude_Value.text else None,
            'formatted_address': self.Formatted_Address_Value.text,
        }

        saved_id = anvil.server.call(
            'save_map_item', 
            record_data, 
            use_test_table=self.use_test_table
        )
        if saved_id:
          table_label = "MapItems_Test" if self.use_test_table else "MapItems"
          alert(f"Record saved successfully to {table_label}!")
          self.refresh_map_display(active_record_id=saved_id)
      except Exception as e:
        alert(f'Error saving record: {e}')

  def search_button_click(self, **event_args):
    try:
      address_query = {
          'address_1': self.Address1_Value.text,
          'address_2': self.Address2_Value.text,
          'city': self.City_Value.selected_value or self.Custom_City_TextBox.text,
          'state': self.State_Province_Region_Value.selected_value,
          'country': self.Country_Code_Value.selected_value,
          'postal_code': self.Postal_Code_Value.text
      }
      result = anvil.server.call('geocode_address', address_query)
      if result:
        self.Latitude_Value.text = str(result.get('latitude', ''))
        self.Longitude_Value.text = str(result.get('longitude', ''))
        self.Formatted_Address_Value.text = result.get('formatted_address', '')
    except Exception as e:
      print(f'Error during search: {e}')

  def full_screen_map_button_click(self, **event_args):
    try:
      anvil.open_form('FullScreenMapForm')
    except Exception as e:
      print(f'Error opening full screen map: {e}')

  def country_dropdown_change(self, **event_args):
    selected_country = self.Country_Code_Value.selected_value
    self.State_Province_Region_Value.items = []
    self.State_Province_Region_Value.selected_value = None
    self.City_Value.items = []
    self.City_Value.selected_value = None
    
    if selected_country:
      try:
        self.State_Province_Region_Value.items = anvil.server.call(
            'get_states_for_country', selected_country
        )
      except Exception as e:
        print(f"Error loading states: {e}")

  def state_dropdown_change(self, **event_args):
      selected_country = self.Country_Code_Value.selected_value
      selected_state = self.State_Province_Region_Value.selected_value
      self.City_Value.items = [("<Select City>", None)]
      self.City_Value.selected_value = None
    
      if selected_country and selected_state:
        try:
          self.City_Value.items = anvil.server.call(
              'get_cities_for_state', selected_country, selected_state
          )
        except Exception as e:
          print(f"Error loading cities: {e}")

  def city_dropdown_change(self, **event_args):
      selected_city = self.City_Value.selected_value
      if selected_city == "MANUAL_ENTRY":
        self.Custom_City_Label.visible = True
        self.Custom_City_TextBox.visible = True
        self.Custom_City_TextBox.focus()
      else:
        self.Custom_City_Label.visible = False
        self.Custom_City_TextBox.visible = False
        self.Custom_City_TextBox.text = ""

  def refresh_map_display(self, cluster_type=None, distance_value=None, active_record_id=None):
        self.map_1.clear()
      
        cluster_type = cluster_type or 'region'

        markers = anvil.server.call(
            'get_clustered_map_markers', 
            cluster_type=cluster_type, 
            distance_value=distance_value, 
            active_record_id=active_record_id,
            use_test_table=self.use_test_table
        )
    
        for m in markers:
          lat_lng = self.map_1.LatLng(m['lat'], m['lon'])
          title = m.get('title', 'Cluster')
          users = m.get('users', [m.get('user_name', 'Unknown User')])
          hex_color = m.get('color', '#ADD8E6')
      
          # Construct a vector symbol icon using the tiered hex color from the server
          marker_symbol = self.map_1.Symbol(
              path=self.map_1.SymbolPath.CIRCLE,
              scale=12,
              fill_color=hex_color,
              fill_opacity=0.9,
              stroke_color='#FFFFFF',
              stroke_weight=2
          )
      
          marker = self.map_1.Marker(
              position=lat_lng,
              title=title,
              icon=marker_symbol,
              animation=self.map_1.Animation.DROP
          )
      
          def make_click_handler(cluster_title, user_list):
            def marker_click_handler(sender, **event_args):
              page_size = 25
              current_page = 0
              total_users = len(user_list)
              total_pages = max(1, (total_users + page_size - 1) // page_size)
            
              while True:
                start_idx = current_page * page_size
                end_idx = min(start_idx + page_size, total_users)
                page_users = user_list[start_idx:end_idx]
              
                formatted_users = "\n".join([f"• {u}" for u in page_users])
                page_info = f"Page {current_page + 1} of {total_pages} (Showing {start_idx + 1}-{end_idx} of {total_users})"
              
                content = f"{cluster_title}\n\n{page_info}\n\n{formatted_users}"
              
                buttons = []
                if current_page > 0:
                  buttons.append(("Previous", "prev"))
                if current_page < total_pages - 1:
                  buttons.append(("Next", "next"))
                buttons.append(("Close", None))
              
                action = alert(content=content, title="Cluster Users", large=True, buttons=buttons)
              
                if action == "next":
                  current_page += 1
                elif action == "prev":
                  current_page -= 1
                else:
                  break
            return marker_click_handler
        
          marker.set_event_handler('click', make_click_handler(title, users))
          self.map_1.add_component(marker)
      
        if markers:
          latest = markers[0]
          self.map_1.center = self.map_1.LatLng(latest['lat'], latest['lon'])
          self.map_1.zoom = 4
          
  def cluster_dropdown_change(self, sender, **event_args):
      """Triggered when the user changes the cluster type dropdown."""
      val = sender.selected_value
      is_radial = val and val.lower() in ['miles', 'kilometers', 'mi', 'km']
    
      # Toggle visibility based on whether radial clustering is selected
      self.Threshold_Label.visible = is_radial
      self.Threshold_Dropdown.visible = is_radial
    
      distance_val = None
      if is_radial:
        # Shift focus to the radius dropdown when it appears
        self.Threshold_Dropdown.focus()
        distance_val = self.Threshold_Dropdown.selected_value
      
      self.refresh_map_display(cluster_type=val, distance_value=distance_val)

  def threshold_dropdown_change(self, sender, **event_args):
    """Triggered when the user adjusts the radius threshold dropdown."""
    cluster_type_val = self.Cluster_Type_Dropdown.selected_value
    self.refresh_map_display(cluster_type=cluster_type_val, distance_value=sender.selected_value)

  def Info_Link_click(self, **event_args):
      """Triggered when the user clicks the info link."""
      alert(
          content="Clusters allow you to zoom in from Global Region down to Postal Code or select Miles/Kilometers and a radius to view the records at these levels.",
          title="Cluster Information",
          large=False
      )