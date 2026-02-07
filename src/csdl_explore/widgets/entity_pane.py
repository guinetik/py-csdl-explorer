"""Entity tab pane — thin shell composing Details, Properties, and Query sub-tabs."""

from datetime import datetime
from pathlib import Path

from textual.widgets import TabbedContent, TabPane
from textual import on

from ..explorer import CSDLExplorer
from ..parser import EntityType
from .details_tab import DetailsTab
from .properties_tab import PropertiesTab
from .query_tab import QueryTab
from .results_viewer import ResultsViewer


class EntityTabPane(TabPane):
    """A tab pane composing Details, Properties, and Query sub-tabs for one entity.

    Args:
        entity: The entity type to display.
        explorer: The CSDL explorer instance.
    """

    def __init__(self, entity: EntityType, explorer: CSDLExplorer):
        pane_id = f"entity-{entity.name}"
        super().__init__(entity.name, id=pane_id)
        self.entity = entity
        self.explorer = explorer

    def compose(self):
        eid = self.entity.name
        with TabbedContent(id=f"sub-tabs-{eid}"):
            yield DetailsTab(self.entity, tab_id=f"detail-{eid}")
            yield PropertiesTab(self.entity, tab_id=f"props-{eid}")
            yield QueryTab(self.entity, tab_id=f"query-{eid}")

    def apply_filter(self, term: str) -> tuple[int, int]:
        """Delegate filter to PropertiesTab.

        Args:
            term: The filter string (lowercase).

        Returns:
            Tuple of (matched_count, total_count).
        """
        props_tab = self.query_one(PropertiesTab)
        return props_tab.apply_filter(term)

    @on(ResultsViewer.SaveRequested)
    def _on_save_response(self, event: ResultsViewer.SaveRequested) -> None:
        """Save the raw response to a file alongside the metadata XML."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{event.entity_name}_{timestamp}.{event.extension}"
        metadata_path = getattr(self.app, "metadata_path", None)
        if metadata_path:
            save_path = metadata_path.parent / filename
        else:
            save_path = Path.cwd() / filename
        save_path.write_text(event.content, encoding="utf-8")
        self.app.notify(f"Saved to {filename}", timeout=3)
