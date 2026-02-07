"""Results viewer widget — table, raw, and tree views of OData query responses."""

import json

from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, DataTable, TabbedContent, TabPane, Button
from textual.widget import Widget
from textual.message import Message
from textual import on

from rich.syntax import Syntax
from rich.tree import Tree as RichTree

from ..formatters import detect_syntax_lexer, detect_file_extension, build_tree_structure

# Map Textual theme names to Rich Syntax themes.
_SYNTAX_THEMES: dict[str, str] = {
    "terminal-vercel-green": "github-dark",
    "classic": "dracula",
}
_DEFAULT_SYNTAX_THEME = "github-dark"


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
    }

    ResultsViewer TabPane {
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
                with VerticalScroll(id=f"rv-raw-scroll-{vid}"):
                    yield Static(id=f"rv-raw-{vid}")
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
        for col in columns:
            table.add_column(col, key=col)
        for row in results:
            table.add_row(*[str(row.get(col, "")) for col in columns])

        # ── Raw tab ──────────────────────────────────────────
        lexer = detect_syntax_lexer(content_type)
        app_theme = getattr(self.app, "theme", None) or ""
        syntax_theme = _SYNTAX_THEMES.get(app_theme, _DEFAULT_SYNTAX_THEME)
        syntax = Syntax(self._raw_text, lexer, theme=syntax_theme, line_numbers=True)
        raw_widget = self.query_one(f"#rv-raw-{vid}", Static)
        raw_widget.update(syntax)

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
        self.query_one(f"#rv-raw-{vid}", Static).update("")
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
