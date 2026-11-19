import csv
import io
import json
import re
import time
import requests
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

STATE_NAME_MAP = {
    "US": {
        "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS",
        "CA": "CALIFORNIA", "CO": "COLORADO", "CT": "CONNECTICUT", "DE": "DELAWARE",
        "DC": "DISTRICT OF COLUMBIA", "FL": "FLORIDA", "GA": "GEORGIA", "HI": "HAWAII",
        "ID": "IDAHO", "IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA",
        "KS": "KANSAS", "KY": "KENTUCKY", "LA": "LOUISIANA", "ME": "MAINE",
        "MD": "MARYLAND", "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA",
        "MS": "MISSISSIPPI", "MO": "MISSOURI", "MT": "MONTANA", "NE": "NEBRASKA",
        "NV": "NEVADA", "NH": "NEW HAMPSHIRE", "NJ": "NEW JERSEY", "NM": "NEW MEXICO",
        "NY": "NEW YORK", "NC": "NORTH CAROLINA", "ND": "NORTH DAKOTA", "OH": "OHIO",
        "OK": "OKLAHOMA", "OR": "OREGON", "PA": "PENNSYLVANIA", "RI": "RHODE ISLAND",
        "SC": "SOUTH CAROLINA", "SD": "SOUTH DAKOTA", "TN": "TENNESSEE", "TX": "TEXAS",
        "UT": "UTAH", "VT": "VERMONT", "VA": "VIRGINIA", "WA": "WASHINGTON",
        "WV": "WEST VIRGINIA", "WI": "WISCONSIN", "WY": "WYOMING",
    },
    "CA": {
        "AB": "ALBERTA", "BC": "BRITISH COLUMBIA", "MB": "MANITOBA",
        "NB": "NEW BRUNSWICK", "NL": "NEWFOUNDLAND AND LABRADOR", "NS": "NOVA SCOTIA",
        "ON": "ONTARIO", "PE": "PRINCE EDWARD ISLAND", "QC": "QUEBEC",
        "SK": "SASKATCHEWAN", "NT": "NORTHWEST TERRITORIES", "NU": "NUNAVUT", "YT": "YUKON",
    },
    "MX": {
        "AGU": "AGUASCALIENTES", "BCN": "BAJA CALIFORNIA", "BCS": "BAJA CALIFORNIA SUR",
        "CAM": "CAMPECHE", "CHP": "CHIAPAS", "CHH": "CHIHUAHUA", "COA": "COAHUILA",
        "COL": "COLIMA", "DUR": "DURANGO", "GUA": "GUANAJUATO", "GRO": "GUERRERO",
        "HID": "HIDALGO", "JAL": "JALISCO", "MEX": "MEXICO", "MIC": "MICHOACAN",
        "MOR": "MORELOS", "NAY": "NAYARIT", "NLE": "NUEVO LEON", "OAX": "OAXACA",
        "PUE": "PUEBLA", "QUE": "QUERETARO", "ROO": "QUINTANA ROO", "SLP": "SAN LUIS POTOSI",
        "SIN": "SINALOA", "SON": "SONORA", "TAB": "TABASCO", "TAM": "TAMAULIPAS",
        "TLA": "TLAXCALA", "VER": "VERACRUZ", "YUC": "YUCATAN", "ZAK": "ZACATECAS",
    },
}

NOMINATIM_HEADERS = {
    "User-Agent": "AnvilPostalCodeReferenceVerifier/1.0 (contact: admin@app.com)"
}


def _request_with_retry(url, params=None, headers=None, max_attempts=3, base_delay=1.5):
  """Polite HTTP GET helper with retry/backoff for transient rate limits or 502/503/504 errors."""
  req_headers = headers or NOMINATIM_HEADERS
  for attempt in range(1, max_attempts + 1):
    try:
      resp = requests.get(url, params=params, headers=req_headers, timeout=15)
      if resp.status_code in (429, 502, 503, 504):
        sleep_for = base_delay * attempt
        print(f"HTTP {resp.status_code} (attempt {attempt}/{max_attempts}); sleeping {sleep_for:.1f}s...")
        time.sleep(sleep_for)
        continue
      resp.raise_for_status()
      return resp
    except Exception as e:
      sleep_for = base_delay * attempt
      print(f"Request error on attempt {attempt}/{max_attempts}: {e}; sleeping {sleep_for:.1f}s...")
      time.sleep(sleep_for)
  return None


