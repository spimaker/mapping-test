from ._anvil_designer import ScorecardTemplate
from anvil import Label
import anvil.server
from .ScorecardRow import ScorecardRow

HEADER_COLUMNS = [
    ("Area", "left", "hdr_area"),
    ("Today", "right", "hdr_today"),
    ("This Week", "right", "hdr_week"),
    ("This Month", "right", "hdr_month"),
    ("This Quarter", "right", "hdr_quarter"),
    ("This Year", "right", "hdr_year"),
    ("All Time", "right", "hdr_all_time"),
]


class Scorecard(ScorecardTemplate):

  def __init__(self, **properties):
    self.init_components(**properties)
    self._header_labels = []
    self._rows = []
    self._expanded_paths = set()
    self._children_cache = {}
    self._build_headers()
    self.load_scorecard()

  def _add_to_target(self, component, slot_name):
    if hasattr(self, "slots") and slot_name in self.slots:
      self.slots[slot_name].add_component(component)
    else:
      self.add_component(component, slot=slot_name)

  def _build_headers(self):
    for lbl in self._header_labels:
      lbl.remove_from_parent()
    self._header_labels.clear()

    for title, align, slot_name in HEADER_COLUMNS:
      lbl = Label(
          text=title,
          align=align,
          bold=True,
          spacing_above="none",
          spacing_below="none",
      )
      self._add_to_target(lbl, slot_name)
      self._header_labels.append(lbl)

  def _path_key(self, path):
    return "|".join(path or [])

  def load_scorecard(self, force_refresh=False):
    self._expanded_paths.clear()
    self._children_cache.clear()
    regions = (
        anvil.server.call(
            "get_scorecard_children",
            level="region",
            path=None,
            force_refresh=force_refresh,
        )
        or []
    )
    self._children_cache[""] = regions
    self.render_hierarchy()

  def _toggle_node(self, node_data):
    next_level = node_data.get("level")
    node_path = node_data.get("path") or []
    if not next_level:
      return

    key = self._path_key(node_path)
    if key in self._expanded_paths:
      self._expanded_paths.remove(key)
    else:
      self._expanded_paths.add(key)
      if key not in self._children_cache:
        self._children_cache[key] = (
            anvil.server.call(
                "get_scorecard_children",
                level=next_level,
                path=node_path,
            )
            or []
        )

    self.render_hierarchy()

  def clear_rows(self):
    for row in self._rows:
      row.remove_from_parent()
    self._rows.clear()

  def _append_level(self, nodes, depth):
    for node in nodes:
      node_path = node.get("path") or []
      key = self._path_key(node_path)
      is_expanded = key in self._expanded_paths
      row_type = "parent" if depth == 0 else "sub"

      row_comp = ScorecardRow(
          values=node,
          row_type=row_type,
          depth=depth,
          expanded=is_expanded,
          on_toggle=self._toggle_node,
      )
      self._add_to_target(row_comp, "rows_slot")
      self._rows.append(row_comp)

      if is_expanded and node.get("has_children"):
        child_nodes = self._children_cache.get(key, [])
        self._append_level(child_nodes, depth + 1)

  def render_hierarchy(self):
    self.clear_rows()
    self._append_level(self._children_cache.get("", []), depth=0)