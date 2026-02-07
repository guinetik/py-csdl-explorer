"""Query sub-tab — composes ConnectionPanel, QueryBuilder, and ResultsViewer."""

from textual.containers import VerticalScroll
from textual.widgets import Static, TabPane, Input, Collapsible
from textual import on, work

from ..parser import EntityType
from .connection_panel import ConnectionPanel
from .query_builder import QueryBuilder
from .results_viewer import ResultsViewer


class QueryTab(TabPane):
    """Query sub-tab combining auth, query builder, and results viewer.

    Args:
        entity: The entity type to query.
        tab_id: Unique tab pane ID.
    """

    DEFAULT_CSS = """
    QueryTab .q-builder-scroll {
        height: 1fr;
    }

    QueryTab Collapsible > Contents {
        padding: 1 0 0 0;
    }
    """

    def __init__(self, entity: EntityType, tab_id: str) -> None:
        super().__init__("Query", id=tab_id)
        self._entity = entity

    def compose(self):
        eid = self._entity.name
        with VerticalScroll(classes="q-builder-scroll"):
            yield ConnectionPanel(panel_id=eid)
            yield QueryBuilder(self._entity, builder_id=eid)
            with Collapsible(title="Results", id=f"q-results-section-{eid}", collapsed=False):
                yield ResultsViewer(viewer_id=f"query-{eid}")

    def on_mount(self) -> None:
        """Update URL preview with initial base URL."""
        cp = self.query_one(ConnectionPanel)
        qb = self.query_one(QueryBuilder)
        qb.update_url_preview(cp.base_url)

    @on(ConnectionPanel.ConnectionChanged)
    def _on_connection_changed(self, event: ConnectionPanel.ConnectionChanged) -> None:
        """Update URL preview when connection changes."""
        qb = self.query_one(QueryBuilder)
        qb.update_url_preview(event.connection.base_url)

    @on(Input.Changed, "ConnectionPanel Input")
    def _on_base_url_changed(self, event: Input.Changed) -> None:
        """Update URL preview when base URL input changes."""
        cp = self.query_one(ConnectionPanel)
        qb = self.query_one(QueryBuilder)
        qb.update_url_preview(cp.base_url)

    @on(QueryBuilder.RunRequested)
    def _on_run_requested(self, event: QueryBuilder.RunRequested) -> None:
        """Execute the OData query."""
        self._run_query()

    @on(QueryBuilder.CopyRequested)
    def _on_copy_requested(self, event: QueryBuilder.CopyRequested) -> None:
        """Copy URL to clipboard."""
        self.app.copy_to_clipboard(event.url)
        self.app.notify("URL copied to clipboard", timeout=2)

    @work(thread=False)
    async def _run_query(self) -> None:
        """Build connection, authenticate, execute query, display results."""
        cp = self.query_one(ConnectionPanel)
        qb = self.query_one(QueryBuilder)
        viewer = self.query_one(ResultsViewer)
        eid = self._entity.name

        if not cp.base_url:
            self.app.notify("Enter a Base URL first", severity="warning")
            return

        conn = cp.build_connection()
        self.app.sap_connection = conn
        self.app.notify("Sending query…", timeout=2)

        try:
            from ..sap_client import SAPClient

            client = SAPClient(conn)
            await client.authenticate()

            params = qb.get_query_params()
            results, full_url, raw_text, content_type = await client.query_entity(eid, params)
            await client.close()

            qb.set_url_preview(full_url)
            viewer.update_results(results, full_url, raw_text, content_type, eid)

            if not results:
                self.app.notify("Query returned no results", severity="warning", timeout=3)
            else:
                columns = [k for k in results[0].keys() if k != "__metadata"]
                self.app.notify(f"{len(results)} results, {len(columns)} columns", timeout=3)

        except Exception as e:
            vid = viewer._viewer_id
            status = viewer.query_one(f"#rv-status-{vid}", Static)
            status.update(f"[red]Error: {e}[/]")
            self.app.notify(f"Query failed: {e}", severity="error", timeout=5)
