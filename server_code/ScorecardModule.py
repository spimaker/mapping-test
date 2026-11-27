import time
from datetime import datetime, timedelta, timezone
import anvil.server
import anvil.tables
from anvil.tables import app_tables

METRIC_KEYS = ("today", "week", "month", "quarter", "year", "all_time")
STALE_AFTER_MINUTES = 60
LOCK_LEASE_MINUTES = 20


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


@anvil.tables.in_transaction
def _try_acquire_rollup_lock(force=False):
    now_dt = datetime.now(timezone.utc)
    status_row = app_tables.scorecard_status.get(key="global_rollup")

    if status_row is None:
        app_tables.scorecard_status.add_row(
            key="global_rollup",
            is_running=True,
            expires_at=now_dt + timedelta(minutes=LOCK_LEASE_MINUTES),
            last_completed_at=None,
            time_run_seconds=None,
        )
        return True

    expires_at = _normalize_dt(status_row["expires_at"])
    last_done = _normalize_dt(status_row["last_completed_at"])

    if status_row["is_running"] and expires_at is not None and expires_at > now_dt:
        return False

    if not force and last_done is not None:
        same_utc_day = last_done.date() == now_dt.date()
        age = now_dt - last_done
        if same_utc_day and age < timedelta(minutes=STALE_AFTER_MINUTES):
            return False

    status_row.update(
        is_running=True,
        expires_at=now_dt + timedelta(minutes=LOCK_LEASE_MINUTES),
    )
    return True


@anvil.tables.in_transaction
def _release_rollup_lock(completed_at=None, time_run_seconds=None):
    status_row = app_tables.scorecard_status.get(key="global_rollup")
    updates = {
        "is_running": False,
        "expires_at": None,
    }
    if time_run_seconds is not None:
        updates["time_run_seconds"] = time_run_seconds
    if completed_at is not None:
        updates["last_completed_at"] = completed_at

    if status_row is not None:
        status_row.update(**updates)
    else:
        app_tables.scorecard_status.add_row(
            key="global_rollup",
            is_running=False,
            expires_at=None,
            last_completed_at=completed_at,
            time_run_seconds=time_run_seconds,
        )


def trigger_rollup_if_needed(force=False):
    if _try_acquire_rollup_lock(force=force):
        anvil.server.launch_background_task(
            "rebuild_scorecard_rollups_task",
            lock_acquired=True,
        )
        return True
    return False


