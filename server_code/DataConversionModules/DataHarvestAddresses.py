from datetime import datetime, timedelta
import itertools
import math
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

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

_ENDPOINT_CYCLE = itertools.cycle(OVERPASS_ENDPOINTS)
_ENDPOINT_COOLDOWN_UNTIL = {}


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


def _extract_coords(element):
  lat = element.get("lat")
  lon = element.get("lon")
  if lat is None or lon is None:
    center = element.get("center") or {}
    if lat is None:
      lat = center.get("lat")
    if lon is None:
      lon = center.get("lon")
  if lat is None or lon is None:
    return None, None
  try:
    return float(lat), float(lon)
  except (ValueError, TypeError):
    return None, None


def _haversine_km(lat1, lon1, lat2, lon2):
  r = 6371.0
  p1 = math.radians(lat1)
  p2 = math.radians(lat2)
  dp = math.radians(lat2 - lat1)
  dl = math.radians(lon2 - lon1)
  a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
  return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _check_area_match(lat, lon, geo_lat, geo_lon, max_distance_km=50.0, max_deg_delta=0.75):
  if geo_lat is None or geo_lon is None:
    return True, None

  if abs(lat - geo_lat) > max_deg_delta or abs(lon - geo_lon) > max_deg_delta:
    dist_km = _haversine_km(geo_lat, geo_lon, lat, lon)
    return False, (
        f"outside expected area ({lat:.4f}, {lon:.4f}) vs geo ({geo_lat:.4f}, {geo_lon:.4f}); "
        f"dist={dist_km:.1f}km > {max_distance_km:.0f}km"
    )

  dist_km = _haversine_km(geo_lat, geo_lon, lat, lon)
  if dist_km > max_distance_km:
    return False, (
        f"too far from geo ({geo_lat:.4f}, {geo_lon:.4f}): "
        f"dist={dist_km:.1f}km > {max_distance_km:.0f}km"
    )

  return True, None


def _parse_overpass_elements(
    data,
    pcode,
    max_addresses=5,
    geo_lat=None,
    geo_lon=None,
    max_distance_km=50.0,
    log_rejects=True,
    max_reject_logs=10,
):
  elements = data.get("elements", [])
  valid_elements = []
  reject_reasons = {}
  logged_rejects = 0

  for element in elements:
    el_type = element.get("type", "?")
    el_id = element.get("id", "?")
    tags = element.get("tags") or {}
    house_no = str(tags.get("addr:housenumber") or "").strip()
    street = str(tags.get("addr:street") or "").strip()
    lat, lon = _extract_coords(element)

    reasons = []
    if not house_no:
      reasons.append("missing addr:housenumber")
    if not street:
      reasons.append("missing addr:street")
    if lat is None or lon is None:
      reasons.append("missing/invalid lat/lon")
    else:
      in_area, area_reason = _check_area_match(
          lat, lon, geo_lat, geo_lon, max_distance_km=max_distance_km
      )
      if not in_area:
        reasons.append(area_reason)

    if reasons:
      reason_key = ", ".join(reasons)
      reject_reasons[reason_key] = reject_reasons.get(reason_key, 0) + 1
      if log_rejects and logged_rejects < max_reject_logs:
        print(f"    [REJECT] {el_type}/{el_id}: {reason_key} | tags={tags}")
        logged_rejects += 1
      continue

    valid_elements.append({
        "osm_ref": f"{el_type}/{el_id}",
        "house_no": house_no,
        "street": street,
        "city": str(tags.get("addr:city") or tags.get("addr:suburb") or "").strip(),
        "postcode": str(tags.get("addr:postcode") or pcode).strip(),
        "lat": lat,
        "lon": lon,
    })

  if reject_reasons:
    summary_str = "; ".join(f"{k}: {v}" for k, v in reject_reasons.items())
    extra_suppressed = max(0, sum(reject_reasons.values()) - logged_rejects)
    suppressed_note = f" ({extra_suppressed} detail lines suppressed)" if extra_suppressed else ""
    print(
        f"    [REJECT SUMMARY] {sum(reject_reasons.values())} of {len(elements)} elements rejected -> "
        f"{summary_str}{suppressed_note}"
    )
  else:
    print(f"    [ELEMENTS] Inspected {len(elements)} raw elements; 0 rejected.")

  if len(valid_elements) <= max_addresses:
    selected = valid_elements
  else:
    selected = random.sample(valid_elements, max_addresses)

  for idx, item in enumerate(selected, 1):
    print(
        f"    [GOOD {idx}/{len(selected)}] {item['osm_ref']} -> "
        f"'{item['house_no']} {item['street']}', city='{item['city'] or '-'}', "
        f"pc='{item['postcode']}', ({item['lat']:.5f}, {item['lon']:.5f})"
    )

  return selected, len(valid_elements), len(elements)


