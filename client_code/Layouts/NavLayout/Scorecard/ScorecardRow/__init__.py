from ._anvil_designer import ScorecardRowTemplate
from anvil import Label, Link

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
      depth=0,
      expanded=False,
      on_toggle=None,
      **properties,
  ):
    self.init_components(**properties)
    self._labels = {}
    self._values = values or {}
    self._on_toggle = on_toggle
    self.set_row_data(
        self._values,
        row_type=row_type,
        depth=depth,
        expanded=expanded,
    )

  def _add_to_slot(self, component, slot_name):
    if hasattr(self, "slots") and slot_name in self.slots:
      self.slots[slot_name].add_component(component)
    else:
      self.add_component(component, slot=slot_name)

  def _on_area_click(self, **event_args):
    if self._values.get("has_children") and callable(self._on_toggle):
      self._on_toggle(self._values)

  def set_row_data(self, values_by_key, row_type="sub", depth=0, expanded=False):
    self._values = values_by_key
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
    has_children = bool(values_by_key.get("has_children"))
    indent = "  " * max(0, depth)

    for key, default_label, align, slot_name in SLOT_COLUMNS:
      if row_type == "header":
        text = default_label
        comp = Label(
            text=text,
            align=align,
            bold=is_bold,
            spacing_above="none",
            spacing_below="none",
        )
      elif key == "area":
        raw_area = str(values_by_key.get(key, ""))
        if has_children:
          caret = "▾ " if expanded else "▸ "
          text = f"{indent}{caret}{raw_area}"
          comp = Link(text=text, align=align, bold=is_bold)
          comp.set_event_handler("click", self._on_area_click)
        else:
          text = f"{indent}{raw_area}"
          comp = Label(
              text=text,
              align=align,
              bold=is_bold,
              spacing_above="none",
              spacing_below="none",
          )
      else:
        text = str(values_by_key.get(key, ""))
        comp = Label(
            text=text,
            align=align,
            bold=is_bold,
            spacing_above="none",
            spacing_below="none",
        )

      self._add_to_slot(comp, slot_name)
      self._labels[key] = comp