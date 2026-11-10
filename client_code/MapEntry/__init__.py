from anvil import alert
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ._anvil_designer import MapEntryTemplate


class MapEntry(MapEntryTemplate):

  def __init__(self, **properties):
    self.init_components(**properties)

    # Event guard flags to prevent loop/double-triggers during programmatic updates
    self._loading_subdivisions = False
    self._loading_cities = False

    self._setup_dropdowns()

    # Wire up change events explicitly if not bound in the Anvil visual designer
    if hasattr(self, 'Country_Code_Value'):
      self.Country_Code_Value.set_event_handler(
          'change', self.country_dropdown_change
      )
    if hasattr(self, 'State_Province_Region_Value'):
      self.State_Province_Region_Value.set_event_handler(
          'change', self.state_dropdown_change
      )
    if hasattr(self, 'City_Value'):
      self.City_Value.set_event_handler('change', self.city_dropdown_change)

    # Ensure custom city input and label are hidden on initial load
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False
    if hasattr(self, 'Custom_City_Label'):
      self.Custom_City_Label.visible = False

  def _setup_dropdowns(self):
    """Populates initial country options and resets state/city dropdowns."""
    try:
      country_items = anvil.server.call('get_country_list')
      if hasattr(self, 'Country_Code_Value'):
        self.Country_Code_Value.items = [
            ('-- Select Country --', None)
        ] + country_items
        self.Country_Code_Value.selected_value = None
    except Exception as e:
      print(f'Error loading country list: {e}')

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
      self.State_Province_Region_Value.items = [
          ('-- Select State / Province --', None)
      ]
      self.State_Province_Region_Value.selected_value = None

    if hasattr(self, 'City_Value'):
      self.City_Value.items = [('-- Select City --', None)]
      self.City_Value.selected_value = None

  def country_dropdown_change(self, **event_args):
    """Triggered when user selects a country; populates state/province subdivisions."""
    if not hasattr(self, 'Country_Code_Value'):
      return

    selected_country = self.Country_Code_Value.selected_value

    # Reset downstream custom city fields
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False
      self.Custom_City_TextBox.text = ''
    if hasattr(self, 'Custom_City_Label'):
      self.Custom_City_Label.visible = False

    # Reset city dropdown safely
    if hasattr(self, 'City_Value'):
      self._loading_cities = True
      self.City_Value.items = [('-- Select City --', None)]
      self.City_Value.selected_value = None
      self._loading_cities = False

    if not selected_country:
      if hasattr(self, 'State_Province_Region_Value'):
        self._loading_subdivisions = True
        self.State_Province_Region_Value.items = [
            ('-- Select State / Province --', None)
        ]
        self.State_Province_Region_Value.selected_value = None
        self._loading_subdivisions = False
      return

    try:
      subdivisions = anvil.server.call(
          'get_subdivisions_for_country', selected_country
      )
      if hasattr(self, 'State_Province_Region_Value'):
        self._loading_subdivisions = True
        self.State_Province_Region_Value.items = [
            ('-- Select State / Province --', None)
        ] + subdivisions
        self.State_Province_Region_Value.selected_value = None
        self._loading_subdivisions = False
    except Exception as e:
      print(f'Error fetching subdivisions: {e}')
      if hasattr(self, 'State_Province_Region_Value'):
        self._loading_subdivisions = True
        self.State_Province_Region_Value.items = [
            ('-- Select State / Province --', None)
        ]
        self.State_Province_Region_Value.selected_value = None
        self._loading_subdivisions = False

  def state_dropdown_change(self, **event_args):
    """Triggered when user selects a state; populates cities without UI state focus loss."""
    if getattr(self, '_loading_subdivisions', False):
      return

    if not hasattr(self, 'Country_Code_Value') or not hasattr(
        self, 'State_Province_Region_Value'
    ):
      return

    selected_country = self.Country_Code_Value.selected_value
    selected_state = self.State_Province_Region_Value.selected_value

    # Hide custom city fields when state changes
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False
      self.Custom_City_TextBox.text = ''
    if hasattr(self, 'Custom_City_Label'):
      self.Custom_City_Label.visible = False

    if not selected_state or not selected_country:
      if hasattr(self, 'City_Value'):
        self._loading_cities = True
        self.City_Value.items = [('-- Select City --', None)]
        self.City_Value.selected_value = None
        self._loading_cities = False
      return

    try:
      cities = anvil.server.call(
          'get_cities_for_state', selected_country, selected_state
      )
      if hasattr(self, 'City_Value'):
        self._loading_cities = True
        self.City_Value.items = (
            [('-- Select City --', None)]
            + cities
            + [('Other (Enter manually)...', 'OTHER_CUSTOM_CITY')]
        )
        self.City_Value.selected_value = None
        self._loading_cities = False
    except Exception as e:
      print(f'Error fetching cities: {e}')
      if hasattr(self, 'City_Value'):
        self._loading_cities = True
        self.City_Value.items = [
            ('-- Select City --', None),
            ('Other (Enter manually)...', 'OTHER_CUSTOM_CITY'),
        ]
        self.City_Value.selected_value = None
        self._loading_cities = False

  def city_dropdown_change(self, **event_args):
    """Triggered when user selects a city; toggles manual entry components for 'Other'."""
    if getattr(self, '_loading_cities', False):
      return

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
      """Gathers form inputs, validates presence of required fields, and invokes server save."""
    
      fields_to_check = {
          'User_Name_Value': getattr(self, 'User_Name_Value', None),
          'Country_CodeB_Value': getattr(self, 'Country_CodeB_Value', None),
          'State_Province_Region_Value': getattr(self, 'State_Province_Region_Value', None),
          'City_Value': getattr(self, 'City_Value', None),
          'Postal_Code_Value': getattr(self, 'Postal_Code_Value', None),
          'Address1_Value': getattr(self, 'Address1_Value', None),
      }

      is_custom = (
          hasattr(self, 'City_Value')
          and self.City_Value.selected_value == 'OTHER_CUSTOM_CITY'
      )
    
      if is_custom:
        city_value = (
            self.Custom_City_TextBox.text.strip()
            if hasattr(self, 'Custom_City_TextBox')
            else ''
        )
      else:
        city_value = (
            self.City_Value.selected_value if hasattr(self, 'City_Value') else ''
        )

      missing_fields = []
    
      for name, comp in fields_to_check.items():
        if comp is None:
          continue
        
        val = None
        if hasattr(comp, 'text'):
          val = comp.text
        elif hasattr(comp, 'selected_value'):
          val = comp.selected_value

        is_empty = False
        if val is None:
          is_empty = True
        elif isinstance(val, str) and not val.strip():
          is_empty = True
        elif name == 'City_Value' and is_custom and not city_value:
          is_empty = True

        # Native Anvil background property highlighting
        if is_empty:
          missing_fields.append(name)
          comp.background = '#fce8e6'  # Soft error red background
        else:
          comp.background = ''        # Clears highlight when filled

      if missing_fields:
        alert('Some required fields are missing data', title='Missing Information')
        return

      form_data = {
          'User_Name_Value': self.User_Name_Value.text.strip(),
          'Country_CodeB_Value': self.Country_CodeB_Value.selected_value,
          'State_Province_Region_Value': self.State_Province_Region_Value.selected_value,
          'City_Value': city_value,
          'Postal_Code_Value': self.Postal_Code_Value.text.strip(),
          'Address1_Value': self.Address1_Value.text.strip(),
          'Address2_Value': self.Address2_Value.text.strip() if hasattr(self, 'Address2_Value') else '',
          'Country_Code_Value': self.Country_CodeB_Value.selected_value,
          'Is_Custom_City': is_custom,
      }

      try:
        result = anvil.server.call('save_map_item', form_data)

        if result.get('status') == 'error':
          alert(result.get('message', 'An error occurred while saving.'))
        elif result.get('status') == 'duplicate':
          alert(
              'This record already exists in the database.', title='Duplicate Record'
          )
        elif result.get('status') == 'saved':
          alert('Map item saved successfully!', title='Success')
      except Exception as e:
        alert(f'Save failed: {e}', title='System Error')