def _post_overpass_fast(headers, query, connect_timeout=6, read_timeout=10, cooldown_sec=120):
  """
  Try endpoints not currently on cooldown in round-robin order.
  If all endpoints are on cooldown, fall back to trying the full list once.
  """
  now = time.time()
  start_url = next(_ENDPOINT_CYCLE)
  start_idx = OVERPASS_ENDPOINTS.index(start_url)
  rotated = OVERPASS_ENDPOINTS[start_idx:] + OVERPASS_ENDPOINTS[:start_idx]

  active = [u for u in rotated if _ENDPOINT_COOLDOWN_UNTIL.get(u, 0) <= now]
  candidates = active if active else rotated

  if not active:
    print(f"    [COOLDOWN BYPASS] All {len(rotated)} endpoints in cooldown; probing once.")

  last_err = None
  for url in candidates:
    try:
      resp = requests.post(
          url,
          data={"data": query},
          headers=headers,
          timeout=(connect_timeout, read_timeout),
      )
      resp.raise_for_status()
      payload = resp.json()
      remark = str(payload.get("remark") or "")
      if "timed out" in remark.lower() or "out of memory" in remark.lower():
        raise RuntimeError(f"Overpass remark at {url}: {remark}")
      _ENDPOINT_COOLDOWN_UNTIL.pop(url, None)
      return payload, url
    except Exception as e:
      last_err = e
      _ENDPOINT_COOLDOWN_UNTIL[url] = time.time() + cooldown_sec
      print(f"    [ENDPOINT SKIP] {url} (cooldown {cooldown_sec}s) -> {e}")

  raise last_err


def _build_postcode_filter(pcode, country_code):
  clean = pcode.strip().upper()
  ca_compact = re.sub(r"\s+", "", clean)
  if country_code == "CA" and len(ca_compact) == 6:
    spaced = f"{ca_compact[:3]}\\s*{ca_compact[3:]}"
    return f'["addr:postcode"~"^{spaced}$",i]'
  if country_code == "CA" and len(ca_compact) <= 3:
    escaped = re.escape(ca_compact)
    return f'["addr:postcode"~"^{escaped}(\\s|$)",i]'
  return f'["addr:postcode"="{pcode.strip()}"]'


def _build_bbox_clause(geo_lat, geo_lon, deg_pad=0.35):
  if geo_lat is None or geo_lon is None:
    return ""
  s = round(geo_lat - deg_pad, 4)
  n = round(geo_lat + deg_pad, 4)
  w = round(geo_lon - deg_pad, 4)
  e = round(geo_lon + deg_pad, 4)
  return f"({s},{w},{n},{e})"