def _request_json(url, params=None):
  resp = _request_with_retry(url, params=params, headers=NOMINATIM_HEADERS)
  if not resp:
    return None
  try:
    return resp.json()
  except Exception as e:
    print(f"JSON decode error from {url}: {e}")
    return None


def _extract_csv_urls_from_datapackage(text, slug):
  """Extract .csv resource URLs from datapackage.json or datapackage.yaml text."""
  urls = []
  base_url = f"https://datahub.io/logistics/{slug}"

  try:
    pkg = json.loads(text)
    for res in pkg.get("resources") or []:
      path = (res.get("path") or "").strip()
      if path.lower().endswith(".csv"):
        urls.append(path if path.startswith("http") else f"{base_url}/{path.lstrip('/')}")
    if urls:
      return urls
  except Exception:
    pass

  for match in re.findall(r"(?:path|url)\s*:\s*['\"]?([^\s'\"]+\.csv)['\"]?", text, flags=re.IGNORECASE):
    p = match.strip()
    urls.append(p if p.startswith("http") else f"{base_url}/{p.lstrip('/')}")

  return list(dict.fromkeys(urls))


def parse_csv_line_candidate(csv_line, default_country="US", default_state="AL"):
  """
  Parse a single CSV line into a candidate dict.
  Supports:
    - 4-column DataHub style: country_code,postal_code,place_name,admin_code1
    - 2-column simple style: postal_code,place_name
    - 1-column postal code only: postal_code
  """
  line = (csv_line or "").strip()
  if not line:
    return None

  cols = next(csv.reader(io.StringIO(line)))
  cols = [c.strip() for c in cols]

  c_code = default_country.strip().upper()
  s_code = default_state.strip().upper()
  pcode = ""
  city = ""

  if len(cols) >= 4:
    c_code = (cols[0] or c_code).upper()
    pcode = cols[1].upper()
    city = cols[2]
    s_code = (cols[3] or s_code).upper()
  elif len(cols) == 2:
    pcode = cols[0].upper()
    city = cols[1]
  elif len(cols) == 1:
    pcode = cols[0].upper()

  if not pcode:
    return None

  return {
      "country_code": c_code,
      "state_code": s_code,
      "postal_code": pcode,
      "city": city,
  }


def fetch_staged_csv_candidates(country_code, state_code):
  """Read raw single-line CSV records from app_tables.Postal_code_stage for country & state."""
  c_code = country_code.strip().upper()
  s_code = state_code.strip().upper()
  candidates = []
  seen_codes = set()

  if not hasattr(app_tables, "Postal_code_stage"):
    return candidates

  for row in app_tables.Postal_code_stage.search():
    raw_line = row["csv"]
    item = parse_csv_line_candidate(raw_line, default_country=c_code, default_state=s_code)
    if not item:
      continue
    if item["country_code"] == c_code and item["state_code"] == s_code:
      pcode = item["postal_code"]
      if pcode not in seen_codes:
        seen_codes.add(pcode)
        candidates.append({"postal_code": pcode, "city": item["city"]})

  return candidates


def fetch_raw_datahub_candidates(country_code, state_code):
  """
  Step 1: Retrieve candidate postal codes (+ cities) for country & state.
  Uses Postal_code_stage first; falls back to DataHub datapackage.yaml if stage has no rows for the state.
  """
  c_code = country_code.strip().upper()
  s_code = state_code.strip().upper()

  staged = fetch_staged_csv_candidates(c_code, s_code)
  if staged:
    print(f"[Step 1] Loaded {len(staged)} staged CSV lines from Postal_code_stage for {c_code}-{s_code}.")
    return staged

  slug = f"postal-codes-{c_code.lower()}"
  base_url = f"https://datahub.io/logistics/{slug}"
  dp_url = f"{base_url}/_r/-/datapackage.yaml"

  dp_resp = _request_with_retry(dp_url, headers={"User-Agent": "AnvilPostalCodeFetcher/1.0"})
  if not dp_resp or not dp_resp.text.strip():
    print(f"[Step 1] Could not fetch {dp_url}")
    return []

  csv_urls = _extract_csv_urls_from_datapackage(dp_resp.text, slug)
  if not csv_urls:
    print(f"[Step 1] No CSV resource URLs found in {dp_url}.")
    return []

  candidates = []
  seen_codes = set()

  for csv_url in csv_urls:
    csv_resp = _request_with_retry(csv_url, headers={"User-Agent": "AnvilPostalCodeFetcher/1.0"})
    if not csv_resp:
      continue

    text = csv_resp.text
    first_line = text.lstrip().splitlines()[0] if text.strip() else ""
    if first_line.lower().startswith("<!doctype html") or first_line.lower().startswith("<html"):
      print(f"[Step 1] Skipping non-CSV HTML response from {csv_url}")
      continue

    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
      row_country = (row.get("country_code") or c_code).strip().upper()
      row_state = (row.get("admin_code1") or "").strip().upper()
      pcode = (row.get("postal_code") or "").strip().upper()
      city = (row.get("place_name") or "").strip()

      if row_country == c_code and row_state == s_code and pcode and pcode not in seen_codes:
        seen_codes.add(pcode)
        candidates.append({"postal_code": pcode, "city": city})

  return candidates


