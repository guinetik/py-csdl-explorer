"""Picklist tab pane — shows Overview, Entities, and Impact Analysis for a picklist."""

from textual.containers import VerticalScroll
from textual.widgets import Static, DataTable, TabbedContent, TabPane
from textual import on
from textual.message import Message

from rich.console import Group
from rich.panel import Panel
from rich.tree import Tree as RichTree
from rich import box

from ..explorer import CSDLExplorer
from ..parser import Property
from ..formatters import format_flag_check
from ..themes import VERCEL_THEME


class PicklistTabPane(TabPane):
    """A tab pane displaying Overview, Entities, and Impact Analysis for one picklist.

    Args:
        name: The picklist name.
        picklist_data: Mapping of entity name to list of properties referencing this picklist.
        explorer: The CSDL explorer instance.
    """

    class EntitySelected(Message):
        """Posted when a user selects an entity row in the Entities sub-tab."""

        def __init__(self, entity_name: str) -> None:
            super().__init__()
            self.entity_name = entity_name

    def __init__(self, name: str, picklist_data: dict[str, list[Property]], explorer: CSDLExplorer):
        pane_id = f"picklist-{name}"
        super().__init__(name, id=pane_id)
        self.picklist_name = name
        self.picklist_data = picklist_data
        self.explorer = explorer

    def compose(self):
        pid = self.picklist_name
        with TabbedContent(id=f"pick-sub-{pid}"):
            with TabPane("Overview", id=f"pick-overview-{pid}"):
                with VerticalScroll():
                    yield Static(id=f"pick-details-{pid}")
            with TabPane("Entities", id=f"pick-entities-{pid}"):
                yield DataTable(
                    id=f"pick-entity-table-{pid}",
                    zebra_stripes=True,
                    cursor_type="row",
                )
            with TabPane("Impact Analysis", id=f"pick-impact-{pid}"):
                with VerticalScroll():
                    yield Static(id=f"pick-impact-summary-{pid}")
                    yield DataTable(
                        id=f"pick-impact-table-{pid}",
                        zebra_stripes=True,
                        cursor_type="row",
                    )

    def on_mount(self) -> None:
        """Render all three sub-tabs after mount."""
        self._render_overview()
        self._setup_entities_table()
        self._setup_impact_table()

    # ── Overview sub-tab ──────────────────────────────────────────

    def _render_overview(self) -> None:
        """Populate the Overview sub-tab with a panel and Rich tree."""
        wc = VERCEL_THEME.warning
        pc = VERCEL_THEME.primary

        entity_count = len(self.picklist_data)
        prop_count = sum(len(props) for props in self.picklist_data.values())

        header_text = f"[bold {wc}]{self.picklist_name}[/]"
        panel = Panel(header_text, title="Picklist", box=box.ROUNDED)

        summary = f"  Used by [bold]{entity_count}[/] entities across [bold]{prop_count}[/] properties\n"

        rtree = RichTree(f"[bold {wc}]{self.picklist_name}[/]")
        for entity_name in sorted(self.picklist_data):
            branch = rtree.add(f"[{pc}]{entity_name}[/]")
            for prop in self.picklist_data[entity_name]:
                label_hint = f' "{prop.label}"' if prop.label else ""
                branch.add(f"{prop.name} [dim]{prop.type}{label_hint}[/]")

        widget = self.query_one(f"#pick-details-{self.picklist_name}", Static)
        widget.update(Group(panel, summary, rtree))

    # ── Entities sub-tab ──────────────────────────────────────────

    def _setup_entities_table(self) -> None:
        """Populate the Entities DataTable."""
        table = self.query_one(f"#pick-entity-table-{self.picklist_name}", DataTable)
        table.add_column("Entity", width=25, key="entity")
        table.add_column("Property", width=20, key="property")
        table.add_column("Type", width=15, key="type")
        table.add_column("Label", width=20, key="label")
        table.add_column("Req", width=3, key="req")
        table.add_column("C", width=3, key="create")
        table.add_column("U", width=3, key="update")

        self._entity_rows: list[str] = []
        for entity_name in sorted(self.picklist_data):
            for prop in self.picklist_data[entity_name]:
                table.add_row(
                    entity_name,
                    prop.name,
                    prop.type,
                    prop.label or "",
                    format_flag_check(prop.required),
                    format_flag_check(prop.creatable),
                    format_flag_check(prop.updatable),
                )
                self._entity_rows.append(entity_name)

    @on(DataTable.RowSelected)
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the Entities table — post EntitySelected."""
        table_id = f"pick-entity-table-{self.picklist_name}"
        if event.data_table.id != table_id:
            return
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._entity_rows):
            self.post_message(self.EntitySelected(self._entity_rows[row_idx]))

    # ── Impact Analysis sub-tab ───────────────────────────────────

    def _setup_impact_table(self) -> None:
        """Populate the Impact Analysis summary and DataTable."""
        wc = VERCEL_THEME.warning

        # Compute stats
        required_props = []
        create_entities = set()
        for entity_name, props in self.picklist_data.items():
            for prop in props:
                if prop.required:
                    required_props.append((entity_name, prop))
                if prop.creatable:
                    create_entities.add(entity_name)

        summary_text = (
            f"  [{wc}]{len(required_props)}[/] required properties — "
            f"changes affect create operations on [{wc}]{len(create_entities)}[/] entities\n"
        )
        self.query_one(f"#pick-impact-summary-{self.picklist_name}", Static).update(summary_text)

        table = self.query_one(f"#pick-impact-table-{self.picklist_name}", DataTable)
        table.add_column("Entity", width=25, key="entity")
        table.add_column("Property", width=20, key="property")
        table.add_column("Req", width=3, key="req")
        table.add_column("C", width=3, key="create")
        table.add_column("U", width=3, key="update")
        table.add_column("Up", width=3, key="upsert")
        table.add_column("Filt", width=4, key="filt")
        table.add_column("Sort", width=4, key="sort")

        for entity_name in sorted(self.picklist_data):
            for prop in self.picklist_data[entity_name]:
                table.add_row(
                    entity_name,
                    prop.name,
                    format_flag_check(prop.required),
                    format_flag_check(prop.creatable),
                    format_flag_check(prop.updatable),
                    format_flag_check(prop.upsertable),
                    format_flag_check(prop.filterable),
                    format_flag_check(prop.sortable),
                )
