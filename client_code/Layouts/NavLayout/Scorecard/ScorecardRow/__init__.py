from ._anvil_designer import ScorecardRowTemplate
from anvil import Label

SLOT_COLUMNS = [
    ("area", "Area", "left", "slot_area"),
    ("today", "Today", "right", "slot_today"),
    ("week", "This Week", "right", "slot_week"),
    ("month", "This Month", "right", "slot_month"),
    ("quarter", "This Quarter", "right", "slot_quarter"),
    ("year", "This Year", "right", "slot_year"),
    ("all_time", "All Time", "right", "slot_all_time"),
]


class ScorecardRow(ScorecardRowTemplate):

  def __init__(
      self,
      values=None,
      row_type="sub",  # "header" | "parent" | "sub"
      **properties,
  ):
    self.init_components(**properties)
    self._labels = {}
    self.set_row_data(values or {}, row_type=row_type)

  def set_row_data(self, values_by_key, row_type="sub"):
    for lbl in self._labels.values():
      lbl.remove_from_parent()
    self._labels.clear()

    grid_el = self.dom_nodes.get("row-grid")
    if grid_el is not None:
      grid_el.classList.remove("sc-header", "sc-parent", "sc-sub")
      if row_type == "header":
        grid_el.classList.add("sc-header")
      elif row_type == "parent":
        grid_el.classList.add("sc-parent")
      else:
        grid_el.classList.add("sc-sub")

    is_bold = row_type in ("header", "parent")

    for key, default_label, align, slot_name in SLOT_COLUMNS:
      text = (
          default_label
          if row_type == "header"
          else str(values_by_key.get(key, ""))
      )
      lbl = Label(
          text=text,
          align=align,
          bold=is_bold,
          spacing_above="none",
          spacing_below="none",
      )
      self.add_component(lbl, slot=slot_name)
      self._labels[key] = lbl