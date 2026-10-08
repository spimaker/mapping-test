#import anvil.tables as tables
#import anvil.tables.query as q
#from anvil.tables import app_tables
#import anvil.server

# This is a server module. It runs on the Anvil server,
# rather than in the user's browser.
#
# To allow anvil.server.call() to call functions here, we mark
# them with @anvil.server.callable.
# Here is an example - you can replace it with your own:
#
# @anvil.server.callable
# def say_hello(name):
#   print("Hello, " + name + "!")
#   return 42
#
import anvil.server
import pycountry

@anvil.server.callable
def get_country_list():
  # Create a list of tuples: (Display Name, Country Code)
  countries = [(country.name, country.alpha_2) for country in pycountry.countries]

  # Sort alphabetically by the country name
  countries = sorted(countries, key=lambda x: x[0])

  return countries
