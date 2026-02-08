"""Details sub-tab — entity overview panel with keys, navigation, and custom fields."""

from textual.containers import VerticalScroll
from textual.widgets import Static, TabPane

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree as RichTree
from rich import box

from ..parser import EntityType
from ..formatters import group_entity_properties
from ..themes import VERCEL_THEME


class DetailsTab(TabPane):
    """Details sub-tab showing entity summary, keys, navigation, and custom fields.

    Args:
        entity: The entity type to display.
        tab_id: Unique tab pane ID.
    """

    DEFAULT_CSS = """
    DetailsTab .detail-scroll {
        height: 1fr;
    }

    DetailsTab .detail-scroll > Static {
        height: auto;
    }
    """

    def __init__(self, entity: EntityType, tab_id: str) -> None:
        super().__init__("Details", id=tab_id)
        self._entity = entity

    def compose(self):
        with VerticalScroll(classes="detail-scroll"):
            yield Static(id=f"details-header-{self._entity.name}")
            yield Static(id=f"details-tree-{self._entity.name}")

    def on_mount(self) -> None:
        """Populate details content after mount."""
        self._populate()

    def _populate(self) -> None:
        """Populate header panel and property tree."""
        entity = self._entity
        pc = VERCEL_THEME.primary
        ac = VERCEL_THEME.accent
        sc = VERCEL_THEME.success

        header_widget = self.query_one(f"#details-header-{entity.name}", Static)
        tree_widget = self.query_one(f"#details-tree-{entity.name}", Static)

        header_text = f"[bold {pc}]{entity.name}[/]"
        if entity.base_type:
            header_text += f"\n[dim]Base: {entity.base_type}[/]"
        header_text += f"\n[dim]Keys: {', '.join(entity.keys)}[/]"
        panel = Panel(header_text, title="Entity", box=box.ROUNDED)

        custom_count = len(entity.custom_fields)
        nav_count = len(entity.navigation)

        summary = Text.from_markup(
            f"  [bold]{len(entity.properties)}[/] properties"
            f"  |  [bold]{custom_count}[/] custom fields"
            f"  |  [bold]{nav_count}[/] navigation\n"
        )

        header_widget.update(Group(panel, summary))

        groups = group_entity_properties(entity)
        rtree = RichTree(f"[bold {pc}]{entity.name}[/]")

        if groups["keys"]:
            keys_branch = rtree.add(f"[{ac}]Keys[/]")
            for prop in groups["keys"]:
                keys_branch.add(f"[{pc}]{prop.name}[/] [dim]{prop.type}[/]")

        if groups["standard"]:
            standard_branch = rtree.add(f"[{pc}]Standard Properties[/] ({len(groups['standard'])})")
            for prop in groups["standard"]:
                label_hint = f' [dim]"{prop.label}"[/]' if prop.label else ""
                pick_hint = f' [magenta]{prop.picklist}[/]' if prop.picklist else ""
                standard_branch.add(f"[{pc}]{prop.name}[/] {prop.type}{label_hint}{pick_hint}")

        if groups["lookups"]:
            lookup_branch = rtree.add(f"[{sc}]Lookup Properties[/] ({len(groups['lookups'])})")
            for prop, nav_name, target in groups["lookups"]:
                lookup_branch.add(f"[{pc}]{prop.name}[/] -> [{sc}]{target}[/] [dim]via {nav_name}[/]")

        all_nav = list(entity.navigation.values())
        if all_nav:
            nav_branch = rtree.add(f"[blue]Navigation[/] ({nav_count})")
            for nav in sorted(all_nav, key=lambda n: n.name):
                target = nav.target_entity or "?"
                nav_branch.add(f"[{pc}]{nav.name}[/] -> [{sc}]{target}[/]")

        if groups["custom"]:
            custom_branch = rtree.add(f"[{ac}]Custom Fields[/] ({custom_count})")
            for prop in groups["custom"]:
                label_hint = f' [dim]"{prop.label}"[/]' if prop.label else ""
                pick_hint = f' [magenta]{prop.picklist}[/]' if prop.picklist else ""
                custom_branch.add(f"[{pc}]{prop.name}[/] {prop.type}{label_hint}{pick_hint}")

        tree_widget.update(rtree)
