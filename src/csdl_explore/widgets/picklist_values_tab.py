"""Picklist Get Values sub-tab — fetch and display picklist values via OData."""

from textual.containers import Horizontal
from textual.widgets import Static, DataTable, TabPane, Button
from textual import on, work

from .connection_panel import ConnectionPanel


class PicklistValuesTab(TabPane):
    """Get Values sub-tab for fetching picklist values from OData API.

    Args:
        picklist_name: The picklist name.
        tab_id: Unique tab pane ID.
    """

    DEFAULT_CSS = """
    PicklistValuesTab .getval-status {
        padding: 0 1;
        height: auto;
    }

    PicklistValuesTab .getval-bar {
        height: 3;
        padding: 0 1;
        align: left middle;
    }

    PicklistValuesTab .getval-bar Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, picklist_name: str, tab_id: str) -> None:
        super().__init__("Get Values", id=tab_id)
        self._picklist_name = picklist_name

    def compose(self):
        pid = self._picklist_name
        yield ConnectionPanel(panel_id=f"pv-{pid}")
        with Horizontal(classes="getval-bar"):
            yield Button(
                "Fetch Values",
                id=f"btn-fetch-{pid}",
                variant="default",
            )
        yield Static(
            "[dim]Not connected[/]",
            id=f"pick-getval-status-{pid}",
            classes="getval-status",
        )
        yield DataTable(
            id=f"pick-getval-table-{pid}",
            zebra_stripes=True,
            cursor_type="row",
        )

    def on_mount(self) -> None:
        """Update connection status."""
        self._update_status()

    @on(ConnectionPanel.ConnectionChanged)
    def _on_connection_changed(self, event: ConnectionPanel.ConnectionChanged) -> None:
        """Update status when connection is configured."""
        self._update_status()

    def _update_status(self) -> None:
        """Update status label from app.sap_connection."""
        status = self.query_one(f"#pick-getval-status-{self._picklist_name}", Static)
        conn = getattr(self.app, "sap_connection", None)
        if conn and conn.base_url:
            status.update(f"Connected to [bold]{conn.base_url}[/]")
        else:
            status.update("[dim]Not connected[/]")

    @on(Button.Pressed)
    def _on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Fetch Values button."""
        if event.button.id == f"btn-fetch-{self._picklist_name}":
            self._fetch_values()

    @work(thread=False)
    async def _fetch_values(self) -> None:
        """Fetch picklist values from the OData API."""
        pid = self._picklist_name
        cp = self.query_one(ConnectionPanel)

        if not cp.base_url:
            self.app.notify("Enter a Base URL first", severity="warning")
            return

        conn = cp.build_connection()
        cp.save_connection(conn)

        status = self.query_one(f"#pick-getval-status-{pid}", Static)
        table = self.query_one(f"#pick-getval-table-{pid}", DataTable)

        status.update("[dim]Fetching...[/]")

        try:
            from ..sap_client import SAPClient

            client = SAPClient(conn)
            await client.authenticate()
            results = await client.get_picklist_values(self._picklist_name)
            await client.close()

            table.clear(columns=True)

            if not results:
                status.update(f"Connected to [bold]{conn.base_url}[/] — no values found")
                return

            locales = sorted({loc for item in results for loc in item["labels"]})
            table.add_column("ID", width=8, key="id")
            table.add_column("Code", width=10, key="code")
            for loc in locales:
                table.add_column(loc, width=18, key=f"label-{loc}")

            for item in results:
                table.add_row(
                    item["id"],
                    item["externalCode"],
                    *[item["labels"].get(loc, "") for loc in locales],
                )

            status.update(
                f"Connected to [bold]{conn.base_url}[/] — "
                f"[bold]{len(results)}[/] values, [bold]{len(locales)}[/] locales"
            )

        except Exception as e:
            status.update(f"[red]Error: {e}[/]")
