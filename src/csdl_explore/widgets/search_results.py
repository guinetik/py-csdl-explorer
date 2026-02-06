"""Search results DataTable for the sidebar."""

from textual.widgets import DataTable
from textual.message import Message


class SearchResults(DataTable):
    """DataTable showing search results in the sidebar.

    Posts a ``SearchResults.EntitySelected`` message when a row is selected.
    """

    class EntitySelected(Message):
        """Posted when a search result row is selected.

        Args:
            entity_name: Name of the selected entity.
        """

        def __init__(self, entity_name: str) -> None:
            super().__init__()
            self.entity_name = entity_name

    def __init__(self, **kwargs):
        super().__init__(cursor_type="row", **kwargs)

    def on_mount(self) -> None:
        """Set up search result columns."""
        self.add_column("Type", width=8, key="type")
        self.add_column("Entity", width=25, key="entity")
        self.add_column("Match", width=25, key="match")
        self.add_column("Details", width=25, key="details")
        self.add_column("Picklist", width=18, key="picklist")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """When a row is selected, post an EntitySelected message."""
        event.stop()
        row = self.get_row(event.row_key)
        if row and len(row) >= 2:
            entity_name = str(row[1])
            if entity_name:
                self.post_message(self.EntitySelected(entity_name))