def get_state_bbox(country_code, state_code):
  """Step 3 helper: fetch bounding box (min_lat, max_lat, min_lon, max_lon) for target state."""
  full_name = STATE_NAME_MAP.get(country_code, {}).get(state_code, state_code)
  results = _request_json(
      "https://nominatim.openstreetmap.org/search",
      params={"q": f"{full_name}, {country_code}", "format": "json", "limit": 1},
  )
  if not results:
    return None

  bb = results[0].get("boundingbox")
  if not bb or len(bb) < 4:
    return None

  return float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])


def resolve_postal_code_location(postal_code, country_code):
  """Step 2: resolve centerpoint, bounding box, state/province, and city for a postal code."""
  results = _request_json(
      "https://nominatim.openstreetmap.org/search",
      params={
          "postalcode": postal_code,
          "country": country_code,
          "format": "json",
          "limit": 1,
          "addressdetails": 1,
      },
  )
  if not results:
    return None

  top = results[0]
  addr = top.get("address", {})
  bb = top.get("boundingbox")

  resolved_state = (
      addr.get("state")
      or addr.get("province")
      or addr.get("region")
      or ""
  ).strip().upper()

  resolved_city = (
      addr.get("city")
      or addr.get("town")
      or addr.get("village")
      or addr.get("municipality")
      or addr.get("county")
      or ""
  ).strip()

  min_lat = float(bb[0]) if bb and len(bb) >= 4 else None
  max_lat = float(bb[1]) if bb and len(bb) >= 4 else None
  min_lon = float(bb[2]) if bb and len(bb) >= 4 else None
  max_lon = float(bb[3]) if bb and len(bb) >= 4 else None

  return {
      "center_lat": float(top["lat"]),
      "center_lon": float(top["lon"]),
      "min_lat": min_lat,
      "max_lat": max_lat,
      "min_lon": min_lon,
      "max_lon": max_lon,
      "state": resolved_state,
      "city": resolved_city,
  }


def location_matches_state(loc, country_code, state_code, bbox=None):
  """Step 3: compare resolved postal code location against target state/province & bounds."""
  if not loc:
    return False

  expected_code = state_code.strip().upper()
  expected_full = STATE_NAME_MAP.get(country_code, {}).get(expected_code, "").upper()
  found_state = loc.get("state", "").upper()

  name_match = bool(found_state) and (
      found_state == expected_code
      or found_state == expected_full
      or (expected_full and (expected_full in found_state or found_state in expected_full))
  )

  bbox_match = True
  if bbox is not None:
    s_min_lat, s_max_lat, s_min_lon, s_max_lon = bbox
    c_lat = loc["center_lat"]
    c_lon = loc["center_lon"]
    bbox_match = (s_min_lat <= c_lat <= s_max_lat) and (s_min_lon <= c_lon <= s_max_lon)

  return name_match and bbox_match


