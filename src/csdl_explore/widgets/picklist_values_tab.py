"""Picklist Get Values sub-tab — fetch and display picklist values via OData."""

import re
from textual.containers import Horizontal
from textual.widgets import Static, TabPane, Button, Collapsible
from textual import on, work

from .connection_panel import ConnectionPanel
from .filterable_table import FilterableDataTable


def _sanitize_id(name: str) -> str:
    """Sanitize name for widget ID."""
    return re.sub(r'-+', '-', re.sub(r'[^a-zA-Z0-9_-]', '-', name)).strip('-')


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
        padding: 0;
        layout: horizontal;
    }

    PicklistValuesTab .getval-bar > Button {
        margin: 0 1 0 0;
    }

    PicklistValuesTab .getval-spacer {
        width: 1fr;
    }

    PicklistValuesTab .getval-actions {
        height: auto;
        width: auto;
        layout: horizontal;
        display: none;
    }

    PicklistValuesTab .getval-actions.-visible {
        display: block;
    }

    PicklistValuesTab .getval-actions Button {
        margin: 0 0 0 1;
    }
    """

    def __init__(self, picklist_name: str, tab_id: str) -> None:
        super().__init__("Get Values", id=tab_id)
        self._picklist_name = picklist_name
        self._raw_json = ""  # Store raw JSON for copy/save

    def compose(self):
        pid = _sanitize_id(self._picklist_name)
        with Collapsible(title="Auth", id=f"cp-section-pv-{pid}"):
            yield ConnectionPanel(panel_id=f"pv-{pid}")
        with Horizontal(classes="getval-bar"):
            yield Button(
                "Fetch Values",
                id=f"btn-fetch-{pid}",
                variant="success",
            )
            yield Static("", classes="getval-spacer")
            with Horizontal(classes="getval-actions"):
                yield Button(
                    "\uf0c5",
                    id=f"btn-copy-{pid}",
                    variant="default",
                )
                yield Button(
                    "\U000f0193",
                    id=f"btn-save-{pid}",
                    variant="default",
                )
        yield Static(
            "[dim]Not connected[/]",
            id=f"pick-getval-status-{pid}",
            classes="getval-status",
        )
        yield FilterableDataTable(
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
        status = self.query_one(f"#pick-getval-status-{_sanitize_id(self._picklist_name)}", Static)
        conn = getattr(self.app, "sap_connection", None)
        if conn and conn.base_url:
            status.update(f"Connected to [bold]{conn.base_url}[/]")
        else:
            status.update("[dim]Not connected[/]")

    @on(Button.Pressed)
    def _on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Fetch Values, Copy, and Save buttons."""
        pid = _sanitize_id(self._picklist_name)
        btn_id = event.button.id or ""
        if btn_id == f"btn-fetch-{pid}":
            self._fetch_values()
        elif btn_id == f"btn-copy-{pid}" and self._raw_json:
            self.app.copy_to_clipboard(self._raw_json)
            self.app.notify("Picklist values copied to clipboard", timeout=2)
        elif btn_id == f"btn-save-{pid}" and self._raw_json:
            self._save_response()

    @work(thread=False)
    async def _fetch_values(self) -> None:
        """Fetch picklist values from the OData API."""
        import json

        pid = _sanitize_id(self._picklist_name)
        cp = self.query_one(ConnectionPanel)

        if not cp.base_url:
            self.app.notify("Enter a Base URL first", severity="warning")
            return

        conn = cp.build_connection()
        cp.save_connection(conn)

        status = self.query_one(f"#pick-getval-status-{pid}", Static)
        table = self.query_one(f"#pick-getval-table-{pid}", FilterableDataTable)
        actions = self.query_one(".getval-actions", Horizontal)

        status.update("[dim]Fetching...[/]")

        try:
            from ..sap_client import SAPClient

            client = SAPClient(conn)
            await client.authenticate()
            results = await client.get_picklist_values(self._picklist_name)
            await client.close()

            # Store raw JSON for copy/save
            self._raw_json = json.dumps(results, indent=2)

            table.clear_filtered_rows()
            table.clear(columns=True)

            if not results:
                status.update(f"Connected to [bold]{conn.base_url}[/] — no values found")
                actions.remove_class("-visible")
                return

            locales = sorted({loc for item in results for loc in item["labels"]})
            table.add_column("ID", width=8, key="id")
            table.add_column("Code", width=10, key="code")
            for loc in locales:
                table.add_column(loc, width=18, key=f"label-{loc}")

            for item in results:
                table.add_filtered_row(
                    item["id"],
                    item["externalCode"],
                    *[item["labels"].get(loc, "") for loc in locales],
                )

            status.update(
                f"Connected to [bold]{conn.base_url}[/] — "
                f"[bold]{len(results)}[/] values, [bold]{len(locales)}[/] locales"
            )

            # Show copy/save buttons
            actions.add_class("-visible")

        except Exception as e:
            status.update(f"[red]Error: {e}[/]")
            actions.remove_class("-visible")

    def _save_response(self) -> None:
        """Save picklist values JSON to file."""
        from datetime import datetime
        from pathlib import Path

        if not self._raw_json:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"picklist_{self._picklist_name}_{timestamp}.json"
        filepath = Path.cwd() / filename

        try:
            filepath.write_text(self._raw_json, encoding="utf-8")
            self.app.notify(f"Saved to {filepath.name}", timeout=3)
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")
