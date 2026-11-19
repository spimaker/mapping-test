import time
import anvil.server
from anvil.tables import app_tables


@anvil.server.background_task
def delete_ca_short_codes_task(report_every_n=500, pause_every_n=250, pause_seconds=0.2):
  """
  Iterates through Data_Geonames_Postal and deletes CA rows where Postal_code
  is 3 characters (stripped length == 3). Stops as soon as an MX row is reached.
  """
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