import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ._anvil_designer import MapEntryTemplate


class MapEntry(MapEntryTemplate):

  def __init__(self, **properties):
    self.init_components(**properties)
    self._setup_dropdowns()

    # Wire up change events explicitly if not bound in the Anvil designer
    if hasattr(self, 'Country_Code_Value'):
      self.Country_Code_Value.set_event_handler('change', self.country_dropdown_change)
    if hasattr(self, 'State_Province_Region_Value'):
      self.State_Province_Region_Value.set_event_handler('change', self.state_dropdown_change)
    if hasattr(self, 'City_Value'):
      self.City_Value.set_event_handler('change', self.city_dropdown_change)

    # Hide custom city components by default on load
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False
    if hasattr(self, 'Custom_City_Label'):
      self.Custom_City_Label.visible = False

  def _setup_dropdowns(self):
    """Populates initial options and default selections."""
    try:
      country_items = anvil.server.call('get_country_list')
      if hasattr(self, 'Country_Code_Value'):
        self.Country_Code_Value.items = [('-- Select Country --', None)] + country_items
        self.Country_Code_Value.selected_value = None
    except Exception as e:
      print(f'Error loading countries: {e}')

    if hasattr(self, 'Cluster_Type_Dropdown'):
      self.Cluster_Type_Dropdown.items = [
          ('Global Region', 'global_region'),
          ('Country', 'country'),
          ('State / Province', 'state'),
          ('City', 'city'),
          ('Postal Code', 'postal'),
          ('Miles Radius', 'miles'),
          ('Kilometers Radius', 'kilometers'),
      ]

    if hasattr(self, 'State_Province_Region_Value'):
      self.State_Province_Region_Value.items = [('-- Select State / Province --', None)]
      self.State_Province_Region_Value.selected_value = None

    if hasattr(self, 'City_Value'):
      self.City_Value.items = [('-- Select City --', None)]
      self.City_Value.selected_value = None

  def country_dropdown_change(self, **event_args):
    """Triggered when user selects a country; populates state subdivisions."""
    if not hasattr(self, 'Country_Code_Value'):
      return
    selected_country = self.Country_Code_Value.selected_value

    if hasattr(self, 'State_Province_Region_Value'):
      self.State_Province_Region_Value.selected_value = None
      self.State_Province_Region_Value.items = [('-- Select State / Province --', None)]

    if hasattr(self, 'City_Value'):
      self.City_Value.selected_value = None
      self.City_Value.items = [('-- Select City --', None)]

    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False
      self.Custom_City_TextBox.text = ''
    if hasattr(self, 'Custom_City_Label'):
      self.Custom_City_Label.visible = False

    if not selected_country:
      return

    try:
      subdivisions = anvil.server.call('get_subdivisions_for_country', selected_country)
      if hasattr(self, 'State_Province_Region_Value'):
        self.State_Province_Region_Value.items = [('-- Select State / Province --', None)] + subdivisions
    except Exception as e:
      print(f'Error fetching subdivisions: {e}')

  def state_dropdown_change(self, **event_args):
    """Triggered when user selects a state; populates cities with 'Other' option."""
    if not hasattr(self, 'Country_Code_Value') or not hasattr(self, 'State_Province_Region_Value'):
      return

    selected_country = self.Country_Code_Value.selected_value
    selected_state = self.State_Province_Region_Value.selected_value

    if hasattr(self, 'City_Value'):
      self.City_Value.selected_value = None
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False
      self.Custom_City_TextBox.text = ''
    if hasattr(self, 'Custom_City_Label'):
      self.Custom_City_Label.visible = False

    if not selected_state or not selected_country:
      if hasattr(self, 'City_Value'):
        self.City_Value.items = [('-- Select City --', None)]
      return

    try:
      cities = anvil.server.call('get_cities_for_state', selected_country, selected_state)
      if hasattr(self, 'City_Value'):
        self.City_Value.items = [('-- Select City --', None)] + cities + [('Other (Enter manually)...', 'OTHER_CUSTOM_CITY')]
    except Exception as e:
      print(f'Error fetching cities: {e}')
      if hasattr(self, 'City_Value'):
        self.City_Value.items = [
            ('-- Select City --', None),
            ('Other (Enter manually)...', 'OTHER_CUSTOM_CITY'),
        ]

  def city_dropdown_change(self, **event_args):
    """Triggered when user selects a city; toggles manual entry fields for 'Other'."""
    if not hasattr(self, 'City_Value'):
      return

    is_custom = self.City_Value.selected_value == 'OTHER_CUSTOM_CITY'

    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = is_custom
      if is_custom:
        self.Custom_City_TextBox.text = ''
        self.Custom_City_TextBox.focus()
      else:
        self.Custom_City_TextBox.text = ''

    if hasattr(self, 'Custom_City_Label'):
      self.Custom_City_Label.visible = is_custom

  def save_button_click(self, **event_args):
      """Triggered when the user clicks the save/submit button."""
    
      # 1. Resolve city value: use Custom_City_TextBox if 'Other' was selected, otherwise use the dropdown value
      city_value = (
          self.Custom_City_TextBox.text.strip()
          if getattr(self, 'City_Value', None) and self.City_Value.selected_value == 'OTHER_CUSTOM_CITY'
          else getattr(self.City_Value, 'selected_value', '')
      )

      # 2. Gather all form data into a dictionary
      form_data = {
          'User_Name_Value': self.User_Name_Value.text,
          'Address1_Value': self.Address1_Value.text,
          'Address2_Value': self.Address2_Value.get_text() if hasattr(self.Address2_Value, 'get_text') else '',
          'City_Value': city_value,
          'State_Province_Region_Value': self.State_Province_Region_Value.selected_value,
          'Postal_Code_Value': self.Postal_Code_Value.text,
          'Country_Code_Value': self.Country_Code_Value.selected_value,
      }

      # 3. Send to your server module function
      result = anvil.server.call('save_map_item', form_data)
    
      if result.get('status') == 'error':
        alert(result.get('message'))
      else:
        # Handle successful save or duplicate notification here
        print("Saved successfully!")    