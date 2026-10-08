from ._anvil_designer import Form1Template
import anvil.server

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
    
