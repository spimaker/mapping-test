import csv
import io
import time
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
  """Map 12-column GeoNames postal TSV row to Data_GeoNames_Postal schema."""
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


def _run_import_batch(
    file,
    start_row=0,
    max_rows=500,
    max_seconds=20.0,
    log_every=250,
):
  t0 = time.perf_counter()
  print(
      f"[DIAG] Starting import batch: start_row={start_row}, "
      f"max_rows={max_rows}, max_seconds={max_seconds}"
  )

  if file is None:
    print("[DIAG] ERROR: No file object received.")
    return {
        "inserted": 0,
        "malformed": 0,
        "processed_in_batch": 0,
        "next_start_row": start_row,
        "reached_eof": True,
        "elapsed_sec": 0.0,
        "error": "No file provided",
    }

  t_read_start = time.perf_counter()
  raw_bytes = file.get_bytes()
  raw_text = raw_bytes.decode("utf-8", errors="replace")
  t_read_done = time.perf_counter()
  print(
      f"[DIAG] File read & decoded: {len(raw_bytes):,} bytes in "
      f"{t_read_done - t_read_start:.2f}s"
  )

  reader = csv.reader(io.StringIO(raw_text), delimiter="\t", quoting=csv.QUOTE_NONE)
  table = app_tables.data_geonames_postal

  data_row_idx = 0
  processed_in_batch = 0
  inserted = 0
  malformed = 0
  reached_eof = True
  stopped_by_time = False

  t_loop_start = time.perf_counter()

  for line_num, cols in enumerate(reader, start=1):
    if not cols or all(not c.strip() for c in cols):
      continue

    if data_row_idx < start_row:
      data_row_idx += 1
      continue

    if max_rows is not None and processed_in_batch >= max_rows:
      reached_eof = False
      break

    elapsed_loop = time.perf_counter() - t_loop_start
    if max_seconds is not None and elapsed_loop >= max_seconds and processed_in_batch > 0:
      reached_eof = False
      stopped_by_time = True
      print(
          f"[DIAG] Time guard hit at {elapsed_loop:.2f}s after "
          f"{processed_in_batch} rows; pausing batch cleanly."
      )
      break

    data_row_idx += 1
    processed_in_batch += 1

    record = _parse_geonames_tsv_row(cols)
    if record is None:
      malformed += 1
      print(
          f"False: {{'line': {line_num}, 'row': {data_row_idx}, "
          f"'reason': 'Malformed/short row', 'raw': {cols}}}"
      )
      continue

    t_row_start = time.perf_counter()
    try:
      table.add_row(**record)
      inserted += 1
      row_ms = (time.perf_counter() - t_row_start) * 1000.0
      if inserted <= 5 or inserted % log_every == 0:
        total_elapsed = max(time.perf_counter() - t0, 0.001)
        rate = inserted / total_elapsed
        print(
            f"True: inserted={inserted} (line={line_num}, row={data_row_idx}, "
            f"add_row={row_ms:.1f}ms, rate={rate:.1f} rows/s) -> "
            f"{record['Country_code']} {record['Postal_code']} ({record['Place']})"
        )
    except Exception as e:
      malformed += 1
      print(
          f"False: {{'line': {line_num}, 'row': {data_row_idx}, "
          f"'error': {str(e)!r}, 'record': {record}}}"
      )

  next_start_row = start_row + processed_in_batch
  total_elapsed = round(time.perf_counter() - t0, 2)
  rate = round(inserted / max(total_elapsed, 0.01), 1)

  summary = {
      "inserted": inserted,
      "malformed": malformed,
      "processed_in_batch": processed_in_batch,
      "next_start_row": next_start_row,
      "reached_eof": reached_eof,
      "stopped_by_time": stopped_by_time,
      "elapsed_sec": total_elapsed,
      "rows_per_sec": rate,
  }
  print(f"[DIAG] Batch summary: {summary}")
  return summary


@anvil.server.background_task
def import_geonames_file_bg(
    file,
    start_row=0,
    max_rows=5000,
    max_seconds=240.0,
    log_every=500,
):
  return _run_import_batch(
      file=file,
      start_row=start_row,
      max_rows=max_rows,
      max_seconds=max_seconds,
      log_every=log_every,
  )


@anvil.server.callable
def import_geonames_file(
    file,
    start_row=0,
    max_rows=500,
    max_seconds=20.0,
    log_every=250,
    use_background_task=False,
):
  """Import rows from an uploaded GeoNames TSV file into Data_GeoNames_Postal."""
  print(
      f"[DIAG] Callable invoked: start_row={start_row}, max_rows={max_rows}, "
      f"use_background_task={use_background_task}"
  )
  if use_background_task:
    task = anvil.server.launch_background_task(
        "import_geonames_file_bg",
        file=file,
        start_row=start_row,
        max_rows=max_rows,
        max_seconds=max_seconds,
        log_every=log_every,
    )
    print(f"[DIAG] Launched background task: {task.get_id()}")
    return {"background_task_id": task.get_id(), "status": "started"}

  return _run_import_batch(
      file=file,
      start_row=start_row,
      max_rows=max_rows,
      max_seconds=max_seconds,
      log_every=log_every,
  )