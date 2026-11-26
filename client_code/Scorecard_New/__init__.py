from ._anvil_designer import Scorecard_NewTemplate
from anvil import Label


COLUMNS = [
    ("area", "Area", "left", "5"),
    ("today", "Today", "right", "1"),
    ("week", "This Week", "right", "1"),
    ("month", "This Month", "right", "1"),
    ("quarter", "This Quarter", "right", "1"),
    ("year", "This Year", "right", "1"),
    ("all_time", "All Time", "right", "2"),
]


def build_scorecard_row(container, values_by_key, is_header=False, indent_px=0):
  """Populate a single 7-column row inside a ColumnPanel."""
  row_labels = {}
  first_comp = None

  for key, default_label, align, col_span in COLUMNS:
    text = (
        default_label
        if is_header
        else str(values_by_key.get(key, ""))
    )
    lbl = Label(
        text=text,
        align=align,
        bold=is_header,
        spacing_above="none",
        spacing_below="none",
    )
    if key == "area" and indent_px > 0 and not is_header:
      lbl.role = "scorecard-indent"
    elif key != "area":
      lbl.role = "scorecard-num"

    if first_comp is None:
      container.add_component(lbl, width=col_span)
      first_comp = lbl
    else:
      # Attach subsequent columns onto the same row as first_comp
      container.add_component(lbl, row=first_comp, width=col_span)

    row_labels[key] = lbl

  return row_labels