@anvil.server.background_task
def rebuild_scorecard_rollups_task(lock_acquired=False):
    if not lock_acquired:
        if not _try_acquire_rollup_lock(force=True):
            return

    start_mono = time.monotonic()
    now_dt = datetime.now(timezone.utc)
    try:
        bounds = _period_bounds(now_dt)
        rollup_map = {}

        for row in app_tables.mapitems_test.search():
            region = _clean_str(row["region"], "Unspecified Region")
            country_code = _clean_str(row["country_code"], "UNSPEC")
            country_label = _format_code_with_name(
                row["country_code"], row["country_name"], "Unspecified Country"
            )
            state_code = _clean_str(row["state"], "Unspecified State")
            state_label = _format_code_with_name(
                row["state"], row["state_name"], "Unspecified State"
            )
            city = _clean_str(row["city"], "Unspecified City")
            postal = _clean_str(row["postal_code"], "Unspecified Postal Code")

            dt_norm = _normalize_dt(row["date_time"])
            inc = {
                "today": 1 if (dt_norm is not None and dt_norm >= bounds["today"]) else 0,
                "week": 1 if (dt_norm is not None and dt_norm >= bounds["week"]) else 0,
                "month": 1 if (dt_norm is not None and dt_norm >= bounds["month"]) else 0,
                "quarter": 1 if (dt_norm is not None and dt_norm >= bounds["quarter"]) else 0,
                "year": 1 if (dt_norm is not None and dt_norm >= bounds["year"]) else 0,
                "all_time": 1,
            }

            levels = (
                ("region", "", region, region, (region,)),
                ("country", region, country_code, country_label, (region, country_code)),
                (
                    "state",
                    f"{region}|{country_code}",
                    state_code,
                    state_label,
                    (region, country_code, state_code),
                ),
                (
                    "city",
                    f"{region}|{country_code}|{state_code}",
                    city,
                    city,
                    (region, country_code, state_code, city),
                ),
                (
                    "postal",
                    f"{region}|{country_code}|{state_code}|{city}",
                    postal,
                    postal,
                    (region, country_code, state_code, city, postal),
                ),
            )

            for lvl, parent_key, calc_key, disp_label, path_tuple in levels:
                path_key = "|".join(path_tuple)
                entry = rollup_map.get(path_key)
                if entry is None:
                    entry = {
                        "level": lvl,
                        "parent_key": parent_key,
                        "path_key": path_key,
                        "calc_key": calc_key,
                        "label": disp_label,
                        "today": 0,
                        "week": 0,
                        "month": 0,
                        "quarter": 0,
                        "year": 0,
                        "all_time": 0,
                    }
                    rollup_map[path_key] = entry
                for k in METRIC_KEYS:
                    entry[k] += inc[k]

        existing = {r["path_key"]: r for r in app_tables.scorecard_rollups.search()}
        for path_key, entry in rollup_map.items():
            payload = {
                "level": entry["level"],
                "parent_key": entry["parent_key"],
                "path_key": path_key,
                "calc_key": entry["calc_key"],
                "label": entry["label"],
                "today": entry["today"],
                "week": entry["week"],
                "month": entry["month"],
                "quarter": entry["quarter"],
                "year": entry["year"],
                "all_time": entry["all_time"],
                "updated_at": now_dt,
            }
            row_obj = existing.pop(path_key, None)
            if row_obj is not None:
                row_obj.update(**payload)
            else:
                app_tables.scorecard_rollups.add_row(**payload)

        for stale_row in existing.values():
            stale_row.delete()

        elapsed_sec = round(time.monotonic() - start_mono, 2)
        _release_rollup_lock(
            completed_at=datetime.now(timezone.utc),
            time_run_seconds=elapsed_sec,
        )
    except Exception:
        elapsed_sec = round(time.monotonic() - start_mono, 2)
        _release_rollup_lock(completed_at=None, time_run_seconds=elapsed_sec)
        raise


@anvil.server.background_task
def rebuild_scorecard_rollups():
    """Alias matching the Scheduled Task name in your settings."""
    rebuild_scorecard_rollups_task(lock_acquired=False)


@anvil.server.callable
def start_scorecard_rollup(force=True):
    started = trigger_rollup_if_needed(force=force)
    return {"started": started}


@anvil.server.callable
def get_scorecard_children(level="region", path=None, force_refresh=False):
    parent_key = "|".join(path or [])
    skip_all_zero = level != "region"
    next_level_map = {
        "region": ("country", True),
        "country": ("state", True),
        "state": ("city", True),
        "city": ("postal", True),
        "postal": (None, False),
    }
    if level not in next_level_map:
        return []

    rollup_rows = list(
        app_tables.scorecard_rollups.search(level=level, parent_key=parent_key)
    )

    if level == "region":
        trigger_rollup_if_needed(force=(force_refresh or not rollup_rows))

    next_level, has_children = next_level_map[level]
    base_path = list(path or [])
    rows = []

    for r in rollup_rows:
        counts = {k: int(r[k] or 0) for k in METRIC_KEYS}
        if skip_all_zero and not any(v > 0 for v in counts.values()):
            continue

        calc_key = r["calc_key"] or r["label"]
        rows.append({
            "area": r["label"],
            "level": next_level,
            "path": base_path + [calc_key],
            "has_children": has_children,
            "today": f"{counts['today']:,}",
            "week": f"{counts['week']:,}",
            "month": f"{counts['month']:,}",
            "quarter": f"{counts['quarter']:,}",
            "year": f"{counts['year']:,}",
            "all_time": f"{counts['all_time']:,}",
        })

    rows.sort(key=lambda item: item["area"].lower())
    return rows