def _query_overpass_addresses(
    headers,
    pcode,
    country_code="",
    geo_lat=None,
    geo_lon=None,
    max_addresses=5,
    connect_timeout=6,
    read_timeout=10,
    max_distance_km=50.0,
):
  postcode_filter = _build_postcode_filter(pcode, country_code)
  bbox_clause = _build_bbox_clause(geo_lat, geo_lon, deg_pad=0.35)

  direct_query = f"""
  [out:json][timeout:10];
  (
    node{postcode_filter}["addr:street"]["addr:housenumber"]{bbox_clause};
    way{postcode_filter}["addr:street"]["addr:housenumber"]{bbox_clause};
  );
  out center tags;
  """
  print(
      f"  [REQUEST 1/2 - postcode+bbox] timeout=({connect_timeout}s, {read_timeout}s) "
      f"filter={postcode_filter} bbox={bbox_clause or 'NONE'} max_dist={max_distance_km}km"
  )
  data, used_url = _post_overpass_fast(
      headers, direct_query, connect_timeout=connect_timeout, read_timeout=read_timeout
  )
  print(f"    [ENDPOINT OK] {used_url}")
  results, total_valid, raw_count = _parse_overpass_elements(
      data,
      pcode,
      max_addresses=max_addresses,
      geo_lat=geo_lat,
      geo_lon=geo_lon,
      max_distance_km=max_distance_km,
  )
  if results:
    return results, "postcode+bbox", total_valid

  if raw_count == 0 and geo_lat is not None and geo_lon is not None:
    around_query = f"""
    [out:json][timeout:10];
    (
      node(around:2000,{geo_lat},{geo_lon})["addr:street"]["addr:housenumber"];
      way(around:2000,{geo_lat},{geo_lon})["addr:street"]["addr:housenumber"];
    );
    out center tags;
    """
    print(
        f"  [REQUEST 2/2 - around_2km] timeout=({connect_timeout}s, {read_timeout}s) "
        f"around=2000m at ({geo_lat}, {geo_lon})"
    )
    data_around, used_around_url = _post_overpass_fast(
        headers, around_query, connect_timeout=connect_timeout, read_timeout=read_timeout
    )
    print(f"    [ENDPOINT OK] {used_around_url}")
    results_around, total_around_valid, _ = _parse_overpass_elements(
        data_around,
        pcode,
        max_addresses=max_addresses,
        geo_lat=geo_lat,
        geo_lon=geo_lon,
        max_distance_km=max_distance_km,
    )
    if results_around:
      return results_around, "around_2km", total_around_valid
    return [], "around_2km(0)", total_around_valid

  return [], "postcode+bbox(0)", 0


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
    skipped_non_us,
    matched_codes,
    total_addresses_added,
    error_count,
    start_time,
):
  elapsed = time.time() - start_time
  rate = processed_records / elapsed if elapsed > 0 else 0.0
  limit_str = str(limit_records) if limit_records else "ALL"
  print(
      f"[Progress] US Checked: {processed_records}/{limit_str} (skipped non-US: {skipped_non_us}) | "
      f"Codes with hits: {matched_codes} | "
      f"Addresses added: {total_addresses_added} | "
      f"Errors: {error_count} | "
      f"Elapsed: {elapsed:.1f}s ({rate:.2f} rec/s)"
  )


@anvil.server.background_task
def harvest_geonames_postal_test(
    limit_records=50,
    max_addresses_per_code=5,
    pause_seconds=3,
    report_every_n=10,
    report_interval_seconds=30,
    connect_timeout=6,
    read_timeout=10,
    target_country="US",
    max_distance_km=50.0,
):
  headers = {
      "User-Agent": "AnvilGeoNamesHarvester/2.5 (contact: admin@app.com)"
  }
  target_cc = (target_country or "US").strip().upper()

  start_time = time.time()
  last_report_time = start_time
  print(
      f"Starting Overpass harvest from Data_Geonames_Postal for country='{target_cc}' "
      f"(limit={limit_records}, max_per_code={max_addresses_per_code}, "
      f"pause={pause_seconds}s, timeout=({connect_timeout}s, {read_timeout}s), "
      f"max_dist={max_distance_km}km)..."
  )

  rows = app_tables.data_geonames_postal.search()

  processed_records = 0
  skipped_non_us = 0
  matched_codes = 0
  total_addresses_added = 0
  error_count = 0
  consecutive_failures = 0
  seq_id = 1

  for row in rows:
    if limit_records is not None and processed_records >= limit_records:
      print(f"Reached {target_cc} record limit ({limit_records}). Stopping harvest.")
      break

    country_code = str(row["Country_code"] or "").strip().upper()
    pcode = str(row["Postal_code"] or "").strip()

    if not country_code or not pcode:
      continue

    if country_code != target_cc:
      skipped_non_us += 1
      if skipped_non_us == 1 or skipped_non_us % 500 == 0:
        print(
            f"  [SKIP] Bypassed {skipped_non_us} non-{target_cc} row(s) so far "
            f"(latest: {country_code} {pcode})..."
        )
      continue

    state_code = str(row["State_code"] or "").strip().upper()
    state_name = str(row["State_name"] or "").strip()
    fallback_city = str(row["Place"] or row["Community_name"] or "").strip()

    try:
      geo_lat = float(row["Latitude"]) if row["Latitude"] is not None else None
      geo_lon = float(row["Longitude"]) if row["Longitude"] is not None else None
    except (ValueError, TypeError):
      geo_lat, geo_lon = None, None

    processed_records += 1
    current_wait = pause_seconds
    print(
        f"\n[{processed_records}/{limit_records}] {target_cc} pcode='{pcode}' state='{state_code}' "
        f"place='{fallback_city}' geo=({geo_lat}, {geo_lon})"
    )

    try:
      sampled_addresses, source_mode, total_valid = _query_overpass_addresses(
          headers=headers,
          pcode=pcode,
          country_code=country_code,
          geo_lat=geo_lat,
          geo_lon=geo_lon,
          max_addresses=max_addresses_per_code,
          connect_timeout=connect_timeout,
          read_timeout=read_timeout,
          max_distance_km=max_distance_km,
      )
      consecutive_failures = 0
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
          f"  [RESULT] +{len(sampled_addresses)} saved (from {total_valid} valid) via {source_mode} | "
          f"total_added={total_addresses_added} | waiting {current_wait}s"
      )
    except requests.HTTPError as e:
      error_count += 1
      consecutive_failures += 1
      status = e.response.status_code if e.response is not None else "unknown"
      base_backoff = max(pause_seconds * 3, 12) if status in (429, 502, 503, 504) else max(pause_seconds * 2, 8)
      current_wait = min(45, base_backoff * (2 ** min(consecutive_failures - 1, 2)))
      print(
          f"  [Overpass HTTP {status}] {pcode} ({country_code}): {e}; "
          f"consecutive_failures={consecutive_failures}, backing off {current_wait}s."
      )
    except Exception as e:
      error_count += 1
      consecutive_failures += 1
      base_backoff = max(pause_seconds * 2, 8)
      current_wait = min(45, base_backoff * (2 ** min(consecutive_failures - 1, 2)))
      print(
          f"  [Overpass Error] {pcode} ({country_code}): {e}; "
          f"consecutive_failures={consecutive_failures}, waiting {current_wait}s."
      )

    now_ts = time.time()
    if (
        (report_every_n and processed_records % report_every_n == 0)
        or (now_ts - last_report_time >= report_interval_seconds)
    ):
      _print_progress(
          processed_records=processed_records,
          limit_records=limit_records,
          skipped_non_us=skipped_non_us,
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
      skipped_non_us=skipped_non_us,
      matched_codes=matched_codes,
      total_addresses_added=total_addresses_added,
      error_count=error_count,
      start_time=start_time,
  )
  print("Background harvest finished.")


