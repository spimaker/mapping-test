import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ._anvil_designer import MapEntryTemplate


class MapEntry(MapEntryTemplate):

  def __init__(self, **properties):
    self.init_components(**properties)
    self._setup_dropdowns()

    # Wire up cascading change events
    self.Country_Code_Value.set_event_handler('change', self.country_dropdown_change)
    self.State_Province_Region_Value.set_event_handler('change', self.state_dropdown_change)
    self.City_Value.set_event_handler('change', self.city_dropdown_change)

    # Ensure custom city entry box starts hidden
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False

  def _setup_dropdowns(self):
    """Populates initial options and default selections."""
    try:
      country_items = anvil.server.call('get_country_list')
      self.Country_Code_Value.items = [('-- Select Country --', None)] + country_items
      self.Country_Code_Value.selected_value = None
    except Exception as e:
      print(f'Error loading countries: {e}')

    self.Cluster_Type_Dropdown.items = [
        ('Global Region', 'global_region'),
        ('Country', 'country'),
        ('State / Province', 'state'),
        ('City', 'city'),
        ('Postal Code', 'postal'),
        ('Miles Radius', 'miles'),
        ('Kilometers Radius', 'kilometers'),
    ]

    # Reset downstream dropdowns on init
    self.State_Province_Region_Value.items = [('-- Select State / Province --', None)]
    self.State_Province_Region_Value.selected_value = None
    self.City_Value.items = [('-- Select City --', None)]
    self.City_Value.selected_value = None

  def country_dropdown_change(self, **event_args):
    """Triggered when user selects a country; populates state subdivisions."""
    selected_country = self.Country_Code_Value.selected_value

    # Reset downstream selections
    self.State_Province_Region_Value.selected_value = None
    self.City_Value.selected_value = None
    self.State_Province_Region_Value.items = [('-- Select State / Province --', None)]
    self.City_Value.items = [('-- Select City --', None)]
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False

    if not selected_country:
      return

    try:
      subdivisions = anvil.server.call('get_subdivisions_for_country', selected_country)
      self.State_Province_Region_Value.items = [('-- Select State / Province --', None)] + subdivisions
    except Exception as e:
      print(f'Error fetching subdivisions: {e}')
      self.State_Province_Region_Value.items = [('-- Select State / Province --', None)]

  def state_dropdown_change(self, **event_args):
    """Triggered when user selects a state; populates cities with 'Other' option."""
    selected_country = self.Country_Code_Value.selected_value
    selected_state = self.State_Province_Region_Value.selected_value

    self.City_Value.selected_value = None
    if hasattr(self, 'Custom_City_TextBox'):
      self.Custom_City_TextBox.visible = False

    if not selected_state or not selected_country:
      self.City_Value.items = [('-- Select City --', None)]
      return

    try:
      cities = anvil.server.call('get_cities_for_state', selected_country, selected_state)
      self.City_Value.items = [('-- Select City --', None)] + cities + [('Other (Enter manually)...', 'OTHER_CUSTOM_CITY')]
    except Exception as e:
      print(f'Error fetching cities: {e}')
      self.City_Value.items = [
          ('-- Select City --', None),
          ('Other (Enter manually)...', 'OTHER_CUSTOM_CITY'),
      ]

  def city_dropdown_change(self, **event_args):
    """Triggered when user selects a city; handles manual entry for 'Other'."""
    if self.City_Value.selected_value == 'OTHER_CUSTOM_CITY':
      if hasattr(self, 'Custom_City_TextBox'):
        self.Custom_City_TextBox.visible = True
        self.Custom_City_TextBox.text = ''
        self.Custom_City_TextBox.focus()
    else:
      if hasattr(self, 'Custom_City_TextBox'):
        self.Custom_City_TextBox.visible = False