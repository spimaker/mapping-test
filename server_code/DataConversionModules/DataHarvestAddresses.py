from datetime import datetime, timedelta
import random
import re
import time
import requests
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

try:
  import pycountry
except ImportError:
  pycountry = None

try:
  from pycountry_convert import country_alpha2_to_continent_code
except ImportError:
  country_alpha2_to_continent_code = None


_COUNTRY_FALLBACKS = {
    "US": "United States",
    "CA": "Canada",
    "MX": "Mexico",
}


def _get_region(country_code):
  cc = (country_code or "").strip().upper()
  if not cc:
    return "Other"
  if country_alpha2_to_continent_code:
    try:
      cont = country_alpha2_to_continent_code(cc)
      return {
          "NA": "North America",
          "SA": "South America",
          "EU": "Europe",
          "AS": "Asia",
          "AF": "Africa",
          "OC": "Oceania",
      }.get(cont, "Other")
    except Exception:
      pass
  return "North America" if cc in {"US", "CA", "MX"} else "Other"


def _get_country_name(country_code):
  cc = (country_code or "").strip().upper()
  if not cc:
    return ""
  if pycountry:
    try:
      obj = pycountry.countries.get(alpha_2=cc) or pycountry.countries.get(alpha_3=cc)
      if obj and getattr(obj, "name", None):
        return obj.name
    except Exception:
      pass
  return _COUNTRY_FALLBACKS.get(cc, cc)


def _random_datetime_last_120_days(anchor_dt):
  max_seconds = 120 * 24 * 3600
  offset_seconds = random.randint(0, max_seconds)
  return anchor_dt - timedelta(seconds=offset_seconds)


def _build_formatted_address(user_val, address_1, city, state, pcode, country_name):
  city_state_zip = " ".join(part for part in [state, pcode] if part).strip()
  if city and city_state_zip:
    loc_block = f"{city}, {city_state_zip}"
  else:
    loc_block = city or city_state_zip

  segments = [seg for seg in [user_val, address_1, loc_block, country_name] if seg]
  return "/".join(segments)


def _escape_overpass_regex(val):
  return re.escape(val.strip())


def _parse_overpass_elements(data, pcode, max_addresses=5):
  valid_elements = []
  for element in data.get("elements", []):
    tags = element.get("tags", {})
    house_no = tags.get("addr:housenumber")
    street = tags.get("addr:street")
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lon = element.get("lon") or element.get("center", {}).get("lon")

    if house_no and street and lat is not None and lon is not None:
      valid_elements.append({
          "house_no": str(house_no).strip(),
          "street": str(street).strip(),
          "city": str(tags.get("addr:city") or tags.get("addr:suburb") or "").strip(),
          "postcode": str(tags.get("addr:postcode") or pcode).strip(),
          "lat": float(lat),
          "lon": float(lon),
      })

  if len(valid_elements) <= max_addresses:
    return valid_elements
  return random.sample(valid_elements, max_addresses)


def _post_overpass(overpass_url, headers, query):
  resp = requests.post(
      overpass_url,
      data={"data": query},
      headers=headers,
      timeout=40,
  )
  resp.raise_for_status()
  return resp.json()


def _query_overpass_addresses(
    overpass_url,
    headers,
    pcode,
    country_code="",
    geo_lat=None,
    geo_lon=None,
    max_addresses=5,
):
  clean_pcode = pcode.strip()
  escaped_pcode = _escape_overpass_regex(clean_pcode)

  # Match exact postcode or prefix (e.g., Canadian 3-char FSA like "T2B" matching "T2B 1A1")
  if country_code == "CA" and len(clean_pcode) <= 3:
    postcode_filter = f'["addr:postcode"~"^{escaped_pcode}(\\s|$)",i]'
  else:
    postcode_filter = f'["addr:postcode"="{clean_pcode}"]'

  # 1. Direct query by postal code without requiring a bounding box
  direct_query = f"""
  [out:json][timeout:35];
  (
    node{postcode_filter}["addr:street"]["addr:housenumber"];
    way{postcode_filter}["addr:street"]["addr:housenumber"];
  );
  out center tags;
  """
  data = _post_overpass(overpass_url, headers, direct_query)
  results = _parse_overpass_elements(data, clean_pcode, max_addresses=max_addresses)
  if results:
    return results, "postcode"

  # 2. Optional fallback using GeoNames Latitude/Longitude if available
  if geo_lat is not None and geo_lon is not None:
    around_query = f"""
    [out:json][timeout:35];
    (
      node(around:3000,{geo_lat},{geo_lon})["addr:street"]["addr:housenumber"];
      way(around:3000,{geo_lat},{geo_lon})["addr:street"]["addr:housenumber"];
    );
    out center tags;
    """
    data_around = _post_overpass(overpass_url, headers, around_query)
    results_around = _parse_overpass_elements(data_around, clean_pcode, max_addresses=max_addresses)
    if results_around:
      return results_around, "around_3km"

  return [], "none"


