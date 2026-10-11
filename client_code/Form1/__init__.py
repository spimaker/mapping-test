from ._anvil_designer import Form1Template
import math
import base64
import anvil
from anvil import *
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil import GoogleMap
import anvil.js

class Form1(Form1Template):

  def __init__(self, **properties):
    super().__init__(**properties)
    self.is_fullscreen = False
    # load test data
    # anvil.server.call('seed_test_data2')

    # delete test data by ID
    # anvil.server.call('delete_id_range')

    # Set Form properties and Data Bindings
    self.init_components(**properties)

    # Populate the Country DropDown from the server
    self.load_countries()

    # Populate cluster type dropdown options
    self.Cluster_Type_Dropdown.items = [
      ("Miles Perimeter", "miles"),
      ("Kilometers Perimeter", "kilometers"),
      ("Postal Code", "postal"),
      ("City", "city"),
      ("State", "state"),
      ("Country", "country")
    ]

    # Populate distance threshold dropdown options
    self.Threshold_Dropdown.items = [
      ('1 mile/km', 1),
      ('5 miles/km', 5),
      ('10 miles/km', 10),
      ('25 miles/km', 25),
      ('50 miles/km', 50),
      ('100 miles/km', 100)
    ]

    # Set default selections
    self.Cluster_Type_Dropdown.selected_value = 'country'
    # self.Cluster_Type_Dropdown.selected_value = 'miles'
    # self.Threshold_Dropdown.selected_value = 25

    # Set initial threshold visibility
    self.update_threshold_visibility()

    # Safely listen for the Escape key globally
    anvil.js.window.addEventListener('keydown', lambda e: self.handle_keydown(e))

    # Load all of the clusters
    self.Load_Clusters_Button_click()

  def load_countries(self):
    """Fetch sorted list of countries from the server module"""
    try:
      country_items = anvil.server.call('get_country_list')
      self.Country_Code_Value.items = country_items
    except Exception as e:
      print(f"Error loading countries: {e}")

  def update_threshold_visibility(self):
    """Shows or hides the threshold controls depending on the cluster type"""
    selected_type = self.Cluster_Type_Dropdown.selected_value
    is_distance = selected_type in ['miles', 'kilometers']

    self.Threshold_Label.visible = is_distance
    self.Threshold_Dropdown.visible = is_distance

  @anvil.handle("Cluster_Type_Dropdown", "change")
  def Cluster_Type_Dropdown_change(self, **event_args):
    """Triggered automatically when the user changes the cluster type"""
    self.update_threshold_visibility()
    self.Load_Clusters_Button_click()

  @anvil.handle("Save_Button", "click")
  def save_button_click(self, **event_args):
    """This method is called when the Save button is clicked"""
    form_data = self._get_address_input_data()

    try:
      result = anvil.server.call('save_map_item', form_data)
      status = result.get('status')
      lat = result.get('latitude')
      lon = result.get('longitude')

      if status == 'duplicate':
        anvil.alert("Warning: This is a duplicate record and was not saved.", title="Duplicate Detected")
      elif status == 'saved':
        anvil.Notification("Successfully saved! Loading map...").show()

      # Set cluster view to 1-mile perimeter on save
      self.Cluster_Type_Dropdown.selected_value = 'miles'
      self.update_threshold_visibility()
      self.Threshold_Dropdown.selected_value = 1

      # Reload clusters so the new record is included and clickable
      self.Load_Clusters_Button_click()

      # Center and zoom onto the newly saved coordinate
      if lat and lon:
        self.map_1.center = GoogleMap.LatLng(lat, lon)
        self.map_1.zoom = 13

    except Exception as e:
      anvil.alert(f"An error occurred: {e}")

  @anvil.handle("Search_Button", "click")
  def search_button_click(self, **event_args):
    """This method is called when the Search button is clicked"""
    search_data = self._get_address_input_data()

    # Check if at least one primary address field has text
    active_fields = [
      search_data['Address1_Value'], search_data['City_Value'], 
      search_data['State_Province_Region_Value'], search_data['Postal_Code_Value']
    ]
    if not any(active_fields) and not search_data['Country_Code_Value']:
      anvil.alert("Please enter search parameters in at least one field.", title="Empty Search")
      return

    try:
      anvil.Notification("Searching map records...").show()

      # Call server to process search logic (10-mile radius for full address, or regional match)
      search_result = anvil.server.call('search_map_items_by_fields', search_data)

      clusters = search_result.get('clusters', [])
      center_lat = search_result.get('latitude')
      center_lon = search_result.get('longitude')
      zoom_level = search_result.get('zoom', 11)

      self.map_1.clear()

      # Plot search results
      for i, cluster in enumerate(clusters):
        lat = cluster['latitude']
        lon = cluster['longitude']
        count = cluster['count']
        color = cluster['color']
        label = cluster['label']
        usernames = cluster['usernames']
        sub_label = cluster.get('sub_label')

        icon_url = self.create_numbered_icon(count, color, sub_label)

        marker = GoogleMap.Marker(
          position=GoogleMap.LatLng(lat, lon),
          icon=icon_url
        )

        marker.set_event_handler('click', lambda *args, un=usernames, lbl=label, **kwargs: self.show_paginated_users(un, lbl))
        self.map_1.add_component(marker)

      # Center and zoom onto search results
      if center_lat and center_lon:
        self.map_1.center = GoogleMap.LatLng(center_lat, center_lon)
        self.map_1.zoom = zoom_level

      anvil.Notification(f"Found {len(clusters)} matching locations!").show()

    except Exception as e:
      anvil.alert(f"Search error: {e}")   

  @anvil.handle("Load_Clusters_Button", "click")
  def Load_Clusters_Button_click(self, **event_args):
    """Triggered when loading and plotting clusters"""
    cluster_type = self.Cluster_Type_Dropdown.selected_value
    threshold = self.Threshold_Dropdown.selected_value if cluster_type in ['miles', 'kilometers'] else None

    try:
      clusters = anvil.server.call('get_clustered_data', cluster_type=cluster_type, threshold=threshold)
      self.map_1.clear()

      for i, cluster in enumerate(clusters):
        lat = cluster['latitude']
        lon = cluster['longitude']
        count = cluster['count']
        color = cluster['color']
        label = cluster['label']
        usernames = cluster['usernames']
        sub_label = cluster.get('sub_label')

        icon_url = self.create_numbered_icon(count, color, sub_label)

        marker = GoogleMap.Marker(
          position=GoogleMap.LatLng(lat, lon),
          icon=icon_url
        )

        marker.set_event_handler('click', lambda *args, un=usernames, lbl=label, **kwargs: self.show_paginated_users(un, lbl))
        self.map_1.add_component(marker)

        if i == 0 and lat and lon:
          self.map_1.center = GoogleMap.LatLng(lat, lon)
          self.map_1.zoom = 6 if cluster_type in ['state', 'country'] else 11

      anvil.Notification(f"Loaded {len(clusters)} clusters successfully!").show()

    except Exception as e:
      anvil.alert(f"Error loading clusters: {e}")

  def create_numbered_icon(self, count, color_hex, sub_label=None):
    """Generates a circular cluster badge using base64 encoding"""
    if sub_label:
      svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56">
            <circle cx="28" cy="28" r="26" fill="{color_hex}" stroke="#FFFFFF" stroke-width="2.5"/>
            <text x="28" y="20" font-size="12" font-weight="bold" fill="#111111" text-anchor="middle" dominant-baseline="middle">{count}</text>
            <text x="28" y="35" font-size="8.5" font-weight="bold" fill="#222222" text-anchor="middle" dominant-baseline="middle">{sub_label}</text>
        </svg>"""
    else:
      svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
            <circle cx="20" cy="20" r="18" fill="{color_hex}" stroke="#FFFFFF" stroke-width="2.5"/>
            <text x="20" y="20.5" font-size="13" font-weight="bold" fill="#111111" text-anchor="middle" dominant-baseline="middle">{count}</text>
        </svg>"""

    encoded_svg = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{encoded_svg}"

  def show_paginated_users(self, usernames, cluster_label):
    """Opens a paginated dialog displaying users, then restores full screen on close"""
    was_fullscreen = self.is_fullscreen

    # If we are in full screen, temporarily exit so the alert renders cleanly
    if was_fullscreen:
      self.is_fullscreen = False
      map_element = anvil.js.get_dom_node(self.map_1)
      map_element.classList.remove('map-fullscreen')
      map_element.style.position = ""
      map_element.style.zIndex = ""
      self.fullscreen_button.text = "Expand Map"
      anvil.js.window.dispatchEvent(anvil.js.window.Event('resize'))
      map_element.dispatchEvent(anvil.js.window.Event('resize'))

    page_size = 50
    total_pages = max(1, math.ceil(len(usernames) / page_size))
    current_page = 1

    try:
      while True:
        start = (current_page - 1) * page_size
        end = start + page_size
        page_items = usernames[start:end]

        list_display = "\n".join([f"• {name}" for name in page_items]) if page_items else "No users on this page."

        content_text = (
          f"Cluster: {cluster_label}\n"
          f"Total Records: {len(usernames)}\n"
          f"Page {current_page} of {total_pages}\n\n"
          f"{list_display}"
        )

        buttons = [("Close", "close")]
        if current_page > 1:
          buttons.insert(0, ("Previous Page", "prev"))
        if current_page < total_pages:
          buttons.append(("Next Page", "next"))

        action = anvil.alert(content=content_text, title="Cluster Records", buttons=buttons)

        if action == "next":
          current_page += 1
        elif action == "prev":
          current_page -= 1
        else:
          break
    finally:
      # Automatically pop back into full screen once the dialog is closed (via X or Close button)
      if was_fullscreen:
        def restore_fullscreen():
          self.is_fullscreen = True
          map_element = anvil.js.get_dom_node(self.map_1)
          map_element.classList.add('map-fullscreen')
          self.fullscreen_button.text = "Exit Full Screen"
          anvil.js.window.dispatchEvent(anvil.js.window.Event('resize'))
          map_element.dispatchEvent(anvil.js.window.Event('resize'))

        anvil.js.window.setTimeout(restore_fullscreen, 100)

  @anvil.handle("fullscreen_button", "click")
  def toggle_fullscreen(self, *args, **kwargs):
    """Shared helper to handle fullscreen state"""
    self.is_fullscreen = not self.is_fullscreen
    map_element = anvil.js.get_dom_node(self.map_1)

    if self.is_fullscreen:
      map_element.classList.add('map-fullscreen')
      self.fullscreen_button.text = "Exit Full Screen"
    else:
      map_element.classList.remove('map-fullscreen')
      map_element.style.position = ""
      map_element.style.zIndex = ""
      self.fullscreen_button.text = "Expand Map"

    # Force the browser window and the map DOM element to recalculate dimensions safely
    anvil.js.window.dispatchEvent(anvil.js.window.Event('resize'))
    map_element.dispatchEvent(anvil.js.window.Event('resize'))

  def fullscreen_button_click(self, **event_args):
    """Triggered when clicking the button"""
    self.toggle_fullscreen()

  def handle_keydown(self, event):
    """Triggered globally when any key is pressed"""
    if getattr(event, 'key', '') == 'Escape' and self.is_fullscreen:
      self.toggle_fullscreen()

  def _get_address_input_data(self):
    """Helper method to collect form input values cleanly and avoid duplication."""
    return {
      'User_Name_Value': self.User_Name_Value.text if hasattr(self, 'User_Name_Value') else None,
      'Address1_Value': self.Address1_Value.text,
      'Address2_Value': self.Address2_Value.text,
      'City_Value': self.City_Value.text,
      'State_Province_Region_Value': self.State_Province_Region_Value.text,
      'Postal_Code_Value': self.Postal_Code_Value.text,
      'Country_Code_Value': self.Country_Code_Value.selected_value,
      'Latitude_Value': float(self.Latitude_Value.text) if getattr(self, 'Latitude_Value', None) and self.Latitude_Value.text else None,
      'Longitude_Value': float(self.Longitude_Value.text) if getattr(self, 'Longitude_Value', None) and self.Longitude_Value.text else None,
      'Formatted_Address_Value': self.Formatted_Address_Value.text if hasattr(self, 'Formatted_Address_Value') else None
    }   