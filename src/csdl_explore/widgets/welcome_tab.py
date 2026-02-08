"""Welcome tab pane with stats and navigation graph."""

from textual.widgets import TabPane, Static, TabbedContent
from textual.containers import Vertical

from ..explorer import CSDLExplorer
from .nav_graph import NavigationGraph


class WelcomeTabPane(TabPane):
    """Welcome screen tab showing metadata stats and navigation graph.

    Args:
        explorer: The CSDL explorer instance.
    """

    DEFAULT_CSS = """
    WelcomeTabPane #welcome-subtabs > Tabs {
        display: none;
    }

    WelcomeTabPane #welcome-stats {
        dock: top;
        height: auto;
        padding: 1 2;
        background: $surface;
    }

    WelcomeTabPane #nav-graph {
        height: 1fr;
    }
    """

    def __init__(self, explorer: CSDLExplorer):
        super().__init__("Welcome", id="welcome-tab")
        self.explorer = explorer

    def on_mount(self) -> None:
        """Set focus to the navigation graph when tab is mounted."""
        # Give focus to the graph so keyboard controls work
        graph = self.query_one("#nav-graph", NavigationGraph)
        graph.focus()

    def compose(self):
        # Calculate stats
        total_props = sum(len(e.properties) for e in self.explorer.entities.values())
        total_custom = sum(
            len([p for p in e.properties.values() if p.name.startswith("custom")])
            for e in self.explorer.entities.values()
        )
        all_picklists = set()
        for entity in self.explorer.entities.values():
            for prop in entity.properties.values():
                if prop.picklist:
                    all_picklists.add(prop.picklist)

        stats_text = (
            f"[bold]Metadata Overview[/]\n\n"
            f"[#00dc82]Entities:[/] {self.explorer.entity_count}\n"
            f"[#00dc82]Properties:[/] {total_props:,}\n"
            f"[#00dc82]Picklists:[/] {len(all_picklists)}\n"
            f"[#00dc82]Custom Fields:[/] {total_custom:,}\n"
        )

        # Use TabbedContent structure like EntityTabPane
        with TabbedContent(id="welcome-subtabs"):
            with TabPane("Overview", id="welcome-overview"):
                yield Static(stats_text, id="welcome-stats")
                yield NavigationGraph(self.explorer, id="nav-graph")
