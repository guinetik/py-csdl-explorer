"""Results viewer widget — table, raw, and tree views of OData query responses."""

import json

from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, DataTable, TabbedContent, TabPane, Button, TextArea
from textual.widget import Widget
from textual.message import Message
from textual import on

from rich.tree import Tree as RichTree

from ..formatters import detect_syntax_lexer, detect_file_extension, build_tree_structure, format_odata_value
from .json_viewer_modal import JsonViewerModal


class ResultsViewer(Widget):
    """Multi-format results viewer with Table, Raw, and Tree tabs.

    Args:
        viewer_id: Unique identifier used to namespace child widget IDs.
    """

    DEFAULT_CSS = """
    ResultsViewer {
        height: 1fr;
        min-height: 10;
    }

    .rv-header {
        height: 3;
        padding: 0 1;
    }

    .rv-status {
        width: 1fr;
        height: 3;
        content-align-vertical: middle;
    }

    .rv-actions {
        width: auto;
        height: auto;
        dock: right;
        display: none;
        margin: 1 1 0 0;
    }

    .rv-actions.-visible {
        display: block;
    }

    .rv-actions Button {
        min-width: 5;
        height: 3;
        padding: 0 1;
    }

    ResultsViewer TabbedContent {
        height: 1fr;
        overflow: auto;
    }

    ResultsViewer TabPane {
        height: 1fr;
        overflow: auto;
    }

    ResultsViewer DataTable {
        height: 1fr;
        width: auto;
        scrollbar-size-horizontal: 2;
    }

    ResultsViewer TextArea {
        height: 1fr;
    }
    """

    class SaveRequested(Message):
        """Posted when the user clicks Save Response.

        Attributes:
            content: Raw response text to save.
            extension: File extension (``"json"`` or ``"xml"``).
            entity_name: Entity set name for the filename.
        """

        def __init__(self, content: str, extension: str, entity_name: str) -> None:
            super().__init__()
            self.content = content
            self.extension = extension
            self.entity_name = entity_name

    def __init__(self, viewer_id: str) -> None:
        super().__init__()
        self._viewer_id = viewer_id
        self._raw_text: str = ""
        self._content_type: str = "application/json"
        self._entity_name: str = ""
        self._results: list[dict] = []  # Store results for row detail view

    def compose(self):
        vid = self._viewer_id
        with Horizontal(classes="rv-header"):
            yield Static("[dim]Not connected[/]", id=f"rv-status-{vid}", classes="rv-status")
            with Horizontal(classes="rv-actions"):
                yield Button(
                    "\uf0c5",
                    id=f"rv-btn-copy-{vid}",
                    variant="default",
                )
                yield Button(
                    "\U000f0193",
                    id=f"rv-btn-save-{vid}",
                    variant="default",
                )
        with TabbedContent(id=f"rv-tabs-{vid}"):
            with TabPane("Table", id=f"rv-tab-table-{vid}"):
                yield DataTable(
                    id=f"rv-table-{vid}",
                    zebra_stripes=True,
                    cursor_type="row",
                )
            with TabPane("Raw", id=f"rv-tab-raw-{vid}"):
                yield TextArea(
                    "",
                    id=f"rv-raw-{vid}",
                    read_only=True,
                    show_line_numbers=True,
                )
            with TabPane("Tree", id=f"rv-tab-tree-{vid}"):
                with VerticalScroll(id=f"rv-tree-scroll-{vid}"):
                    yield Static(id=f"rv-tree-{vid}")

    def update_results(
        self,
        results: list[dict],
        url: str,
        raw_text: str,
        content_type: str,
        entity_name: str,
    ) -> None:
        """Populate all three tabs with query results.

        Args:
            results: Parsed result dicts from OData response.
            url: Full request URL.
            raw_text: Raw response body text.
            content_type: HTTP Content-Type header value.
            entity_name: Entity set name (for save filename).
        """
        vid = self._viewer_id
        # Store pretty-printed version for save/copy
        if "json" in content_type.lower():
            try:
                self._raw_text = json.dumps(json.loads(raw_text), indent=2)
            except (json.JSONDecodeError, ValueError):
                self._raw_text = raw_text
        else:
            self._raw_text = raw_text
        self._content_type = content_type
        self._entity_name = entity_name
        self._results = results  # Store for row detail view

        status = self.query_one(f"#rv-status-{vid}", Static)
        actions = self.query_one(".rv-actions", Horizontal)

        if not results:
            status.update(f"0 results — {url}")
            self._clear_tabs()
            return

        actions.add_class("-visible")
        columns = [k for k in results[0].keys() if k != "__metadata"]
        status.update(
            f"[bold]{len(results)}[/] results, "
            f"[bold]{len(columns)}[/] columns — {url}"
        )

        # ── Table tab ────────────────────────────────────────
        table = self.query_one(f"#rv-table-{vid}", DataTable)
        table.clear(columns=True)
        # Compute column widths from header + data so table overflows horizontally
        formatted_rows = []
        for row in results:
            formatted_rows.append([format_odata_value(str(row.get(col, ""))) for col in columns])
        for i, col in enumerate(columns):
            max_val = max((len(r[i]) for r in formatted_rows), default=0)
            width = max(len(col), min(max_val, 40)) + 2
            table.add_column(col, key=col, width=width)
        for row in formatted_rows:
            table.add_row(*row)

        # ── Raw tab ──────────────────────────────────────────
        lexer = detect_syntax_lexer(content_type)
        raw_area = self.query_one(f"#rv-raw-{vid}", TextArea)
        # Set language before loading text for proper syntax highlighting
        if lexer and lexer != "text":
            raw_area.language = lexer
        raw_area.load_text(self._raw_text)

        # ── Tree tab ─────────────────────────────────────────
        tree_data = build_tree_structure(results)
        rich_tree = RichTree(f"[bold #00dc82]{entity_name}[/] [dim]({len(results)} results)[/]")
        self._populate_rich_tree(rich_tree, tree_data)
        tree_widget = self.query_one(f"#rv-tree-{vid}", Static)
        tree_widget.update(rich_tree)

    def _clear_tabs(self) -> None:
        """Reset all tab contents to empty state."""
        vid = self._viewer_id
        table = self.query_one(f"#rv-table-{vid}", DataTable)
        table.clear(columns=True)
        self.query_one(f"#rv-raw-{vid}", TextArea).load_text("")
        self.query_one(f"#rv-tree-{vid}", Static).update("")

    def _populate_rich_tree(self, parent, nodes: list[tuple[str, str, list]]) -> None:
        """Recursively add nodes to a Rich Tree.

        Args:
            parent: Rich Tree or branch to add children to.
            nodes: List of ``(label, type_hint, children)`` tuples.
        """
        for label, type_hint, children in nodes:
            if children:
                hint = f" [dim]{type_hint}[/]" if type_hint else ""
                branch = parent.add(f"[#00dc82]{label}[/]{hint}")
                self._populate_rich_tree(branch, children)
            else:
                hint = f" [dim]{type_hint}[/]" if type_hint else ""
                parent.add(f"[#00dc82]{label}[/]{hint}")

    @on(Button.Pressed)
    def _on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Save and Copy button clicks."""
        vid = self._viewer_id
        btn_id = event.button.id or ""
        if btn_id == f"rv-btn-save-{vid}" and self._raw_text:
            ext = detect_file_extension(self._content_type)
            self.post_message(
                self.SaveRequested(self._raw_text, ext, self._entity_name)
            )
        elif btn_id == f"rv-btn-copy-{vid}" and self._raw_text:
            self.app.copy_to_clipboard(self._raw_text)
            self.app.notify("Response copied to clipboard", timeout=2)

    def _show_row_detail(self, row_index: int) -> None:
        """Show JSON modal for a specific row."""
        if not self._results or row_index < 0 or row_index >= len(self._results):
            return

        row_data = self._results[row_index]
        self.app.push_screen(
            JsonViewerModal(f"{self._entity_name} - Row {row_index + 1}", row_data)
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show JSON modal when a row is selected (Enter key)."""
        if event.data_table.id != f"rv-table-{self._viewer_id}":
            return

        try:
            self._show_row_detail(event.cursor_row)
        except Exception as e:
            self.app.notify(f"Error showing row: {e}", severity="error")

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Show JSON modal when a cell is clicked (double-click)."""
        if event.data_table.id != f"rv-table-{self._viewer_id}":
            return

        try:
            self._show_row_detail(event.cursor_row)
        except Exception as e:
            self.app.notify(f"Error showing row: {e}", severity="error")
