"""Interactive navigation graph widget - force-directed entity relationship visualization."""

from textual.widget import Widget
from textual.reactive import reactive
from textual.message import Message
from textual import events, work
from textual.containers import Vertical
from textual.widgets import Static

from rich.text import Text
from rich.console import Group, RenderableType

from ..explorer import CSDLExplorer
from ..formatters import build_navigation_graph


class NavigationGraph(Widget):
    """Interactive graph visualization of entity navigation relationships.

    Shows entities as boxes connected by navigation properties. Uses force-directed
    layout from NetworkX. Supports pan, zoom, and click-to-open interactions.

    Args:
        explorer: The CSDL explorer instance.
    """

    # Allow this widget to receive keyboard focus
    can_focus = True

    DEFAULT_CSS = """
    NavigationGraph {
        height: 1fr;
        width: 1fr;
        overflow: auto;
    }

    NavigationGraph .graph-loading {
        width: 100%;
        height: 100%;
        content-align: center middle;
    }

    NavigationGraph .graph-canvas {
        width: 100%;
        height: 1fr;
    }

    NavigationGraph .graph-help {
        dock: bottom;
        height: 3;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        display: none;
    }

    NavigationGraph .graph-help.visible {
        display: block;
    }
    """

    BINDINGS = [
        ("up", "pan('up')", "Pan Up"),
        ("down", "pan('down')", "Pan Down"),
        ("left", "pan('left')", "Pan Left"),
        ("right", "pan('right')", "Pan Right"),
        ("plus", "zoom('plus')", "Zoom In"),
        ("minus", "zoom('minus')", "Zoom Out"),
        ("tab", "navigate('tab')", "Next Node"),
        ("shift+tab", "navigate('shift+tab')", "Prev Node"),
        ("enter", "select", "Open"),
        ("home", "reset", "Reset"),
        ("h", "toggle_help", "Help"),
    ]

    # Reactive state
    show_help = reactive(False)
    zoom_level = reactive(1.0)

    class EntitySelected(Message):
        """Posted when a node is selected for opening.

        Attributes:
            entity_name: Name of the entity to open.
        """

        def __init__(self, entity_name: str) -> None:
            super().__init__()
            self.entity_name = entity_name

    def __init__(self, explorer: CSDLExplorer, **kwargs) -> None:
        super().__init__(**kwargs)
        self._explorer = explorer
        self._graph_data: dict | None = None
        self._viewport = (0.0, 0.0, 1.0)  # pan_x, pan_y, zoom
        self._selected_node: str | None = None
        self._node_list: list[str] = []
        self._world_bounds = {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}
        self._zoom_levels = [0.25, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]
        self._zoom_index = 4  # Start at 1.0

    def compose(self):
        yield Static("Building graph...", classes="graph-loading")
        yield Static(id="graph-canvas", classes="graph-canvas")
        yield Static(
            "[dim]↑↓←→ Pan | +/- Zoom | Tab Navigate | Enter Open | Home Reset | h Help[/]",
            classes="graph-help",
        )

    def on_mount(self) -> None:
        """Compute graph on mount in background thread."""
        self._build_graph_async()

    def on_resize(self) -> None:
        """Re-render graph when widget is resized."""
        if self._graph_data:
            self._render_graph()

    @work(thread=True)
    def _build_graph_async(self) -> None:
        """Build graph in worker thread to avoid blocking UI."""
        try:
            graph_data = build_navigation_graph(self._explorer)
            self.app.call_from_thread(self._on_graph_ready, graph_data)
        except Exception as e:
            self.app.call_from_thread(self._on_graph_error, str(e))

    def _on_graph_ready(self, graph_data: dict) -> None:
        """Handle graph computation completion."""
        self._graph_data = graph_data
        self._world_bounds = graph_data["bounds"]

        # Build sorted node list for Tab navigation
        self._node_list = sorted(n["id"] for n in graph_data["nodes"])

        # Select first node by default
        if self._node_list:
            self._selected_node = self._node_list[0]

        # Center viewport on most connected node (hub)
        positions = graph_data["positions"]
        if positions and graph_data["nodes"]:
            # Find node with most total connections
            hub_node = max(
                graph_data["nodes"],
                key=lambda n: n["incoming_count"] + n["outgoing_count"]
            )
            hub_pos = positions.get(hub_node["id"])
            if hub_pos:
                self._viewport = (hub_pos[0], hub_pos[1], 1.0)
            else:
                # Fallback to centroid if hub position not found
                x_coords = [pos[0] for pos in positions.values()]
                y_coords = [pos[1] for pos in positions.values()]
                centroid_x = sum(x_coords) / len(x_coords)
                centroid_y = sum(y_coords) / len(y_coords)
                self._viewport = (centroid_x, centroid_y, 1.0)

        # Hide loading, show canvas
        self.query_one(".graph-loading", Static).display = False
        self._render_graph()

    def _on_graph_error(self, error: str) -> None:
        """Handle graph computation error."""
        loading = self.query_one(".graph-loading", Static)
        loading.update(f"[red]Error building graph:[/] {error}")

    def _render_graph(self) -> None:
        """Render the visible portion of the graph."""
        if not self._graph_data:
            return

        canvas = self.query_one("#graph-canvas", Static)

        # If no nodes, show message
        if not self._graph_data["nodes"]:
            canvas.update("[dim]No navigation relationships found in metadata[/]")
            return

        # Get viewport dimensions (use minimum size if not yet laid out)
        widget_width = max(self.size.width, 80)
        widget_height = max(self.size.height - 4, 20)  # Account for help bar

        # Calculate visible world bounds
        # World coords from spring_layout are roughly in [-1, 1] range
        # Viewport size in world units (not screen units!)
        pan_x, pan_y, zoom = self._viewport

        # Base world viewport size (will be scaled by zoom)
        # Increased to match larger world coordinates from scale=4.0
        base_world_width = 6.0  # Show ~6 units of world space
        base_world_height = 6.0

        # Apply zoom (higher zoom = smaller viewport = more detail)
        visible_width = base_world_width / zoom
        visible_height = base_world_height / zoom

        visible_bounds = {
            "min_x": pan_x - visible_width / 2,
            "max_x": pan_x + visible_width / 2,
            "min_y": pan_y - visible_height / 2,
            "max_y": pan_y + visible_height / 2,
        }

        # Filter visible nodes
        positions = self._graph_data["positions"]
        visible_nodes = []
        for node in self._graph_data["nodes"]:
            node_id = node["id"]
            if node_id not in positions:
                continue
            x, y = positions[node_id]
            if (
                visible_bounds["min_x"] <= x <= visible_bounds["max_x"]
                and visible_bounds["min_y"] <= y <= visible_bounds["max_y"]
            ):
                visible_nodes.append(node)

        # Build render grid
        grid = {}  # (row, col) -> character
        node_boxes = {}  # node_id -> (row, col, width, height)

        # Calculate world space dimensions
        world_width = visible_bounds["max_x"] - visible_bounds["min_x"]
        world_height = visible_bounds["max_y"] - visible_bounds["min_y"]

        # Avoid division by zero
        if world_width == 0:
            world_width = 1
        if world_height == 0:
            world_height = 1

        # Render nodes
        for node in visible_nodes:
            node_id = node["id"]
            x, y = positions[node_id]

            # Convert world coordinates to screen coordinates
            # Map from world space [min, max] to screen space [0, width/height]
            normalized_x = (x - visible_bounds["min_x"]) / world_width
            normalized_y = (y - visible_bounds["min_y"]) / world_height
            screen_x = int(normalized_x * widget_width)
            screen_y = int(normalized_y * widget_height)

            # Determine box representation based on zoom
            is_selected = node_id == self._selected_node
            if zoom >= 0.7:
                # Full box - check bounds and collision
                box_width = len(node_id) + 4
                box_height = 3

                # Only render if entire box fits on screen (prevent clipping at edges)
                if (screen_x >= 0 and screen_y >= 0 and
                    screen_x + box_width <= widget_width and
                    screen_y + box_height <= widget_height):
                    if not self._box_would_collide(grid, screen_x, screen_y, box_width, box_height):
                        self._render_node_box(grid, node_id, screen_x, screen_y, is_selected)
                        node_boxes[node_id] = (screen_y, screen_x, box_width, box_height)
            elif zoom >= 0.4:
                # Single char
                grid[(screen_y, screen_x)] = f"[{'#00dc82' if is_selected else '#666666'}][{node_id[0]}][/]"
                node_boxes[node_id] = (screen_y, screen_x, 1, 1)
            else:
                # Dot
                grid[(screen_y, screen_x)] = f"[{'#00dc82' if is_selected else '#666666'}]•[/]"
                node_boxes[node_id] = (screen_y, screen_x, 1, 1)

        # Render edges (only between fully visible boxes)
        if zoom >= 0.7:  # Only show edges at full box zoom level
            for edge in self._graph_data["edges"]:
                source = edge["source"]
                target = edge["target"]
                # Only draw edge if both boxes were rendered (in node_boxes dict)
                if source in node_boxes and target in node_boxes:
                    self._render_edge(grid, node_boxes[source], node_boxes[target])

        # Convert grid to text
        if grid:
            max_row = max(pos[0] for pos in grid.keys())
            max_col = max(pos[1] for pos in grid.keys())

            lines = []
            # Render the graph grid
            for row in range(max_row + 1):
                line_parts = []
                for col in range(max_col + 1):
                    char = grid.get((row, col), " ")
                    line_parts.append(char)
                lines.append("".join(line_parts))

            canvas.update("\n".join(lines))
        else:
            canvas.update(f"[dim]No entities in viewport\nWidget: {widget_width}x{widget_height}\nZoom: {zoom}[/]")

    def _box_would_collide(self, grid: dict, x: int, y: int, width: int, height: int) -> bool:
        """Check if a box at the given position would collide with existing grid content.

        Includes 1-cell padding on all sides to ensure boxes don't touch.

        Args:
            grid: The rendering grid.
            x: Left column position.
            y: Top row position.
            width: Box width in characters.
            height: Box height in rows.

        Returns:
            True if any cell in the box region (plus padding) is already occupied.
        """
        # Check box region plus 1-cell padding on all sides
        for row in range(max(0, y - 1), y + height + 1):
            for col in range(max(0, x - 1), x + width + 1):
                if (row, col) in grid:
                    return True
        return False

    def _render_node_box(
        self,
        grid: dict,
        name: str,
        x: int,
        y: int,
        is_selected: bool,
    ) -> None:
        """Render a node as a box with the entity name inside."""
        width = len(name) + 4
        color = "#00dc82" if is_selected else "#808080"

        # Box characters
        if is_selected:
            tl, tr, bl, br = "╔", "╗", "╚", "╝"
            h, v = "═", "║"
        else:
            tl, tr, bl, br = "┌", "┐", "└", "┘"
            h, v = "─", "│"

        # Top border
        grid[(y, x)] = f"[{color}]{tl}[/]"
        for i in range(1, width - 1):
            grid[(y, x + i)] = f"[{color}]{h}[/]"
        grid[(y, x + width - 1)] = f"[{color}]{tr}[/]"

        # Middle row with name
        grid[(y + 1, x)] = f"[{color}]{v}[/]"
        name_text = f" {name} "
        for i, char in enumerate(name_text):
            grid[(y + 1, x + 1 + i)] = f"[{'#00dc82' if is_selected else 'white'}]{char}[/]"
        grid[(y + 1, x + width - 1)] = f"[{color}]{v}[/]"

        # Bottom border
        grid[(y + 2, x)] = f"[{color}]{bl}[/]"
        for i in range(1, width - 1):
            grid[(y + 2, x + i)] = f"[{color}]{h}[/]"
        grid[(y + 2, x + width - 1)] = f"[{color}]{br}[/]"

    def _render_edge(
        self,
        grid: dict,
        source_box: tuple,
        target_box: tuple,
    ) -> None:
        """Render an edge between two node boxes using simple line drawing."""
        # For simplicity, just draw a straight line from source center to target center
        s_row, s_col, s_width, s_height = source_box
        t_row, t_col, t_width, t_height = target_box

        # Source center
        sx = s_col + s_width // 2
        sy = s_row + s_height // 2

        # Target center
        tx = t_col + t_width // 2
        ty = t_row + t_height // 2

        # Draw horizontal then vertical line (orthogonal routing)
        # Use dim color so edges don't overpower boxes
        color = "#444444"

        # Horizontal line
        start_x = min(sx, tx)
        end_x = max(sx, tx)
        for col in range(start_x, end_x + 1):
            cell = grid.get((sy, col), " ")
            # Only draw in empty cells (don't overwrite box characters)
            if cell == " " or not cell.strip():
                grid[(sy, col)] = f"[{color}]─[/]"

        # Vertical line
        start_y = min(sy, ty)
        end_y = max(sy, ty)
        for row in range(start_y, end_y + 1):
            cell = grid.get((row, tx), " ")
            # Only draw in empty cells (don't overwrite box characters)
            if cell == " " or not cell.strip():
                grid[(row, tx)] = f"[{color}]│[/]"

    # Actions

    def action_pan(self, direction: str = "up") -> None:
        """Pan the viewport in the given direction."""
        pan_x, pan_y, zoom = self._viewport
        step = 0.5 / zoom  # Smooth panning - about 1/12th of viewport

        if direction == "up":
            pan_y -= step
        elif direction == "down":
            pan_y += step
        elif direction == "left":
            pan_x -= step
        elif direction == "right":
            pan_x += step

        self._viewport = (pan_x, pan_y, zoom)
        self._render_graph()

    def action_zoom(self, direction: str = "plus") -> None:
        """Zoom in or out."""
        if direction == "plus":
            self._zoom_index = min(self._zoom_index + 1, len(self._zoom_levels) - 1)
        else:
            self._zoom_index = max(self._zoom_index - 1, 0)

        new_zoom = self._zoom_levels[self._zoom_index]
        pan_x, pan_y, _ = self._viewport
        self._viewport = (pan_x, pan_y, new_zoom)
        self.zoom_level = new_zoom
        self._render_graph()

    def action_navigate(self, direction: str = "tab") -> None:
        """Navigate between nodes using Tab/Shift+Tab."""
        if not self._node_list or not self._selected_node:
            return

        try:
            current_idx = self._node_list.index(self._selected_node)
        except ValueError:
            current_idx = 0

        if direction == "tab":
            next_idx = (current_idx + 1) % len(self._node_list)
        else:  # shift+tab
            next_idx = (current_idx - 1) % len(self._node_list)

        self._selected_node = self._node_list[next_idx]
        self._render_graph()

    def action_select(self) -> None:
        """Open the selected node's entity in a tab."""
        if self._selected_node:
            self.post_message(self.EntitySelected(self._selected_node))

    def action_reset(self) -> None:
        """Reset viewport to default (centered on hub node, zoom 1.0)."""
        if not self._graph_data or not self._graph_data["positions"]:
            return

        # Center on most connected node (hub)
        positions = self._graph_data["positions"]
        if self._graph_data["nodes"]:
            hub_node = max(
                self._graph_data["nodes"],
                key=lambda n: n["incoming_count"] + n["outgoing_count"]
            )
            hub_pos = positions.get(hub_node["id"])
            if hub_pos:
                self._viewport = (hub_pos[0], hub_pos[1], 1.0)
            else:
                # Fallback to centroid
                x_coords = [pos[0] for pos in positions.values()]
                y_coords = [pos[1] for pos in positions.values()]
                self._viewport = (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords), 1.0)

        self._zoom_index = 4  # Reset to 1.0
        self.zoom_level = 1.0
        self._render_graph()

    def action_toggle_help(self) -> None:
        """Toggle help bar visibility."""
        help_bar = self.query_one(".graph-help", Static)
        if help_bar.has_class("visible"):
            help_bar.remove_class("visible")
        else:
            help_bar.add_class("visible")

    def on_click(self, event: events.Click) -> None:
        """Handle mouse clicks on nodes."""
        # TODO: Map click coordinates to nodes and post EntitySelected
        # For now, clicking just selects via keyboard navigation
        pass
