from ._anvil_designer import MapEntryTemplate
import anvil.server

class MapEntry(MapEntryTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings
    self.init_components(**properties)
    self.last_saved_record_id = None
    
    # Load initial country options on startup
    try:
      self.Country_Code_Value.items = anvil.server.call('get_country_list')
    except Exception as e:
      print(f"Error loading initial country list: {e}")
      
    # Initial map marker population
    self.refresh_map_display()

  def clear_button_click(self, **event_args):
      """Clears all input fields and resets dropdown selections."""
      self.User_Name_Value.text = ""
    
      self.Country_Code_Value.selected_value = None
      self.State_Province_Region_Value.selected_value = None
      self.City_Value.selected_value = None
      self.City_Value.items = [("<Select City>", None)]
    
      # Hide custom city inputs on clear
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
    """Saves the record to the database and updates the map display."""
    try:
      record_data = {
          'user_name': self.User_Name_Value.text,
          'country_code': self.Country_Code_Value.selected_value,
          'state_province_region': self.State_Province_Region_Value.selected_value,
          'city': self.City_Value.selected_value,
          'custom_city': self.Custom_City_TextBox.text,
          'postal_code': self.Postal_Code_Value.text,
          'address1': self.Address1_Value.text,
          'address2': self.Address2_Value.text,
          'latitude': float(self.Latitude_Value.text) if self.Latitude_Value.text else None,
          'longitude': float(self.Longitude_Value.text) if self.Longitude_Value.text else None,
          'formatted_address': self.Formatted_Address_Value.text,
      }
      
      # Call server function to save and return the new record ID
      self.last_saved_record_id = anvil.server.call('save_map_item', record_data)
      
      # Refresh map to highlight the newly saved record
      self.refresh_map_display()
    except Exception as e:
      print(f'Error saving record: {e}')

  def search_button_click(self, **event_args):
    """Handles address lookup / geocoding search logic."""
    try:
      address_query = {
          'address1': self.Address1_Value.text,
          'address2': self.Address2_Value.text,
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
      print(f'Error during search/geocoding: {e}')

  def full_screen_map_button_click(self, **event_args):
    """Opens the full screen map view form."""
    try:
      anvil.open_form('FullScreenMapForm')
    except Exception as e:
      print(f'Error opening full screen map: {e}')

  def country_dropdown_change(self, **event_args):
    """Cascades country selection to update states/regions."""
    selected_country = self.Country_Code_Value.selected_value
    
    # Reset dependent dropdowns
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
      """Cascades state selection to update cities by passing both country and state codes."""
      selected_country = self.Country_Code_Value.selected_value
      selected_state = self.State_Province_Region_Value.selected_value
    
      # Reset city dropdown with the default prompt so it doesn't show <invalid value>
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
      """Triggered when the city dropdown selection changes. Toggles custom city fields."""
      selected_city = self.City_Value.selected_value
    
      if selected_city == "MANUAL_ENTRY":
        self.Custom_City_Label.visible = True
        self.Custom_City_TextBox.visible = True
        self.Custom_City_TextBox.focus()
      else:
        self.Custom_City_Label.visible = False
        self.Custom_City_TextBox.visible = False
        self.Custom_City_TextBox.text = ""

        
  def refresh_map_display(self, **event_args):
    """Reloads map markers reflecting current visibility and active record, showing usernames."""
    show_actuals = (
        self.Show_Actuals_Checkbox.checked
        if hasattr(self, 'Show_Actuals_Checkbox')
        else True
    )

    try:
      markers = anvil.server.call(
          'get_map_markers_with_privacy_view',
          active_record_id=getattr(self, 'last_saved_record_id', None),
          show_actuals=show_actuals,
      )

      if hasattr(self, 'map_1'):
        self.map_1.clear()
        
        for m in markers:
          lat_lng = anvil.GoogleMap.LatLng(m['latitude'], m['longitude'])
          marker = anvil.GoogleMap.Marker(
              position=lat_lng,
              title=m['user_name']  # Displays only the user's name on the marker
          )
        
          if m['color'] == 'red':
            marker.icon = anvil.GoogleMap.Icon(url="http://maps.google.com/mapfiles/ms/icons/red-dot.png")
          elif m['color'] == 'green':
            marker.icon = anvil.GoogleMap.Icon(url="http://maps.google.com/mapfiles/ms/icons/green-dot.png")
          else:
            marker.icon = anvil.GoogleMap.Icon(url="http://maps.google.com/mapfiles/ms/icons/blue-dot.png")

          self.map_1.add_component(marker)

    except Exception as e:
      print(f'Error refreshing map markers: {e}')