"""Entity tab pane — shows Details and Properties for a single entity."""

from textual.containers import VerticalScroll
from textual.widgets import Static, DataTable, TabbedContent, TabPane

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree as RichTree
from rich import box

from ..explorer import CSDLExplorer
from ..parser import EntityType
from ..formatters import sort_properties, group_entity_properties, format_flag_check
from ..themes import VERCEL_THEME


class EntityTabPane(TabPane):
    """A tab pane displaying Details and Properties sub-tabs for one entity.

    Args:
        entity: The entity type to display.
        explorer: The CSDL explorer instance.
    """

    def __init__(self, entity: EntityType, explorer: CSDLExplorer):
        pane_id = f"entity-{entity.name}"
        super().__init__(entity.name, id=pane_id)
        self.entity = entity
        self.explorer = explorer
        self._prop_rows: list[tuple] = []
        self._table_filter: str = ""

    def compose(self):
        with TabbedContent(id=f"sub-tabs-{self.entity.name}"):
            with TabPane("Details", id=f"detail-{self.entity.name}"):
                with VerticalScroll():
                    yield Static(id=f"details-{self.entity.name}")
            with TabPane("Properties", id=f"props-{self.entity.name}"):
                yield DataTable(
                    id=f"prop-table-{self.entity.name}",
                    zebra_stripes=True,
                    cursor_type="row",
                )

    def on_mount(self) -> None:
        """Render details and set up property table after mount."""
        self._render_details()
        self._setup_property_table()

    def _render_details(self) -> None:
        """Populate the Details sub-tab with a Rich panel and tree."""
        entity = self.entity
        pc = VERCEL_THEME.primary
        ac = VERCEL_THEME.accent
        sc = VERCEL_THEME.success

        details_widget = self.query_one(f"#details-{entity.name}", Static)

        header_text = f"[bold {pc}]{entity.name}[/]"
        if entity.base_type:
            header_text += f"\n[dim]Base: {entity.base_type}[/]"
        header_text += f"\n[dim]Keys: {', '.join(entity.keys)}[/]"
        panel = Panel(header_text, title="Entity", box=box.ROUNDED)

        custom_count = len(entity.custom_fields)
        nav_count = len(entity.navigation)

        groups = group_entity_properties(entity)
        rtree = RichTree(f"[bold {pc}]{entity.name}[/]")

        if groups["keys"]:
            keys_branch = rtree.add(f"[{ac}]Keys[/]")
            for prop in groups["keys"]:
                keys_branch.add(f"[{pc}]{prop.name}[/] [dim]{prop.type}[/]")

        if groups["other_nav"]:
            nav_branch = rtree.add(f"[blue]Navigation[/] ({nav_count})")
            for nav in groups["other_nav"][:15]:
                target = nav.target_entity or "?"
                nav_branch.add(f"[{pc}]{nav.name}[/] -> [{sc}]{target}[/]")
            if len(groups["other_nav"]) > 15:
                nav_branch.add(f"[dim]... and {len(groups['other_nav']) - 15} more[/]")

        if groups["custom"]:
            custom_branch = rtree.add(f"[{ac}]Custom Fields[/] ({custom_count})")
            for prop in groups["custom"][:10]:
                label_hint = f' [dim]"{prop.label}"[/]' if prop.label else ""
                pick_hint = f' [magenta]{prop.picklist}[/]' if prop.picklist else ""
                custom_branch.add(f"[{pc}]{prop.name}[/] {prop.type}{label_hint}{pick_hint}")
            if custom_count > 10:
                custom_branch.add(f"[dim]... and {custom_count - 10} more[/]")

        summary = Text.from_markup(
            f"  [bold]{len(entity.properties)}[/] properties"
            f"  |  [bold]{custom_count}[/] custom fields"
            f"  |  [bold]{nav_count}[/] navigation\n"
        )

        details_widget.update(Group(panel, summary, rtree))

    def _setup_property_table(self) -> None:
        """Populate the Properties sub-tab DataTable."""
        entity = self.entity
        ac = VERCEL_THEME.accent

        prop_table = self.query_one(f"#prop-table-{entity.name}", DataTable)
        prop_table.add_column("Property", width=25, key="name")
        prop_table.add_column("Type", width=15, key="type")
        prop_table.add_column("Len", width=5, key="len")
        prop_table.add_column("Label", width=20, key="label")
        prop_table.add_column("Picklist", width=18, key="picklist")
        prop_table.add_column("Req", width=3, key="req")
        prop_table.add_column("C", width=3, key="create")
        prop_table.add_column("U", width=3, key="update")
        prop_table.add_column("Up", width=3, key="upsert")
        prop_table.add_column("Vis", width=3, key="vis")
        prop_table.add_column("Sort", width=4, key="sort")
        prop_table.add_column("Filt", width=4, key="filt")

        self._prop_rows = []
        for prop in sort_properties(entity.properties, entity.keys):
            is_key = prop.name in entity.keys
            row = (
                f"[{ac}]{prop.name}[/]" if is_key else prop.name,
                prop.type,
                prop.max_length or "",
                prop.label or "",
                prop.picklist or "",
                format_flag_check(prop.required or is_key),
                format_flag_check(prop.creatable),
                format_flag_check(prop.updatable),
                format_flag_check(prop.upsertable),
                format_flag_check(prop.visible),
                format_flag_check(prop.sortable),
                format_flag_check(prop.filterable),
            )
            self._prop_rows.append(row)
            prop_table.add_row(*row)

    def apply_filter(self, term: str) -> tuple[int, int]:
        """Filter the property table by fuzzy match.

        Args:
            term: The filter string (lowercase).

        Returns:
            Tuple of (matched_count, total_count).
        """
        self._table_filter = term
        try:
            prop_table = self.query_one(DataTable)
        except Exception:
            return (0, 0)

        prop_table.clear()

        if not term:
            for row in self._prop_rows:
                prop_table.add_row(*row)
            return (len(self._prop_rows), len(self._prop_rows))

        matched = 0
        for row in self._prop_rows:
            row_text = " ".join(str(c) for c in row).lower()
            if _fuzzy_match(term, row_text):
                prop_table.add_row(*row)
                matched += 1
        return (matched, len(self._prop_rows))


def _fuzzy_match(pattern: str, text: str) -> bool:
    """Check if all characters in *pattern* appear in order in *text*.

    Args:
        pattern: Lowercase search pattern.
        text: Lowercase text to match against.

    Returns:
        ``True`` if every character of *pattern* appears sequentially in *text*.
    """
    it = iter(text)
    return all(c in it for c in pattern)
