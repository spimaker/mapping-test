import csv
import io
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables


def _clean_str(val):
  if val is None:
    return None
  s = str(val).strip()
  return s if s != "" else None


def _to_float(val):
  s = _clean_str(val)
  if s is None:
    return None
  try:
    return float(s)
  except ValueError:
    return None


def _parse_geonames_tsv_row(cols):
  """
  Map 12-column GeoNames postal TSV row to Data_GeoNames_Postal schema:
    0: country code       -> Country_code
    1: postal code        -> Postal_code
    2: place name         -> Place
    3: admin name1        -> State_name
    4: admin code1        -> State_code
    5: admin name2        -> CountyProvince_name
    6: admin code2        -> CountyProvince_code
    7: admin name3        -> Community_name
    8: admin code3        -> Community_code
    9: latitude           -> Latitude
   10: longitude          -> Longitude
   11: accuracy           -> GeoAccuracy
  """
  if not cols or len(cols) < 11:
    return None

  country_code = _clean_str(cols[0])
  postal_code = _clean_str(cols[1])
  if not country_code or not postal_code:
    return None

  state_code = _clean_str(cols[4])
  accuracy = _to_float(cols[11]) if len(cols) >= 12 else None

  return {
      "Country_code": country_code.upper(),
      "Postal_code": postal_code.upper(),
      "Place": _clean_str(cols[2]),
      "State_name": _clean_str(cols[3]),
      "State_code": state_code.upper() if state_code else None,
      "CountyProvince_name": _clean_str(cols[5]),
      "CountyProvince_code": _clean_str(cols[6]),
      "Community_name": _clean_str(cols[7]),
      "Community_code": _clean_str(cols[8]),
      "Latitude": _to_float(cols[9]),
      "Longitude": _to_float(cols[10]),
      "GeoAccuracy": accuracy,
  }


@anvil.server.callable
def import_geonames_file(file, start_row=0, max_rows=None, log_every=2500):
  """
  Import rows from an uploaded GeoNames TSV Media object into app_tables.data_geonames_postal.
  Uses 0-based non-empty data row indexing via start_row and max_rows for safe batching.
  """
  if file is None:
    return {
        "inserted": 0,
        "malformed": 0,
        "processed_in_batch": 0,
        "next_start_row": start_row,
        "reached_eof": True,
        "error": "No file selected in FileLoader",
    }

  raw_text = file.get_bytes().decode("utf-8", errors="replace")
  reader = csv.reader(io.StringIO(raw_text), delimiter="\t", quoting=csv.QUOTE_NONE)

  table = app_tables.data_geonames_postal
  data_row_idx = 0
  processed_in_batch = 0
  inserted = 0
  malformed = 0
  reached_eof = True

  for line_num, cols in enumerate(reader, start=1):
    if not cols or all(not c.strip() for c in cols):
      continue

    if data_row_idx < start_row:
      data_row_idx += 1
      continue

    if max_rows is not None and processed_in_batch >= max_rows:
      reached_eof = False
      break

    data_row_idx += 1
    processed_in_batch += 1

    record = _parse_geonames_tsv_row(cols)
    if record is None:
      malformed += 1
      print(f"False: {{'line': {line_num}, 'row': {data_row_idx}, 'reason': 'Malformed/short row', 'raw': {cols}}}")
      continue

    try:
      table.add_row(**record)
      inserted += 1
      if inserted <= 5 or inserted % log_every == 0:
        print(f"True: inserted={inserted} (line={line_num}, row={data_row_idx}) -> {record}")
    except Exception as e:
      malformed += 1
      print(f"False: {{'line': {line_num}, 'row': {data_row_idx}, 'error': {str(e)!r}, 'record': {record}}}")

  next_start_row = start_row + processed_in_batch
  summary = {
      "inserted": inserted,
      "malformed": malformed,
      "processed_in_batch": processed_in_batch,
      "next_start_row": next_start_row,
      "reached_eof": reached_eof,
  }
  print(f"Batch complete: {summary}")
  return summary