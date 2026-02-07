"""Picklist Entities sub-tab — DataTable of entities using this picklist."""

from textual.widgets import DataTable, TabPane
from textual.message import Message
from textual import on

from ..parser import Property
from ..formatters import format_flag_check


class PicklistEntitiesTab(TabPane):
    """Entities sub-tab listing all entities and properties using a picklist.

    Args:
        picklist_name: The picklist name.
        picklist_data: Mapping of entity name to properties using this picklist.
        tab_id: Unique tab pane ID.
    """

    class EntitySelected(Message):
        """Posted when a user selects an entity row."""

        def __init__(self, entity_name: str) -> None:
            super().__init__()
            self.entity_name = entity_name

    def __init__(
        self, picklist_name: str, picklist_data: dict[str, list[Property]], tab_id: str,
    ) -> None:
        super().__init__("Entities", id=tab_id)
        self._picklist_name = picklist_name
        self._picklist_data = picklist_data
        self._entity_rows: list[str] = []

    def compose(self):
        yield DataTable(
            id=f"pick-entity-table-{self._picklist_name}",
            zebra_stripes=True,
            cursor_type="row",
        )

    def on_mount(self) -> None:
        """Populate the entities table."""
        self._setup_table()

    def _setup_table(self) -> None:
        """Add columns and rows."""
        table = self.query_one(f"#pick-entity-table-{self._picklist_name}", DataTable)
        table.add_column("Entity", width=25, key="entity")
        table.add_column("Property", width=20, key="property")
        table.add_column("Type", width=15, key="type")
        table.add_column("Label", width=20, key="label")
        table.add_column("Req", width=3, key="req")
        table.add_column("C", width=3, key="create")
        table.add_column("U", width=3, key="update")

        self._entity_rows = []
        for entity_name in sorted(self._picklist_data):
            for prop in self._picklist_data[entity_name]:
                table.add_row(
                    entity_name, prop.name, prop.type, prop.label or "",
                    format_flag_check(prop.required),
                    format_flag_check(prop.creatable),
                    format_flag_check(prop.updatable),
                )
                self._entity_rows.append(entity_name)

    @on(DataTable.RowSelected)
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Post EntitySelected when a row is clicked."""
        table_id = f"pick-entity-table-{self._picklist_name}"
        if event.data_table.id != table_id:
            return
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._entity_rows):
            self.post_message(self.EntitySelected(self._entity_rows[row_idx]))
