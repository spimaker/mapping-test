from ._anvil_designer import MapEntryTemplate
import math
import base64
import anvil
from anvil import *
import anvil.users
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil import GoogleMap
import anvil.js

class MapEntry(MapEntryTemplate):
  def __init__(self, **properties):
    super().__init__(**properties)
    self.is_fullscreen = False
    self.current_lat = 34.0522
    self.current_lon = -118.2437

    # Track the last executed search parameters so we can re-cluster on the fly
    self.last_search_data = None

    # Set Form properties and Data Bindings
    self.init_components(**properties)

    # Initialize UI elements and event listeners
    self._setup_dropdowns()
    self._setup_global_listeners()

    # Load initial map and floating utilities
    self.initialize_map_with_geolocation()
    self.add_floating_locate_button()

  # ==========================================
  # 1. INITIALIZATION & SETUP HELPERS
  # ==========================================
  def _setup_dropdowns(self):
    """Populates dropdown options and default selections."""
    try:
      country_items = anvil.server.call('get_country_list')
      self.Country_Code_Value.items = [("-- Select Country --", None)] + country_items
      self.Country_Code_Value.selected_value = None
    except Exception as e:
      print(f"Error loading countries: {e}")

    self.Cluster_Type_Dropdown.items = [
      ("Global Region", "global_region"),
      ("Country", "country"),
      ("State / Province", "state"),
      ("City", "city"),
      ("Postal Code", "postal"),
      ("Miles Radius", "miles"),
      ("Kilometers Radius", "kilometers")
    ]

    self.Threshold_Dropdown.items = [
      ('1 mile/km', 1), ('5 miles/km', 5), ('10 miles/km', 10),
      ('25 miles/km', 25), ('50 miles/km', 50), ('100 miles/km', 100)
    ]

    self.Cluster_Type_Dropdown.selected_value = 'miles'
    self.Threshold_Dropdown.selected_value = 25
    self.update_threshold_visibility()

  def _setup_global_listeners(self):
    """Attaches window-level event listeners like ESC key support."""
    anvil.js.window.addEventListener('keydown', lambda e: self.handle_keydown(e))

  def update_threshold_visibility(self):
    """Shows or hides distance threshold dropdowns based on cluster type."""
    is_distance = self.Cluster_Type_Dropdown.selected_value in ['miles', 'kilometers']
    self.Threshold_Label.visible = is_distance
    self.Threshold_Dropdown.visible = is_distance

  # ==========================================
  # 2. MAP & CLUSTER RENDERING
  # ==========================================
  def display_clusters_on_map(self, result):
    """Renders markers and clusters onto the map component."""
    clusters = result.get('clusters', [])
    lat, lon, zoom = result.get('latitude'), result.get('longitude'), result.get('zoom', 11)

    self.map_1.clear()

    for cluster in clusters:
      icon_url = self.create_numbered_icon(cluster['count'], cluster['color'], cluster.get('sub_label'))
      marker = GoogleMap.Marker(
        position=GoogleMap.LatLng(cluster['latitude'], cluster['longitude']),
        icon=icon_url
      )
      marker.set_event_handler(
        'click', 
        lambda *args, un=cluster['usernames'], lbl=cluster['label'], **kw: self.show_paginated_users(un, lbl)
      )
      self.map_1.add_component(marker)

    if lat and lon:
      self.map_1.center = GoogleMap.LatLng(lat, lon)
      self.map_1.zoom = zoom

  def create_numbered_icon(self, count, color_hex, sub_label=None):
    """Generates an SVG cluster badge using base64 encoding."""
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

  # ==========================================
  # 3. BUTTON CLICK & EVENT HANDLERS
  # ==========================================
  @anvil.handle("Cluster_Type_Dropdown", "change")
  def Cluster_Type_Dropdown_change(self, **event_args):
    self.update_threshold_visibility()
    # If we have an active search, re-run the search with the new cluster type; otherwise load global clusters
    if self.last_search_data:
      self.rerun_last_search()
    else:
      self.Load_Clusters_Button_click()

  @anvil.handle("Threshold_Dropdown", "change")
  def Threshold_Dropdown_change(self, **event_args):
    """Re-runs the search or re-loads clusters when the distance threshold changes."""
    if self.last_search_data:
      self.rerun_last_search()
    else:
      self.Load_Clusters_Button_click()

  @anvil.handle("Load_Clusters_Button", "click")
  def Load_Clusters_Button_click(self, **event_args):
    """Loads and plots clusters while maintaining current map position."""
    cluster_type = self.Cluster_Type_Dropdown.selected_value
    threshold = self.Threshold_Dropdown.selected_value if cluster_type in ['miles', 'kilometers'] else None

    try:
      clusters = anvil.server.call('get_clustered_data', cluster_type=cluster_type, threshold=threshold)
      result = {
        'clusters': clusters,
        'latitude': self.current_lat,
        'longitude': self.current_lon,
        'zoom': self.map_1.zoom
      }
      self.display_clusters_on_map(result)
      anvil.Notification(f"Loaded {len(clusters)} clusters successfully!").show()
    except Exception as e:
      anvil.alert(f"Error loading clusters: {e}")

  @anvil.handle("Save_Button", "click")
  def save_button_click(self, **event_args):
    if not self.Country_Code_Value.selected_value:
      anvil.alert("Please select a country before saving.", title="Country Required")
      return

    form_data = self._get_address_input_data()
    try:
      result = anvil.server.call('save_map_item', form_data)
      status, lat, lon = result.get('status'), result.get('latitude'), result.get('longitude')

      if status == 'duplicate':
        anvil.alert("Warning: This is a duplicate record and was not saved.", title="Duplicate Detected")
      elif status == 'saved':
        anvil.Notification("Successfully saved! Loading map...").show()

      self.Cluster_Type_Dropdown.selected_value = 'miles'
      self.update_threshold_visibility()
      self.Threshold_Dropdown.selected_value = 1
      self.Load_Clusters_Button_click()

      if lat and lon:
        self.map_1.center = GoogleMap.LatLng(lat, lon)
        self.map_1.zoom = 13
    except Exception as e:
      anvil.alert(f"An error occurred: {e}")

  @anvil.handle("Search_Button", "click")
  def search_button_click(self, **event_args):
    if not self.Country_Code_Value.selected_value:
      anvil.alert("Please select a country to search within.", title="Country Required")
      return

    search_data = self._get_address_input_data()
    search_data['cluster_type'] = self.Cluster_Type_Dropdown.selected_value
    search_data['threshold'] = self.Threshold_Dropdown.selected_value if self.Cluster_Type_Dropdown.selected_value in ['miles', 'kilometers'] else None

    # Save search criteria for dynamic re-clustering
    self.last_search_data = search_data
    self.execute_search(search_data)

  def rerun_last_search(self):
    """Re-runs the last active search using updated dropdown parameters (like cluster type)."""
    if not self.last_search_data:
      return
    # Update cluster settings in stored criteria
    self.last_search_data['cluster_type'] = self.Cluster_Type_Dropdown.selected_value
    self.last_search_data['threshold'] = self.Threshold_Dropdown.selected_value if self.Cluster_Type_Dropdown.selected_value in ['miles', 'kilometers'] else None

    self.execute_search(self.last_search_data)

  def execute_search(self, search_data):
    """Sends search data to server and renders map results."""
    try:
      result = anvil.server.call('search_map_items_by_fields', search_data)

      if result.get('status') == 'disambiguation_needed':
        options = result['options']
        dropdown_items = [(opt['display_name'], opt) for opt in options]
        selection_dropdown = DropDown(items=dropdown_items)

        user_chose = alert(
          content=selection_dropdown,
          title="Multiple Locations Found",
          buttons=[("Select Location", True), ("Cancel", False)]
        )

        if user_chose and selection_dropdown.selected_value:
          chosen_opt = selection_dropdown.selected_value
          search_data['Selected_Latitude'] = chosen_opt['latitude']
          search_data['Selected_Longitude'] = chosen_opt['longitude']
          self.City_Value.text = chosen_opt['city']
          self.State_Province_Region_Value.text = chosen_opt['state']
          result = anvil.server.call('search_map_items_by_fields', search_data)
        else:
          return

      self.display_clusters_on_map(result)
    except Exception as e:
      alert(str(e))

  @anvil.handle("Clear_Button", "click")
  def clear_button_click(self, **event_args):
    text_fields = [
      'User_Name_Value', 'Address1_Value', 'Address2_Value', 'City_Value', 
      'State_Province_Region_Value', 'Postal_Code_Value', 'Latitude_Value', 
      'Longitude_Value', 'Formatted_Address_Value'
    ]
    for field_name in text_fields:
      if hasattr(self, field_name) and getattr(self, field_name):
        getattr(self, field_name).text = ""

    if hasattr(self, 'Country_Code_Value'):
      self.Country_Code_Value.selected_value = None

    self.last_search_data = None
    anvil.Notification("Form cleared.").show()

  # ==========================================
  # 4. GEOLOCATION & FLOATING UI HELPERS
  # ==========================================
  def initialize_map_with_geolocation(self):
    """Loads all clusters on startup using default LA fallback."""
    def fetch_and_display(lat, lon, zoom_level):
      try:
        self.current_lat, self.current_lon = lat, lon
        clusters = anvil.server.call('get_clustered_data', cluster_type='miles', threshold=25)
        result = {'clusters': clusters, 'latitude': lat, 'longitude': lon, 'zoom': zoom_level}
        self.display_clusters_on_map(result)
      except Exception as e:
        anvil.alert(f"Error loading clusters: {e}")

    fetch_and_display(34.0522, -118.2437, 10)

  def add_floating_locate_button(self):
    """Dynamically injects a floating 'Locate Me' button."""
    btn_id = "floating-locate-me-btn"
    if not anvil.js.window.document.getElementById(btn_id):
      btn = anvil.js.window.document.createElement('button')
      btn.id = btn_id
      btn.innerText = "📍 Locate Me"
      btn.style.cssText = """
        position: fixed; bottom: 20px; right: 20px; z-index: 99999;
        background: #ffffff; color: #222222; border: 2px solid #ccc;
        padding: 10px 16px; font-weight: bold; font-size: 14px;
        border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); cursor: pointer;
      """
      btn.onclick = lambda e: self.locate_me_action()
      anvil.js.window.document.body.appendChild(btn)

  @anvil.handle("Locate_Me_Button", "click")
  def locate_me_button_click(self, **event_args):
    self.locate_me_action()

  def locate_me_action(self):
    """Requests mobile browser geolocation when tapped."""
    def success(position):
      try:
        self.current_lat = position.coords.latitude
        self.current_lon = position.coords.longitude
        clusters = anvil.server.call('get_clustered_data', cluster_type='miles', threshold=25)
        result = {'clusters': clusters, 'latitude': self.current_lat, 'longitude': self.current_lon, 'zoom': 11}
        self.display_clusters_on_map(result)
        anvil.Notification("Centered on your location!").show()
      except Exception as e:
        anvil.alert(f"Error centering location: {e}")

    def error(err):
      anvil.alert("Unable to retrieve your location. Please check browser permissions.")

    if hasattr(anvil.js.window.navigator, 'geolocation'):
      anvil.js.window.navigator.geolocation.getCurrentPosition(success, error, {'timeout': 10000, 'maximumAge': 60000})
    else:
      anvil.alert("Geolocation is not supported by your browser.")

  # ==========================================
  # 5. FULLSCREEN & PAGINATION HELPERS
  # ==========================================
  @anvil.handle("fullscreen_button", "click")
  def fullscreen_button_click(self, **event_args):
    self.toggle_fullscreen()

  def toggle_fullscreen(self, *args, **kwargs):
    self.is_fullscreen = not self.is_fullscreen
    map_element = anvil.js.get_dom_node(self.map_1)
    exit_btn_id = "mobile-exit-fullscreen-btn"
    existing_btn = anvil.js.window.document.getElementById(exit_btn_id)

    if self.is_fullscreen:
      map_element.classList.add('map-fullscreen')
      self.fullscreen_button.text = "Exit Full Screen"
      if not existing_btn:
        btn = anvil.js.window.document.createElement('button')
        btn.id = exit_btn_id
        btn.innerText = "✕ Exit Full Screen"
        btn.style.cssText = """
          position: fixed; top: 15px; right: 15px; z-index: 100000;
          background: #ffffff; color: #222222; border: 2px solid #ccc;
          padding: 10px 16px; font-weight: bold; font-size: 14px;
          border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); cursor: pointer;
        """
        btn.onclick = lambda e: self.toggle_fullscreen()
        anvil.js.window.document.body.appendChild(btn)
    else:
      map_element.classList.remove('map-fullscreen')
      map_element.style.position = ""
      map_element.style.zIndex = ""
      self.fullscreen_button.text = "Expand Map"
      if existing_btn:
        existing_btn.remove()

    anvil.js.window.dispatchEvent(anvil.js.window.Event('resize'))
    map_element.dispatchEvent(anvil.js.window.Event('resize'))

  def handle_keydown(self, event):
    """Handles window-level key events (e.g., ESC to exit fullscreen)."""
    if getattr(event, 'key', '') == 'Escape' and self.is_fullscreen:
      self.toggle_fullscreen()

  def show_paginated_users(self, usernames, cluster_label):
    was_fullscreen = self.is_fullscreen
    if was_fullscreen:
      self.toggle_fullscreen()

    page_size, total_pages, current_page = 50, max(1, math.ceil(len(usernames) / 50)), 1

    try:
      while True:
        start = (current_page - 1) * page_size
        page_items = usernames[start:start + page_size]
        list_display = "\n".join([f"• {name}" for name in page_items]) if page_items else "No users."

        content_text = f"Cluster: {cluster_label}\nTotal Records: {len(usernames)}\nPage {current_page} of {total_pages}\n\n{list_display}"
        buttons = [("Close", "close")]
        if current_page > 1: buttons.insert(0, ("Previous Page", "prev"))
        if current_page < total_pages: buttons.append(("Next Page", "next"))

        action = anvil.alert(content=content_text, title="Cluster Records", buttons=buttons)
        if action == "next": current_page += 1
        elif action == "prev": current_page -= 1
        else: break
    finally:
      if was_fullscreen:
        anvil.js.window.setTimeout(lambda: self.toggle_fullscreen(), 100)

  def _get_address_input_data(self):
    """Packages all address input fields into a dictionary for server calls."""
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