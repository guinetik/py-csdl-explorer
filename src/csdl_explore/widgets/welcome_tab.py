"""Welcome tab pane with stats and navigation graph."""

from textual.widgets import TabPane, Static

from ..explorer import CSDLExplorer
from .nav_graph import NavigationGraph


class WelcomeTabPane(TabPane):
    """Welcome screen tab showing metadata stats and navigation graph.

    Args:
        explorer: The CSDL explorer instance.
    """

    def __init__(self, explorer: CSDLExplorer):
        super().__init__("Welcome", id="welcome-tab")
        self.explorer = explorer

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

        yield Static(stats_text, id="welcome-stats")
        yield NavigationGraph(self.explorer, id="nav-graph")
