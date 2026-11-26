from ._anvil_designer import ScorecardTemplate
from anvil import Label
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

SAMPLE_GROUPS = [
    {
        "parent": {
            "area": "Operations",
            "today": "4",
            "week": "19",
            "month": "82",
            "quarter": "240",
            "year": "910",
            "all_time": "3,420",
        },
        "children": [
            {
                "area": "Intake & Triage",
                "today": "2",
                "week": "9",
                "month": "38",
                "quarter": "112",
                "year": "420",
                "all_time": "1,580",
            },
            {
                "area": "Follow-Ups & Reviews",
                "today": "2",
                "week": "10",
                "month": "44",
                "quarter": "128",
                "year": "490",
                "all_time": "1,840",
            },
        ],
    },
]


class Scorecard(ScorecardTemplate):

  def __init__(self, groups=None, **properties):
    self.init_components(**properties)
    self._header_labels = []
    self._rows = []
    self._build_headers()
    self.render_scorecard(SAMPLE_GROUPS if groups is None else groups)

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
      self.add_component(lbl, slot=slot_name)
      self._header_labels.append(lbl)

  def clear_rows(self):
    for row in self._rows:
      row.remove_from_parent()
    self._rows.clear()

  def render_scorecard(self, groups):
    self.clear_rows()

    for group in groups:
      parent_row = ScorecardRow(
          values=group.get("parent", {}),
          row_type="parent",
      )
      self.add_component(parent_row, slot="rows_slot")
      self._rows.append(parent_row)

      for child in group.get("children", []):
        child_row = ScorecardRow(
            values=child,
            row_type="sub",
        )
        self.add_component(child_row, slot="rows_slot")
        self._rows.append(child_row)