@anvil.server.callable
def start_geonames_harvest_test(limit_records=50, target_country="US", max_distance_km=50.0):
  return anvil.server.launch_background_task(
      "harvest_geonames_postal_test",
      limit_records=limit_records,
      max_addresses_per_code=5,
      pause_seconds=3,
      report_every_n=10,
      report_interval_seconds=30,
      connect_timeout=6,
      read_timeout=10,
      target_country=target_country,
      max_distance_km=max_distance_km,
  )


@anvil.server.callable
def start_individual_harvest(limit_records=50, target_country="US", max_distance_km=50.0):
  return start_geonames_harvest_test(
      limit_records=limit_records,
      target_country=target_country,
      max_distance_km=max_distance_km,
  )


@anvil.server.background_task
def delete_ca_short_codes_task(report_every_n=500, pause_every_n=250, pause_seconds=0.2):
  start_time = time.time()
  checked = 0
  deleted = 0
  skipped = 0
  stopped_on_mx = False

  print("Starting CA 3-character postal code cleanup on Data_Geonames_Postal...")
  rows = app_tables.data_geonames_postal.search()

  for row in rows:
    checked += 1
    country_code = str(row["Country_code"] or "").strip().upper()
    pcode = str(row["Postal_code"] or "").strip()

    if country_code == "MX":
      print(f"Reached 'MX' record at row #{checked} (Postal_code='{pcode}'). Stopping cleanup.")
      stopped_on_mx = True
      break

    if country_code == "CA" and len(pcode) == 3:
      row.delete()
      deleted += 1
    else:
      skipped += 1

    if report_every_n and checked % report_every_n == 0:
      elapsed = time.time() - start_time
      print(
          f"[Cleanup Progress] Checked: {checked} | Deleted (CA 3-char): {deleted} | "
          f"Skipped: {skipped} | Elapsed: {elapsed:.1f}s"
      )

    if pause_every_n and pause_seconds and checked % pause_every_n == 0:
      time.sleep(pause_seconds)

  elapsed = time.time() - start_time
  print(
      f"Cleanup finished in {elapsed:.1f}s. Checked: {checked}, "
      f"Deleted: {deleted}, Skipped: {skipped}, Stopped on MX: {stopped_on_mx}."
  )
  return {
      "checked": checked,
      "deleted": deleted,
      "skipped": skipped,
      "stopped_on_mx": stopped_on_mx,
  }


@anvil.server.callable
def start_delete_ca_short_codes():
  return anvil.server.launch_background_task("delete_ca_short_codes_task")