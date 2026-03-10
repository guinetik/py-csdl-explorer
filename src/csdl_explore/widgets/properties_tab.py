"""Properties sub-tab — FilterableDataTable of entity properties with fuzzy filtering."""

from textual import on
from textual.widgets import TabPane

from ..parser import EntityType
from ..formatters import sort_properties, format_property_table_row
from ..themes import VERCEL_THEME
from .filterable_table import FilterableDataTable
from .record_view_modal import RecordViewModal


class PropertiesTab(TabPane):
    """Properties sub-tab with a filterable DataTable.

    Args:
        entity: The entity type whose properties to display.
        tab_id: Unique tab pane ID.
    """

    def __init__(self, entity: EntityType, tab_id: str) -> None:
        super().__init__("Properties", id=tab_id)
        self._entity = entity

    def compose(self):
        yield FilterableDataTable(
            id=f"prop-table-{self._entity.name}",
            zebra_stripes=True,
            cursor_type="row",
        )

    def on_mount(self) -> None:
        """Populate the property table after mount."""
        self._setup_table()

    # Column labels for the record-view modal (order matches add_column calls).
    _COLUMN_LABELS = [
        "Property", "Type", "Length", "Label", "Picklist",
        "Required", "Creatable", "Updatable", "Upsertable",
        "Visible", "Sortable", "Filterable",
    ]

    def _setup_table(self) -> None:
        """Add columns and rows to the FilterableDataTable."""
        entity = self._entity
        ac = VERCEL_THEME.accent

        prop_table = self.query_one(f"#prop-table-{entity.name}", FilterableDataTable)
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

        for prop in sort_properties(entity.properties, entity.keys):
            row = format_property_table_row(
                prop, keys=entity.keys, accent_color=ac,
            )
            prop_table.add_filtered_row(*row)

    @on(FilterableDataTable.RowSelected)
    def _on_row_selected(self, event: FilterableDataTable.RowSelected) -> None:
        """Open record-view modal when a row is selected."""
        table_id = f"prop-table-{self._entity.name}"
        if event.data_table.id != table_id:
            return
        from rich.text import Text

        row_data = event.data_table.get_row(event.row_key)
        # Strip Rich markup from the property name (key fields have color tags).
        raw_name = str(row_data[0])
        if raw_name.startswith("["):
            raw_name = Text.from_markup(raw_name).plain
        # Pair column labels with row values, converting checkmarks to Yes/No.
        fields = []
        for label, val in zip(self._COLUMN_LABELS, row_data):
            s = str(val)
            if s.startswith("["):
                s = Text.from_markup(s).plain
            if s == "\u2713":
                s = "Yes"
            elif s == "" and label not in ("Length", "Label", "Picklist"):
                s = "No"
            fields.append((label, s))
        self.app.push_screen(RecordViewModal(raw_name, fields))

    def apply_filter(self, term: str) -> tuple[int, int]:
        """Delegate filter to the FilterableDataTable.

        Args:
            term: The filter string (lowercase).

        Returns:
            Tuple of (matched_count, total_count).
        """
        try:
            prop_table = self.query_one(f"#prop-table-{self._entity.name}", FilterableDataTable)
        except Exception:
            return (0, 0)
        return prop_table.apply_filter(term)
