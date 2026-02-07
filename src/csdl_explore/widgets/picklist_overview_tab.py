"""Picklist Overview sub-tab — summary panel and entity/property tree."""

from textual.containers import VerticalScroll
from textual.widgets import Static, TabPane

from rich.console import Group
from rich.panel import Panel
from rich.tree import Tree as RichTree
from rich import box

from ..parser import Property
from ..themes import VERCEL_THEME


class PicklistOverviewTab(TabPane):
    """Overview sub-tab showing picklist summary and usage tree.

    Args:
        picklist_name: The picklist name.
        picklist_data: Mapping of entity name to properties using this picklist.
        tab_id: Unique tab pane ID.
    """

    def __init__(
        self, picklist_name: str, picklist_data: dict[str, list[Property]], tab_id: str,
    ) -> None:
        super().__init__("Overview", id=tab_id)
        self._picklist_name = picklist_name
        self._picklist_data = picklist_data

    def compose(self):
        with VerticalScroll():
            yield Static(id=f"pick-details-{self._picklist_name}")

    def on_mount(self) -> None:
        """Render overview content."""
        self._render()

    def _render(self) -> None:
        """Populate panel and Rich tree."""
        wc = VERCEL_THEME.warning
        pc = VERCEL_THEME.primary

        entity_count = len(self._picklist_data)
        prop_count = sum(len(props) for props in self._picklist_data.values())

        header_text = f"[bold {wc}]{self._picklist_name}[/]"
        panel = Panel(header_text, title="Picklist", box=box.ROUNDED)

        summary = f"  Used by [bold]{entity_count}[/] entities across [bold]{prop_count}[/] properties\n"

        rtree = RichTree(f"[bold {wc}]{self._picklist_name}[/]")
        for entity_name in sorted(self._picklist_data):
            branch = rtree.add(f"[{pc}]{entity_name}[/]")
            for prop in self._picklist_data[entity_name]:
                label_hint = f' "{prop.label}"' if prop.label else ""
                branch.add(f"{prop.name} [dim]{prop.type}{label_hint}[/]")

        widget = self.query_one(f"#pick-details-{self._picklist_name}", Static)
        widget.update(Group(panel, summary, rtree))
