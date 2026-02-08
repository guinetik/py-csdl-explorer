"""
Textual-based TUI for CSDL Metadata Explorer.

A full terminal application with tree navigation, search, and Postman-style
entity tabs.  Requires: pip install csdl-explore[tui]
"""

import re
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Static, Input, TabbedContent, TabPane, DataTable,
)
from textual import events, on

from .explorer import CSDLExplorer
from .formatters import format_search_result_row
from .sap_client import SAPConnection, load_env_file
from .themes import ALL_THEMES, THEME_NAMES
from .widgets import EntityTree, EntityTabPane, PicklistTabPane, SearchResults, FilterBar

MAX_TABS = 15


def _sanitize_id(name: str) -> str:
    """Sanitize name for widget ID."""
    return re.sub(r'-+', '-', re.sub(r'[^a-zA-Z0-9_-]', '-', name)).strip('-')


class CSDLExplorerApp(App):
    """Main CSDL Metadata Explorer application.

    A split-pane TUI with an entity tree on the left and Postman-style
    entity tabs on the right.  Supports theming via ``ctrl+t``.
    """

    CSS = """
    Screen {
        padding: 0;
        margin: 0;
    }

    #app-grid {
        layout: horizontal;
        height: 1fr;
        width: 100%;
        margin: 0;
        padding: 0;
    }

    #sidebar {
        width: 32;
        min-width: 25;
        max-width: 50;
        height: 100%;
        padding: 0;
        margin: 0;
        border-right: solid $primary;
    }

    #main {
        width: 1fr;
        height: 100%;
    }

    #search-box {
        dock: top;
        height: auto;
        width: 100%;
        border: none;
    }

    #search-box:focus {
        border: solid $primary;
    }

    #search-box:focus-within {
        border: solid $primary;
    }

    #entity-tree {
        height: 1fr;
    }

    #search-results {
        height: 1fr;
        display: none;
    }

    #search-results.visible {
        display: block;
    }

    #stats {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }

    #welcome {
        width: 100%;
        height: 100%;
        padding: 2 4;
    }

    TabbedContent {
        height: 1fr;
    }

    #filter-bar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
        display: none;
    }

    #filter-bar.visible {
        display: block;
    }

    /* Sleek thin scrollbars */
    * {
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
        scrollbar-color: $surface;
        scrollbar-color-hover: $primary 30%;
        scrollbar-color-active: $primary;
    }

    Input {
        scrollbar-size-horizontal: 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "clear_search", "Clear"),
        Binding("t", "toggle_tree", "Toggle Tree"),
        Binding("ctrl+t", "cycle_theme", "Theme"),
        Binding("ctrl+w", "close_tab", "Close Tab"),
        Binding("?", "show_help", "Help"),
    ]

    def __init__(self, explorer: CSDLExplorer, **kwargs):
        """Initialise the application.

        Args:
            explorer: The CSDL explorer instance to visualise.
            **kwargs: Extra keyword arguments forwarded to ``App``.
        """
        super().__init__(**kwargs)
        self.explorer = explorer
        self.title = "CSDL Explorer"
        self.sub_title = f"{explorer.entity_count} entities"
        self._table_filter: str = ""

        # SAP connection state
        self.metadata_path: Optional[Path] = explorer.metadata_path
        self.sap_connection: Optional[SAPConnection] = None
        self._load_env()

        for theme in ALL_THEMES:
            self.register_theme(theme)
        self.theme = "terminal-vercel-green"

    def _load_env(self) -> None:
        """Load SAP connection from .env file alongside metadata, if it exists."""
        if not self.metadata_path:
            return
        env_path = self.metadata_path.parent / f"{self.metadata_path.stem}.env"
        if env_path.exists():
            try:
                env_dict = load_env_file(env_path)
                self.sap_connection = SAPConnection.from_env_dict(env_dict)
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="app-grid"):
            with Vertical(id="sidebar"):
                yield Input(placeholder="Filter Metadata Entities", id="search-box")
                yield EntityTree(self.explorer, id="entity-tree")
                yield SearchResults(id="search-results")
                yield Static(
                    f"[dim]{self.explorer.entity_count} entities[/]",
                    id="stats",
                )

            with Vertical(id="main"):
                with TabbedContent(id="tabs"):
                    with TabPane("Welcome", id="welcome-tab"):
                        yield Static(
                            "[dim]Select an entity from the tree to open it in a tab.\n\n"
                            "Search with [bold]/[/] — Toggle tree with [bold]t[/] — "
                            "Close tab with [bold]Ctrl+W[/]\n\n"
                            "Multiple entities can be open simultaneously.[/]",
                            id="welcome",
                        )
                yield FilterBar(id="filter-bar")

        yield Footer()

    # ── Tree selection → open entity tab ─────────────────────────

    @on(EntityTree.NodeSelected)
    def on_tree_node_selected(self, event) -> None:
        """Handle tree node selection — open entity or picklist in a tab."""
        if not event.node.data:
            return
        if event.node.data.get("type") == "entity":
            self._open_entity_tab(event.node.data["name"])
        elif event.node.data.get("type") == "picklist":
            self._open_picklist_tab(event.node.data["name"], event.node.data["entities"])

    # ── Search result selection → open entity tab ────────────────

    @on(SearchResults.EntitySelected)
    def on_search_entity_selected(self, event: SearchResults.EntitySelected) -> None:
        """Handle search result selection — open entity in a tab."""
        self._open_entity_tab(event.entity_name)

    # ── Tab management ───────────────────────────────────────────

    def _open_entity_tab(self, name: str) -> None:
        """Open an entity in a new tab, or focus its existing tab.

        Args:
            name: Name of the entity to open.
        """
        entity = self.explorer.get_entity(name)
        if not entity:
            return

        tabs = self.query_one("#tabs", TabbedContent)
        pane_id = f"entity-{name}"

        # If already open, just focus it
        try:
            tabs.query_one(f"#{pane_id}", TabPane)
            tabs.active = pane_id
            self.sub_title = name
            return
        except Exception:
            pass

        # Remove welcome tab if present
        try:
            welcome = tabs.query_one("#welcome-tab", TabPane)
            tabs.remove_pane("welcome-tab")
        except Exception:
            pass

        # Cap at MAX_TABS (count both entity + picklist panes)
        entity_count = len(tabs.query(EntityTabPane))
        picklist_count = len(tabs.query(PicklistTabPane))
        if entity_count + picklist_count >= MAX_TABS:
            self.notify(f"Max {MAX_TABS} tabs open. Close a tab first.", severity="warning")
            return

        # Create and add new entity pane
        pane = EntityTabPane(entity, self.explorer)
        tabs.add_pane(pane)
        tabs.active = pane_id
        self.sub_title = name

    def _open_picklist_tab(self, name: str, entity_names: list[str]) -> None:
        """Open a picklist in a new tab, or focus its existing tab.

        Args:
            name: Name of the picklist.
            entity_names: Entity names that reference this picklist.
        """
        tabs = self.query_one("#tabs", TabbedContent)
        pane_id = f"picklist-{_sanitize_id(name)}"

        # If already open, just focus it
        try:
            tabs.query_one(f"#{pane_id}", TabPane)
            tabs.active = pane_id
            self.sub_title = f"Picklist: {name}"
            return
        except Exception:
            pass

        # Remove welcome tab if present
        try:
            tabs.query_one("#welcome-tab", TabPane)
            tabs.remove_pane("welcome-tab")
        except Exception:
            pass

        # Cap at MAX_TABS (count both entity + picklist panes)
        entity_count = len(tabs.query(EntityTabPane))
        picklist_count = len(tabs.query(PicklistTabPane))
        if entity_count + picklist_count >= MAX_TABS:
            self.notify(f"Max {MAX_TABS} tabs open. Close a tab first.", severity="warning")
            return

        # Collect picklist data: entity_name → [Property, ...]
        picklist_data: dict[str, list] = {}
        for entity_name in entity_names:
            entity = self.explorer.get_entity(entity_name)
            if not entity:
                continue
            matching = [p for p in entity.properties.values() if p.picklist == name]
            if matching:
                picklist_data[entity_name] = matching

        pane = PicklistTabPane(name, picklist_data, self.explorer)
        tabs.add_pane(pane)
        tabs.active = pane_id
        self.sub_title = f"Picklist: {name}"

    @on(PicklistTabPane.EntitySelected)
    def on_picklist_entity_selected(self, event: PicklistTabPane.EntitySelected) -> None:
        """Handle entity selection from a picklist pane — open entity tab."""
        self._open_entity_tab(event.entity_name)

    def action_close_tab(self) -> None:
        """Close the active entity tab."""
        tabs = self.query_one("#tabs", TabbedContent)
        active = tabs.active
        if not active or active == "welcome-tab":
            return

        tabs.remove_pane(active)
        self._table_filter = ""
        self.query_one("#filter-bar", FilterBar).hide()

        # If no tabs left, show welcome
        remaining = tabs.query(TabPane)
        if not remaining:
            welcome_pane = TabPane("Welcome", Static(
                "[dim]Select an entity from the tree to open it in a tab.[/]",
                id="welcome",
            ), id="welcome-tab")
            tabs.add_pane(welcome_pane)
            tabs.active = "welcome-tab"
            self.sub_title = f"{self.explorer.entity_count} entities"

    @on(TabbedContent.TabActivated, "#tabs")
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Update subtitle and filter bar when switching tabs."""
        pane = event.pane
        if isinstance(pane, EntityTabPane):
            self.sub_title = pane.entity.name
            self._table_filter = pane._table_filter
            bar = self.query_one("#filter-bar", FilterBar)
            if self._table_filter:
                bar.show_filter(self._table_filter)
            else:
                bar.hide()
        elif isinstance(pane, PicklistTabPane):
            self.sub_title = f"Picklist: {pane.picklist_name}"
            self.query_one("#filter-bar", FilterBar).hide()
        elif pane.id == "welcome-tab":
            self.sub_title = f"{self.explorer.entity_count} entities"
            self.query_one("#filter-bar", FilterBar).hide()

    # ── Search ───────────────────────────────────────────────────

    @on(Input.Submitted, "#search-box")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        """Handle search submission (Enter key)."""
        term = event.value.strip()
        self._filter_tree(term)

    @on(Input.Changed, "#search-box")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Live search as user types."""
        term = event.value.strip()
        self._filter_tree(term)

    def _filter_tree(self, term: str) -> None:
        """Filter the entity tree based on search term.

        Args:
            term: The search query string.
        """
        tree = self.query_one("#entity-tree", EntityTree)
        count = tree.filter_tree(term)

        if term:
            self.sub_title = f"Filter: {term} ({count} matches)"
        else:
            self.sub_title = f"{self.explorer.entity_count} entities"

    def action_clear_search(self) -> None:
        """Clear search and return to tree."""
        # If there's an active table filter, clear that first
        if self._table_filter:
            self._table_filter = ""
            tabs = self.query_one("#tabs", TabbedContent)
            active = tabs.active
            if active and active != "welcome-tab":
                try:
                    pane = tabs.query_one(f"#{active}", EntityTabPane)
                    pane.apply_filter("")
                except Exception:
                    pass
            self.query_one("#filter-bar", FilterBar).hide()
            return

        search_box = self.query_one("#search-box", Input)
        search_box.value = ""

        # Clear tree filter
        self._filter_tree("")

        # Focus tree
        tree = self.query_one("#entity-tree", EntityTree)
        tree.focus()

    # ── Table filtering (fzf-style) ─────────────────────────────

    def on_key(self, event: events.Key) -> None:
        """Capture keystrokes for table filtering when a FilterableDataTable has focus."""
        from .widgets import FilterableDataTable

        focused = self.focused
        if not isinstance(focused, FilterableDataTable):
            return

        # Get the current tab name for subtitle
        tabs = self.query_one("#tabs", TabbedContent)
        active = tabs.active
        if not active or active == "welcome-tab":
            return

        # Determine the context name for subtitle
        context_name = "Filtered"
        try:
            pane = tabs.query_one(f"#{active}", EntityTabPane)
            context_name = pane.entity.name
        except Exception:
            try:
                pane = tabs.query_one(f"#{active}", PicklistTabPane)
                context_name = f"Picklist: {pane.picklist_name}"
            except Exception:
                pass

        if event.character and event.character.isprintable():
            self._table_filter += event.character
            matched, total = focused.apply_filter(self._table_filter.lower())
            self._update_filter_display(context_name, matched, total)
            event.prevent_default()
        elif event.key == "backspace" and self._table_filter:
            self._table_filter = self._table_filter[:-1]
            matched, total = focused.apply_filter(self._table_filter.lower())
            self._update_filter_display(context_name, matched, total)
            event.prevent_default()
        elif event.key == "escape" and self._table_filter:
            self._table_filter = ""
            focused.apply_filter("")
            self.query_one("#filter-bar", FilterBar).hide()
            self.sub_title = context_name
            event.prevent_default()

    def _update_filter_display(self, context_name: str, matched: int, total: int) -> None:
        """Update the filter bar and subtitle after filtering."""
        bar = self.query_one("#filter-bar", FilterBar)
        if self._table_filter:
            bar.show_filter(self._table_filter)
            self.sub_title = f"{context_name} | filter: {self._table_filter} ({matched}/{total})"
        else:
            bar.hide()
            self.sub_title = context_name

    # ── Actions ──────────────────────────────────────────────────

    def action_focus_search(self) -> None:
        """Focus the search box."""
        self.query_one("#search-box", Input).focus()

    def action_toggle_tree(self) -> None:
        """Toggle sidebar visibility."""
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display

    def action_cycle_theme(self) -> None:
        """Cycle through registered themes."""
        current = self.theme
        try:
            idx = THEME_NAMES.index(current)
        except ValueError:
            idx = -1
        next_theme = THEME_NAMES[(idx + 1) % len(THEME_NAMES)]
        self.theme = next_theme
        self.notify(f"Theme: {next_theme}", timeout=2)

    def action_show_help(self) -> None:
        """Show help notification."""
        self.notify(
            "/ = Search | Enter = select | t = Toggle tree | "
            "Ctrl+T = Theme | Ctrl+W = Close tab | Esc = Clear | q = Quit",
            title="Keyboard shortcuts",
            timeout=5,
        )


def run_app(explorer: CSDLExplorer):
    """Run the Textual TUI application."""
    app = CSDLExplorerApp(explorer)
    app.run()
