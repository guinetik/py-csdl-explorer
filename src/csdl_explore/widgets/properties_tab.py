"""Properties sub-tab — DataTable of entity properties with fuzzy filtering."""

from textual.widgets import DataTable, TabPane

from ..parser import EntityType
from ..formatters import sort_properties, format_property_table_row, fuzzy_match
from ..themes import VERCEL_THEME


class PropertiesTab(TabPane):
    """Properties sub-tab with a filterable DataTable.

    Args:
        entity: The entity type whose properties to display.
        tab_id: Unique tab pane ID.
    """

    def __init__(self, entity: EntityType, tab_id: str) -> None:
        super().__init__("Properties", id=tab_id)
        self._entity = entity
        self._prop_rows: list[tuple] = []
        self._table_filter: str = ""

    def compose(self):
        yield DataTable(
            id=f"prop-table-{self._entity.name}",
            zebra_stripes=True,
            cursor_type="row",
        )

    def on_mount(self) -> None:
        """Populate the property table after mount."""
        self._setup_table()

    def _setup_table(self) -> None:
        """Add columns and rows to the DataTable."""
        entity = self._entity
        ac = VERCEL_THEME.accent

        prop_table = self.query_one(f"#prop-table-{entity.name}", DataTable)
        prop_table.add_column("Property", width=25, key="name")
        prop_table.add_column("Type", width=15, key="type")
        prop_table.add_column("Len", width=5, key="len")
        prop_table.add_column("Label", width=20, key="label")
        prop_table.add_column("Picklist", width=18, key="picklist")
        prop_table.add_column("Req", width=3, key="req")
        prop_table.add_column("C", width=3, key="create")
        prop_table.add_column("U", width=3, key="update")
        prop_table.add_column("Up", width=3, key="upsert")
        prop_table.add_column("Vis", width=3, key="vis")
        prop_table.add_column("Sort", width=4, key="sort")
        prop_table.add_column("Filt", width=4, key="filt")

        self._prop_rows = []
        for prop in sort_properties(entity.properties, entity.keys):
            row = format_property_table_row(
                prop, keys=entity.keys, accent_color=ac,
            )
            self._prop_rows.append(row)
            prop_table.add_row(*row)

    def apply_filter(self, term: str) -> tuple[int, int]:
        """Filter the property table by fuzzy match.

        Args:
            term: The filter string (lowercase).

        Returns:
            Tuple of (matched_count, total_count).
        """
        self._table_filter = term
        try:
            prop_table = self.query_one(f"#prop-table-{self._entity.name}", DataTable)
        except Exception:
            return (0, 0)

        prop_table.clear()

        if not term:
            for row in self._prop_rows:
                prop_table.add_row(*row)
            return (len(self._prop_rows), len(self._prop_rows))

        matched = 0
        for row in self._prop_rows:
            row_text = " ".join(str(c) for c in row).lower()
            if fuzzy_match(term, row_text):
                prop_table.add_row(*row)
                matched += 1
        return (matched, len(self._prop_rows))