def _upsert_summary_bbox(table, match_kwargs, base_kwargs, lat, lon, count_delta=1):
  row = table.get(**match_kwargs)
  if not row:
    vals = dict(base_kwargs)
    vals.update({
        "min_lat": lat,
        "max_lat": lat,
        "min_lon": lon,
        "max_lon": lon,
        "center_lat": lat,
        "center_lon": lon,
        "user_count": count_delta,
    })
    table.add_row(**vals)
    return

  min_lat = lat if row["min_lat"] is None else min(row["min_lat"], lat)
  max_lat = lat if row["max_lat"] is None else max(row["max_lat"], lat)
  min_lon = lon if row["min_lon"] is None else min(row["min_lon"], lon)
  max_lon = lon if row["max_lon"] is None else max(row["max_lon"], lon)
  new_count = (row["user_count"] or 0) + count_delta

  row.update(
      min_lat=min_lat,
      max_lat=max_lat,
      min_lon=min_lon,
      max_lon=max_lon,
      center_lat=(min_lat + max_lat) / 2.0,
      center_lon=(min_lon + max_lon) / 2.0,
      user_count=new_count,
  )


def _insert_map_item_and_sync(
    addr,
    country_code,
    state_code,
    state_name,
    pcode,
    fallback_city,
    seq_id,
    batch_anchor_dt,
):
  city = (addr["city"] or fallback_city or state_name or state_code).strip()
  state = (state_code or "").strip().upper()
  region = _get_region(country_code)
  country_name = _get_country_name(country_code)
  lat = addr["lat"]
  lon = addr["lon"]

  address_1 = f'{addr["house_no"]} {addr["street"]}'.strip()
  user_val = f"{country_code}/{state}/{city}/{pcode}/{address_1}"
  formatted_address = _build_formatted_address(
      user_val=user_val,
      address_1=address_1,
      city=city,
      state=state,
      pcode=pcode,
      country_name=country_name,
  )

  rand_dt = _random_datetime_last_120_days(batch_anchor_dt)
  created_dt = datetime.now()

  app_tables.mapitems_test.add_row(
      id=seq_id,
      user=user_val,
      date_time=rand_dt,
      created_time=created_dt,
      region=region,
      country_code=country_code,
      country_name=country_name,
      state=state,
      state_name=state_name,
      city=city,
      address_1=address_1,
      address_2="",
      postal_code=pcode,
      formatted_address=formatted_address,
      latitude=lat,
      longitude=lon,
  )

  app_tables.map_user_lookup.add_row(
      id=seq_id,
      user=user_val,
      region=region,
      country_code=country_code,
      state=state,
      city=city,
      postal_code=pcode,
  )

  if pcode:
    _upsert_summary_bbox(
        app_tables.map_postal_summary,
        {"country_code": country_code, "postal_code": pcode},
        {"country_code": country_code, "postal_code": pcode},
        lat,
        lon,
    )
  if city:
    _upsert_summary_bbox(
        app_tables.map_city_summary,
        {"country_code": country_code, "state": state, "city": city},
        {"country_code": country_code, "state": state, "city": city},
        lat,
        lon,
    )
  if state:
    _upsert_summary_bbox(
        app_tables.map_state_summary,
        {"country_code": country_code, "state": state},
        {"country_code": country_code, "state": state},
        lat,
        lon,
    )
  if country_code:
    _upsert_summary_bbox(
        app_tables.map_country_summary,
        {"country_code": country_code},
        {"country_code": country_code},
        lat,
        lon,
    )
  if region:
    _upsert_summary_bbox(
        app_tables.map_region_summary,
        {"region": region},
        {"region": region},
        lat,
        lon,
    )


def _print_progress(
    processed_records,
    limit_records,
    matched_codes,
    total_addresses_added,
    error_count,
    start_time,
):
  elapsed = time.time() - start_time
  rate = processed_records / elapsed if elapsed > 0 else 0.0
  limit_str = str(limit_records) if limit_records else "ALL"
  print(
      f"[Progress] Checked: {processed_records}/{limit_str} | "
      f"Codes with hits: {matched_codes} | "
      f"Addresses added: {total_addresses_added} | "
      f"Errors: {error_count} | "
      f"Elapsed: {elapsed:.1f}s ({rate:.2f} rec/s)"
  )


