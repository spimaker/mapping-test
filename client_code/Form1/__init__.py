from ._anvil_designer import Form1Template
import anvil
import anvil.server
from anvil import GoogleMap

class Form1(Form1Template):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings
    self.init_components(**properties)

    # Populate the Country DropDown from the server
    self.load_countries()

  def load_countries(self):
    try:
      # Fetch sorted list of countries from the server module
      country_items = anvil.server.call('get_country_list')

      # Anvil DropDown items take a list of tuples: (Label, Value)
      # e.g., [("United States", "US"), ("Canada", "CA"), ...]
      self.Country_Code_Value.items = country_items

    except Exception as e:
      print(f"Error loading countries: {e}")

  @anvil.handle("Save_Button", "click")
  def save_button_click(self, **event_args):
    """This method is called when the Save button is clicked"""

    form_data = {
      'User_Name_Value': self.User_Name_Value.text,
      'Address1_Value': self.Address1_Value.text,
      'Address2_Value': self.Address2_Value.text,
      'City_Value': self.City_Value.text,
      'State_Province_Region_Value': self.State_Province_Region_Value.text,
      'Postal_Code_Value': self.Postal_Code_Value.text,
      'Country_Code_Value': self.Country_Code_Value.selected_value,
      'Latitude_Value': float(self.Latitude_Value.text) if self.Latitude_Value.text else None,
      'Longitude_Value': float(self.Longitude_Value.text) if self.Longitude_Value.text else None,
      'Formatted_Address_Value': self.Formatted_Address_Value.text
    }

    try:
      result = anvil.server.call('save_map_item', form_data)

      status = result.get('status')
      current_id = result.get('id')
      lat = result.get('latitude')
      lon = result.get('longitude')
      formatted_addr = result.get('formatted_address')
      all_items = result.get('all_items', [])

      if status == 'duplicate':
        anvil.alert("Warning: This is a duplicate record and was not saved.", title="Duplicate Detected")

      # Clear the map before plotting all markers
      self.map_1.clear()

      # Loop through all items and place markers (Blue for current, Red for others)
      for item in all_items:
        item_lat = item.get('latitude')
        item_lon = item.get('longitude')

        if item_lat and item_lon:
          # Check if this item is the current/newly processed address
          is_current = (item.get('id') == current_id)

          # Google Maps default marker URL colors or standard icons can be applied via icon property, 
          # or we can use Google Maps standard marker tinting logic:
          marker_kwargs = {
            'position': GoogleMap.LatLng(item_lat, item_lon),
            'animation': GoogleMap.Animation.DROP if is_current else None
          }

          # Assign custom icon color (Blue for current address, Red for others)
          if is_current:
            marker_kwargs['icon'] = "http://maps.google.com/mapfiles/ms/icons/blue-dot.png"
          else:
            marker_kwargs['icon'] = "http://maps.google.com/mapfiles/ms/icons/red-dot.png"

          marker = GoogleMap.Marker(**marker_kwargs)
          self.map_1.add_component(marker)

      # Focus the map view on the current address location
      if lat and lon:
        self.map_1.center = GoogleMap.LatLng(lat, lon)
        self.map_1.zoom = 15

        if status == 'saved':
          anvil.Notification("Successfully saved, mapped, and loaded all locations!").show()

    except Exception as e:
      anvil.alert(f"An error occurred: {e}")
    