def _process_candidate_item(item, default_country, default_state, state_bbox=None, save_to_table=True):
  """Validate one candidate dict and print 'True: ...' or 'False: ...'."""
  c_code = (item.get("country_code") or default_country).strip().upper()
  s_code = (item.get("state_code") or default_state).strip().upper()
  pcode = (item.get("postal_code") or "").strip().upper()
  fallback_city = (item.get("city") or "").strip()

  if not pcode:
    return "invalid"

  if save_to_table and app_tables.datahub_postal_codes.get(Country_Code=c_code, Postal_Code=pcode):
    return "skipped"

  loc = resolve_postal_code_location(pcode, c_code)
  time.sleep(1.2)

  if not location_matches_state(loc, c_code, s_code, bbox=state_bbox):
    rejected_record = {
        "Country_Code": c_code,
        "State_Code": s_code,
        "Postal_Code": pcode,
        "City_code": (loc.get("city") if loc else None) or fallback_city or None,
        "resolved": loc,
    }
    print(f"False: {rejected_record}")
    return "rejected"

  resolved_city = loc.get("city") or fallback_city or None
  saved_record = {
      "Country_Code": c_code,
      "State_Code": s_code,
      "Postal_Code": pcode,
      "City_code": resolved_city,
      "center_lat": loc["center_lat"],
      "center_lon": loc["center_lon"],
      "min_lat": loc["min_lat"],
      "max_lat": loc["max_lat"],
      "min_lon": loc["min_lon"],
      "max_lon": loc["max_lon"],
  }
  if save_to_table:
    app_tables.datahub_postal_codes.add_row(**saved_record)
  print(f"True: {saved_record}")
  return "added"


@anvil.server.callable
def stage_single_csv_line(csv_line):
  """Append a single raw CSV line into Postal_code_stage.csv."""
  line = (csv_line or "").strip()
  if not line:
    return {"success": False, "error": "Empty CSV line"}
  app_tables.Postal_code_stage.add_row(csv=line)
  return {"success": True, "csv": line}


@anvil.server.callable
def test_single_csv_line(csv_line, country_code="US", state_code="AL", save_to_table=True):
  """Test one CSV line immediately (e.g., 'US,35203,Birmingham,AL' or '35203,Birmingham')."""
  item = parse_csv_line_candidate(csv_line, default_country=country_code, default_state=state_code)
  if not item:
    print(f"False: {{'raw_line': {csv_line!r}, 'error': 'Could not parse postal_code'}}")
    return False

  bbox = get_state_bbox(item["country_code"], item["state_code"])
  time.sleep(1.2)
  status = _process_candidate_item(
      item,
      default_country=item["country_code"],
      default_state=item["state_code"],
      state_bbox=bbox,
      save_to_table=save_to_table,
  )
  return status == "added"


@anvil.server.background_task
def harvest_first_state_test_task(country_code="US", state_code="AL"):
  """Test run: processes ONLY one state/province (default: US - AL) with True:/False: logging."""
  c_code = country_code.strip().upper()
  s_code = state_code.strip().upper()

  print("========================================")
  print(f"Starting Single-State Test Harvest: {c_code} - {s_code}")
  print("========================================")

  candidates = fetch_raw_datahub_candidates(c_code, s_code)
  print(f"[Step 1] Retrieved {len(candidates)} candidate postal codes for {c_code}-{s_code}.")
  if not candidates:
    print("No candidate postal codes found in Postal_code_stage or DataHub for this region.")
    return

  state_bbox = get_state_bbox(c_code, s_code)
  print(f"[Step 3] Target state bounding box for {c_code}-{s_code}: {state_bbox}")
  time.sleep(1.2)

  added = 0
  skipped_existing = 0
  rejected = 0

  for item in candidates:
    status = _process_candidate_item(item, c_code, s_code, state_bbox=state_bbox, save_to_table=True)
    if status == "added":
      added += 1
    elif status == "skipped":
      skipped_existing += 1
    elif status == "rejected":
      rejected += 1

  print("========================================")
  print(
      f"Test complete for {c_code}-{s_code}: "
      f"added={added}, skipped_existing={skipped_existing}, rejected={rejected}"
  )
  print("========================================")


@anvil.server.callable
def start_first_state_test(country_code="US", state_code="AL"):
  """Client callable to launch the single-state test background task (defaults to US - AL)."""
  return anvil.server.launch_background_task(
      "harvest_first_state_test_task",
      country_code=country_code,
      state_code=state_code,
  )


@anvil.server.callable
def start_north_america_datahub_audit():
  return start_first_state_test("US", "AL")


@anvil.server.callable
def start_full_north_america_harvest():
  return start_first_state_test("US", "AL")