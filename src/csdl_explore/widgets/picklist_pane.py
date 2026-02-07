"""Picklist tab pane — thin shell composing Overview, Entities, Impact, and Get Values."""

from textual.widgets import TabbedContent, TabPane
from textual.message import Message
from textual import on

from ..explorer import CSDLExplorer
from ..parser import Property
from .picklist_overview_tab import PicklistOverviewTab
from .picklist_entities_tab import PicklistEntitiesTab
from .picklist_impact_tab import PicklistImpactTab
from .picklist_values_tab import PicklistValuesTab


class PicklistTabPane(TabPane):
    """A tab pane composing Overview, Entities, Impact Analysis, and Get Values for one picklist.

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
            yield PicklistOverviewTab(pid, self.picklist_data, tab_id=f"pick-overview-{pid}")
            yield PicklistEntitiesTab(pid, self.picklist_data, tab_id=f"pick-entities-{pid}")
            yield PicklistImpactTab(pid, self.picklist_data, tab_id=f"pick-impact-{pid}")
            yield PicklistValuesTab(pid, tab_id=f"pick-getval-{pid}")

    @on(PicklistEntitiesTab.EntitySelected)
    def _on_entity_selected(self, event: PicklistEntitiesTab.EntitySelected) -> None:
        """Bubble EntitySelected up to app level."""
        self.post_message(self.EntitySelected(event.entity_name))
