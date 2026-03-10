"""Picklist Impact Analysis sub-tab — shows required properties and affected entities."""

import re
from textual.containers import VerticalScroll
from textual.widgets import Static, TabPane

from ..parser import Property
from ..formatters import format_flag_check, compute_picklist_impact
from ..themes import VERCEL_THEME
from .filterable_table import FilterableDataTable


def _sanitize_id(name: str) -> str:
    """Sanitize name for widget ID."""
    return re.sub(r'-+', '-', re.sub(r'[^a-zA-Z0-9_-]', '-', name)).strip('-')


class PicklistImpactTab(TabPane):
    """Impact Analysis sub-tab showing how picklist changes affect entities.

    Args:
        picklist_name: The picklist name.
        picklist_data: Mapping of entity name to properties using this picklist.
        tab_id: Unique tab pane ID.
    """

    def __init__(
        self, picklist_name: str, picklist_data: dict[str, list[Property]], tab_id: str,
    ) -> None:
        super().__init__("Impact Analysis", id=tab_id)
        self._picklist_name = picklist_name
        self._picklist_data = picklist_data

    def compose(self):
        with VerticalScroll():
            yield Static(id=f"pick-impact-summary-{_sanitize_id(self._picklist_name)}")
            yield FilterableDataTable(
                id=f"pick-impact-table-{_sanitize_id(self._picklist_name)}",
                zebra_stripes=True,
                cursor_type="row",
            )

    def on_mount(self) -> None:
        """Populate impact summary and table."""
        self._setup()

    def _setup(self) -> None:
        """Compute impact stats and populate widgets."""
        wc = VERCEL_THEME.warning
        impact = compute_picklist_impact(self._picklist_data)

        summary_text = (
            f"  [{wc}]{impact['required_count']}[/] required properties — "
            f"changes affect create operations on [{wc}]{impact['create_entity_count']}[/] entities\n"
        )
        self.query_one(f"#pick-impact-summary-{_sanitize_id(self._picklist_name)}", Static).update(summary_text)

        table = self.query_one(f"#pick-impact-table-{_sanitize_id(self._picklist_name)}", FilterableDataTable)
        table.add_column("Entity", width=25, key="entity")
        table.add_column("Property", width=20, key="property")
        table.add_column("Req", width=3, key="req")
        table.add_column("C", width=3, key="create")
        table.add_column("U", width=3, key="update")
        table.add_column("Up", width=3, key="upsert")
        table.add_column("Filt", width=4, key="filt")
        table.add_column("Sort", width=4, key="sort")

        for entity_name in sorted(self._picklist_data):
            for prop in self._picklist_data[entity_name]:
                table.add_filtered_row(
                    entity_name, prop.name,
                    format_flag_check(prop.required),
                    format_flag_check(prop.creatable),
                    format_flag_check(prop.updatable),
                    format_flag_check(prop.upsertable),
                    format_flag_check(prop.filterable),
                    format_flag_check(prop.sortable),
                )
