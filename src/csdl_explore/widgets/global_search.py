"""Global search widget for jumping to any metadata element."""

from textual.widget import Widget
from textual.widgets import Input, DataTable, Static
from textual.containers import Vertical
from textual.message import Message
from textual import on

from ..explorer import CSDLExplorer


class GlobalSearch(Widget):
    """Global search across all metadata - entities, properties, picklists.

    Args:
        explorer: The CSDL explorer instance.
    """

    can_focus = True

    DEFAULT_CSS = """
    GlobalSearch {
        height: 1fr;
        width: 1fr;
    }

    GlobalSearch #global-search-input {
        dock: top;
        height: 3;
        width: 100%;
        margin: 1 2;
    }

    GlobalSearch #global-search-results {
        height: 1fr;
        width: 100%;
    }

    GlobalSearch #global-search-help {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    class EntitySelected(Message):
        """Posted when an entity is selected from search results.

        Attributes:
            entity_name: Name of the entity to open.
        """

        def __init__(self, entity_name: str) -> None:
            super().__init__()
            self.entity_name = entity_name

    class PicklistSelected(Message):
        """Posted when a picklist is selected from search results.

        Attributes:
            picklist_name: Name of the picklist to open.
            entity_names: Entities that reference this picklist.
        """

        def __init__(self, picklist_name: str, entity_names: list[str]) -> None:
            super().__init__()
            self.picklist_name = picklist_name
            self.entity_names = entity_names

    def __init__(self, explorer: CSDLExplorer, **kwargs) -> None:
        super().__init__(**kwargs)
        self._explorer = explorer
        self._all_results = []  # Store all search results

    def compose(self):
        yield Input(
            placeholder="Search everything: entities, properties, picklists...",
            id="global-search-input"
        )
        yield DataTable(id="global-search-results", cursor_type="row")
        yield Static(
            "[dim]Type to search • Enter to open • Shows entities, properties, picklists[/]",
            id="global-search-help"
        )

    def on_mount(self) -> None:
        """Initialize the results table."""
        table = self.query_one("#global-search-results", DataTable)
        table.add_columns("Type", "Name", "Location")
        table.cursor_type = "row"

        # Focus the search input
        self.query_one("#global-search-input", Input).focus()

    @on(Input.Changed, "#global-search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        query = event.value.strip().lower()
        if not query:
            # Clear results if empty
            table = self.query_one("#global-search-results", DataTable)
            table.clear()
            self._all_results = []
            return

        # Search across all metadata
        results = []

        # Search entities
        for entity_name, entity in self._explorer.entities.items():
            if query in entity_name.lower():
                results.append({
                    "type": "Entity",
                    "name": entity_name,
                    "location": f"{len(entity.properties)} properties",
                    "entity": entity_name,
                })

        # Search properties
        for entity_name, entity in self._explorer.entities.items():
            for prop_name in entity.properties:
                if query in prop_name.lower():
                    results.append({
                        "type": "Property",
                        "name": prop_name,
                        "location": entity_name,
                        "entity": entity_name,
                    })

        # Search picklists
        all_picklists = {}
        for entity in self._explorer.entities.values():
            for prop in entity.properties.values():
                if prop.picklist:
                    if prop.picklist not in all_picklists:
                        all_picklists[prop.picklist] = []
                    all_picklists[prop.picklist].append(entity.name)

        for picklist_name, entity_names in all_picklists.items():
            if query in picklist_name.lower():
                results.append({
                    "type": "Picklist",
                    "name": picklist_name,
                    "location": f"{len(entity_names)} entities",
                    "entity": entity_names[0] if entity_names else "",
                    "entity_names": entity_names,
                })

        # Search navigation properties
        for entity_name, entity in self._explorer.entities.items():
            for nav_name in entity.navigation:
                if query in nav_name.lower():
                    nav = entity.navigation[nav_name]
                    target = nav.target_entity or "?"
                    results.append({
                        "type": "Navigation",
                        "name": nav_name,
                        "location": f"{entity_name} → {target}",
                        "entity": entity_name,
                    })

        # Update table
        self._all_results = results
        table = self.query_one("#global-search-results", DataTable)
        table.clear()

        for i, result in enumerate(results[:100]):  # Limit to 100 results for performance
            table.add_row(
                result["type"],
                result["name"],
                result["location"],
                key=str(i),
            )

    @on(DataTable.RowSelected, "#global-search-results")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection - open the associated entity or picklist."""
        try:
            idx = int(event.row_key.value)
        except (ValueError, TypeError):
            return
        if idx >= len(self._all_results):
            return

        result = self._all_results[idx]
        if result["type"] == "Picklist":
            self.post_message(
                self.PicklistSelected(result["name"], result.get("entity_names", []))
            )
        elif result["entity"]:
            self.post_message(self.EntitySelected(result["entity"]))
