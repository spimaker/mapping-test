import time
from datetime import datetime, timedelta, timezone
import anvil.server
from anvil.tables import app_tables

_BRANCH_CACHE_TTL = 120
_BRANCH_CACHE = {}


def _clean_str(val, fallback=""):
  if val is None:
    return fallback
  s = str(val).strip()
  return s if s else fallback


def _format_code_with_name(code_val, name_val, fallback):
  code = _clean_str(code_val)
  name = _clean_str(name_val)
  if code and name and name.lower() != code.lower():
    return f"{code} ({name})"
  if code:
    return code
  if name:
    return name
  return fallback


def _period_bounds(now_dt):
  d = now_dt.date()
  day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

  week_start_date = d - timedelta(days=d.weekday())
  week_start = datetime(
      week_start_date.year,
      week_start_date.month,
      week_start_date.day,
      tzinfo=timezone.utc,
  )

  month_start = datetime(d.year, d.month, 1, tzinfo=timezone.utc)

  q_start_month = ((d.month - 1) // 3) * 3 + 1
  quarter_start = datetime(d.year, q_start_month, 1, tzinfo=timezone.utc)

  year_start = datetime(d.year, 1, 1, tzinfo=timezone.utc)

  return {
      "today": day_start,
      "week": week_start,
      "month": month_start,
      "quarter": quarter_start,
      "year": year_start,
  }


def _normalize_dt(dt_val):
  if dt_val is None:
    return None
  if hasattr(dt_val, "tzinfo") and dt_val.tzinfo:
    return dt_val.astimezone(timezone.utc)
  return dt_val.replace(tzinfo=timezone.utc)


def _empty_counts():
  return {
      "today": 0,
      "week": 0,
      "month": 0,
      "quarter": 0,
      "year": 0,
      "all_time": 0,
  }


def _has_any_activity(counts):
  return any(v > 0 for v in counts.values())


def _format_row(display_label, key_value, counts, next_level, path, has_children):
  return {
      "area": display_label,
      "key": key_value,
      "level": next_level,
      "path": path,
      "has_children": has_children,
      "today": f"{counts['today']:,}",
      "week": f"{counts['week']:,}",
      "month": f"{counts['month']:,}",
      "quarter": f"{counts['quarter']:,}",
      "year": f"{counts['year']:,}",
      "all_time": f"{counts['all_time']:,}",
  }


def _aggregate_rows(rows_iter, key_and_label_fn, path_fn, next_level, has_children, bounds, skip_all_zero):
  # buckets[calc_key] = {"label": display_label, "counts": {...}}
  buckets = {}

  for row in rows_iter:
    calc_key, display_label = key_and_label_fn(row)
    item = buckets.get(calc_key)
    if item is None:
      item = {"label": display_label, "counts": _empty_counts()}
      buckets[calc_key] = item

    counts = item["counts"]
    counts["all_time"] += 1

    dt_norm = _normalize_dt(row["date_time"])
    if dt_norm is not None:
      if dt_norm >= bounds["year"]:
        counts["year"] += 1
      if dt_norm >= bounds["quarter"]:
        counts["quarter"] += 1
      if dt_norm >= bounds["month"]:
        counts["month"] += 1
      if dt_norm >= bounds["week"]:
        counts["week"] += 1
      if dt_norm >= bounds["today"]:
        counts["today"] += 1

  result = []
  for calc_key, item in buckets.items():
    counts = item["counts"]
    if skip_all_zero and not _has_any_activity(counts):
      continue
    result.append(
        _format_row(
            display_label=item["label"],
            key_value=calc_key,
            counts=counts,
            next_level=next_level,
            path=path_fn(calc_key),
            has_children=has_children,
        )
    )

  result.sort(key=lambda r: r["area"].lower())
  return result


def _region_key_label(row):
  val = _clean_str(row["region"], "Unspecified Region")
  return val, val


def _country_key_label(row):
  code = _clean_str(row["country_code"], "UNSPEC")
  label = _format_code_with_name(row["country_code"], row["country_name"], "Unspecified Country")
  return code, label


def _state_key_label(row):
  st = _clean_str(row["state"], "Unspecified State")
  label = _format_code_with_name(row["state"], row["state_name"], "Unspecified State")
  return st, label


def _city_key_label(row):
  val = _clean_str(row["city"], "Unspecified City")
  return val, val


def _postal_key_label(row):
  val = _clean_str(row["postal_code"], "Unspecified Postal Code")
  return val, val


def _compute_branch(level, path_tuple, bounds):
  skip_all_zero = level != "region"

  if level == "region":
    return _aggregate_rows(
        app_tables.mapitems_test.search(),
        key_and_label_fn=_region_key_label,
        path_fn=lambda k: [k],
        next_level="country",
        has_children=True,
        bounds=bounds,
        skip_all_zero=skip_all_zero,
    )

  if level == "country" and len(path_tuple) == 1:
    region_val = path_tuple[0]
    return _aggregate_rows(
        app_tables.mapitems_test.search(region=region_val),
        key_and_label_fn=_country_key_label,
        path_fn=lambda k: [region_val, k],
        next_level="state",
        has_children=True,
        bounds=bounds,
        skip_all_zero=skip_all_zero,
    )

  if level == "state" and len(path_tuple) == 2:
    region_val, country_code_val = path_tuple
    matched = (
        r for r in app_tables.mapitems_test.search(country_code=country_code_val)
        if _clean_str(r["region"], "Unspecified Region") == region_val
    )
    return _aggregate_rows(
        matched,
        key_and_label_fn=_state_key_label,
        path_fn=lambda k: [region_val, country_code_val, k],
        next_level="city",
        has_children=True,
        bounds=bounds,
        skip_all_zero=skip_all_zero,
    )

  if level == "city" and len(path_tuple) == 3:
    region_val, country_code_val, state_val = path_tuple
    matched = (
        r for r in app_tables.mapitems_test.search(state=state_val)
        if _clean_str(r["region"], "Unspecified Region") == region_val
        and _clean_str(row["country_code"], "UNSPEC") == country_code_val
    )
    return _aggregate_rows(
        matched,
        key_and_label_fn=_city_key_label,
        path_fn=lambda k: [region_val, country_code_val, state_val, k],
        next_level="postal",
        has_children=True,
        bounds=bounds,
        skip_all_zero=skip_all_zero,
    )

  if level == "postal" and len(path_tuple) == 4:
    region_val, country_code_val, state_val, city_val = path_tuple
    matched = (
        r for r in app_tables.mapitems_test.search(city=city_val)
        if _clean_str(r["region"], "Unspecified Region") == region_val
        and _clean_str(r["country_code"], "UNSPEC") == country_code_val
        and _clean_str(r["state"], "Unspecified State") == state_val
    )
    return _aggregate_rows(
        matched,
        key_and_label_fn=_postal_key_label,
        path_fn=lambda k: [region_val, country_code_val, state_val, city_val, k],
        next_level=None,
        has_children=False,
        bounds=bounds,
        skip_all_zero=skip_all_zero,
    )

  return []


@anvil.server.callable
def get_scorecard_children(level="region", path=None, force_refresh=False):
  now_dt = datetime.now(timezone.utc)
  bounds = _period_bounds(now_dt)
  path_tuple = tuple(path or [])
  cache_key = (level, path_tuple, now_dt.date().isoformat())

  now_ts = time.monotonic()
  cached = _BRANCH_CACHE.get(cache_key)
  if not force_refresh and cached is not None:
    built_at, cached_rows = cached
    if (now_ts - built_at) <= _BRANCH_CACHE_TTL:
      return cached_rows

  rows = _compute_branch(level, path_tuple, bounds)
  _BRANCH_CACHE[cache_key] = (now_ts, rows)
  return rows


@anvil.server.callable
def refresh_scorecard_cache():
  _BRANCH_CACHE.clear()
  return {"status": "cleared"}