@anvil.server.background_task
def harvest_geonames_postal_test(
    limit_records=50,
    max_addresses_per_code=5,
    pause_seconds=4,
    report_every_n=10,
    report_interval_seconds=30,
):
  overpass_url = "https://overpass.openstreetmap.fr/api/interpreter"
  headers = {
      "User-Agent": "AnvilGeoNamesHarvester/1.7 (contact: admin@app.com)"
  }

  start_time = time.time()
  last_report_time = start_time
  print(
      f"Starting direct Overpass harvest (no bbox required; limit={limit_records}, "
      f"max_per_code={max_addresses_per_code}, pause={pause_seconds}s)..."
  )

  rows = app_tables.data_geonames_postal.search()

  processed_records = 0
  matched_codes = 0
  total_addresses_added = 0
  error_count = 0
  seq_id = 1

  for row in rows:
    if limit_records is not None and processed_records >= limit_records:
      print(f"Reached record limit ({limit_records}). Stopping harvest.")
      break

    country_code = str(row["Country_code"] or "").strip().upper()
    state_code = str(row["State_code"] or "").strip().upper()
    state_name = str(row["State_name"] or "").strip()
    pcode = str(row["Postal_code"] or "").strip()
    fallback_city = str(row["Place"] or row["Community_name"] or "").strip()

    try:
      geo_lat = float(row["Latitude"]) if row["Latitude"] is not None else None
      geo_lon = float(row["Longitude"]) if row["Longitude"] is not None else None
    except (ValueError, TypeError):
      geo_lat, geo_lon = None, None

    if not country_code or not pcode:
      continue

    processed_records += 1
    current_wait = pause_seconds

    try:
      sampled_addresses, source_mode = _query_overpass_addresses(
          overpass_url=overpass_url,
          headers=headers,
          pcode=pcode,
          country_code=country_code,
          geo_lat=geo_lat,
          geo_lon=geo_lon,
          max_addresses=max_addresses_per_code,
      )
      if sampled_addresses:
        matched_codes += 1
      batch_anchor_dt = datetime.now()
      for addr in sampled_addresses:
        _insert_map_item_and_sync(
            addr=addr,
            country_code=country_code,
            state_code=state_code,
            state_name=state_name,
            pcode=pcode,
            fallback_city=fallback_city,
            seq_id=seq_id,
            batch_anchor_dt=batch_anchor_dt,
        )
        seq_id += 1
        total_addresses_added += 1

      print(
          f"[{processed_records}] {pcode} ({state_code}, {country_code}): "
          f"+{len(sampled_addresses)} address(es) via {source_mode} (total={total_addresses_added}); "
          f"waiting {current_wait}s."
      )
    except requests.HTTPError as e:
      error_count += 1
      status = e.response.status_code if e.response is not None else "unknown"
      if status in (429, 502, 503, 504):
        current_wait = max(pause_seconds * 4, 20)
      print(
          f"[Overpass HTTP {status}] Error on {pcode} ({country_code}): {e}; "
          f"backing off {current_wait}s."
      )
    except Exception as e:
      error_count += 1
      current_wait = max(pause_seconds * 2, 10)
      print(
          f"[Overpass Error] {pcode} ({country_code}): {e}; "
          f"waiting {current_wait}s."
      )

    now_ts = time.time()
    if (
        (report_every_n and processed_records % report_every_n == 0)
        or (now_ts - last_report_time >= report_interval_seconds)
    ):
      _print_progress(
          processed_records=processed_records,
          limit_records=limit_records,
          matched_codes=matched_codes,
          total_addresses_added=total_addresses_added,
          error_count=error_count,
          start_time=start_time,
      )
      last_report_time = now_ts

    time.sleep(current_wait)

  _print_progress(
      processed_records=processed_records,
      limit_records=limit_records,
      matched_codes=matched_codes,
      total_addresses_added=total_addresses_added,
      error_count=error_count,
      start_time=start_time,
  )
  print("Background harvest finished.")


@anvil.server.callable
def start_geonames_harvest_test(limit_records=50):
  return anvil.server.launch_background_task(
      "harvest_geonames_postal_test",
      limit_records=limit_records,
      max_addresses_per_code=5,
      pause_seconds=4,
      report_every_n=10,
      report_interval_seconds=30,
  )


@anvil.server.callable
def start_individual_harvest(limit_records=50):
  return start_geonames_harvest_test(limit_records=limit_records)