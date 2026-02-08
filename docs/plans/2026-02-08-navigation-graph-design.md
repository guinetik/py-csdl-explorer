# Interactive Navigation Graph - Design Document

**Date:** 2026-02-08
**Status:** Approved
**Implementation:** Pending

## Overview

Add an interactive navigation graph visualization to the welcome screen that shows entity relationships through navigation properties. Users can pan, zoom, and click nodes to explore the metadata structure visually.

## Goals

- Visualize navigation relationships between entities as an interactive graph
- Replace empty welcome screen with useful metadata overview
- Enable visual exploration: click nodes to open entity tabs
- Support pan/zoom for graphs with hundreds of connected entities
- Keep rendering performant by only drawing visible nodes/edges

## User Experience

When users launch the TUI with no tabs open, they see:
1. **Stats panel** at top: counts of entities, properties, picklists, custom fields
2. **Interactive graph** below: force-directed layout showing entities (boxes) connected by navigation properties (lines)

**Interaction:**
- Arrow keys pan the viewport
- `+`/`-` zoom in/out (5 preset levels: 0.25x, 0.5x, 0.75x, 1.0x, 1.5x)
- Tab/Shift+Tab navigate between nodes
- Enter opens selected entity in a tab
- Click a node box to select and open immediately
- `h` toggles help overlay
- `Home` resets to default view (centered, 1.0x zoom)

When users close all entity/picklist tabs, the welcome screen reappears automatically (already implemented).

## Architecture

### Domain Layer (formatters.py)

Add `build_navigation_graph(explorer: CSDLExplorer) -> dict`:

```python
def build_navigation_graph(explorer: CSDLExplorer) -> dict:
    """Build navigation graph structure from metadata.

    Returns:
        dict with:
        - nodes: list[dict] with {id, name, incoming_count, outgoing_count}
        - edges: list[dict] with {source, target, nav_name}
        - positions: dict[str, tuple[float, float]] from NetworkX spring_layout
        - bounds: dict with {min_x, max_x, min_y, max_y}
    """
```

**Algorithm:**
1. Filter entities: only include entities with ≥1 navigation property (incoming or outgoing)
2. Build NetworkX DiGraph: nodes = entity names, edges = navigation properties (source → target)
3. Compute layout: `nx.spring_layout(graph, k=1.5, iterations=50)`
4. Extract positions and bounds
5. Return plain Python dicts/lists (no NetworkX objects)

### Widget Layer (widgets/nav_graph.py)

Create `NavigationGraph(Widget)`:

**State:**
- `_graph_data: dict` - cached result from `build_navigation_graph()`
- `_viewport: tuple[float, float, float]` - (pan_x, pan_y, zoom_level)
- `_selected_node: str | None` - currently highlighted node ID
- `_world_bounds: dict` - min/max x/y of all nodes
- `_node_list: list[str]` - sorted node IDs for Tab navigation
- `_show_help: bool` - help overlay toggle

**Rendering:**

Dynamic viewport rendering (only draw what's visible):

1. Calculate visible world bounds from viewport (pan + zoom + widget dimensions)
2. Filter nodes: only nodes whose `(x, y)` positions fall within visible bounds
3. For each visible node:
   - Convert world coordinates to screen coordinates: `screen_x = (world_x - pan_x) * zoom`
   - Draw box with entity name at screen position
4. For each edge where both source and target nodes are visible:
   - Draw line using orthogonal routing (horizontal then vertical)
5. Highlight selected node with different border style

**Zoom Detail Levels:**
- `zoom >= 0.7`: Full boxes with entity names
- `0.4 <= zoom < 0.7`: Single-char boxes (first letter only)
- `zoom < 0.4`: Dots only

**Box Rendering:**

Normal node:
```
┌─────────────┐
│   EmpJob    │
└─────────────┘
```

Selected node:
```
╔═════════════╗
║   EmpJob    ║
╚═════════════╝
```

Small (zoom < 0.7): `[E]`
Tiny (zoom < 0.4): `•`

**Edge Rendering:**

Simple orthogonal lines using box-drawing characters (`─ │ └ ┘ ┌ ┐ ├ ┤ ┬ ┴ ┼`)

Example:
```
┌─────────┐
│ Source  │───┐
└─────────┘   │
              ├──> ┌─────────┐
┌─────────┐   │    │ Target  │
│ Another │───┘    └─────────┘
└─────────┘
```

When edges cross: use `┼` for intersection

**Color Scheme:**
- Normal nodes: `$primary` border
- Selected node: `$accent` border
- Normal edges: dim gray (`[dim]`)
- Connected edges (when node selected): `$accent`
- Node text: `$text`

### Integration (app.py)

**Welcome Screen Update:**

Replace current welcome screen Static with:
```python
with TabPane("Welcome", id="welcome-tab"):
    yield Static("Stats content", id="welcome-stats")
    yield NavigationGraph(explorer, id="nav-graph")
```

Stats widget shows counts:
- Entities: 735
- Properties: 12,453
- Picklists: 127
- Custom fields: 2,341

**Message Handling:**

```python
@on(NavigationGraph.EntitySelected)
def on_graph_entity_selected(self, event: NavigationGraph.EntitySelected) -> None:
    """Handle node selection from graph - open entity tab."""
    self._open_entity_tab(event.entity_name)
```

## Controls

### Keyboard

- **Arrow keys**: Pan viewport (shift by 5 chars)
- **+/-**: Zoom in/out (cycle presets: 0.25, 0.5, 0.75, 1.0, 1.5)
- **Tab/Shift+Tab**: Navigate nodes (move selection)
- **Enter**: Open selected entity in tab
- **Home**: Reset viewport (center + zoom 1.0)
- **h**: Toggle help overlay

### Mouse

- **Click node**: Select and open entity tab
- **Scroll wheel**: Pan vertically (optional, if supported)

## Implementation Details

### Performance Optimizations

1. **Lazy graph computation**: Run `build_navigation_graph()` in `@work` thread on mount to avoid blocking UI
2. **Viewport culling**: Only render nodes/edges within visible bounds
3. **Spatial indexing**: Use dict keyed by `(row, col)` to detect character cell overlaps
4. **Caching**: Compute graph once, cache positions
5. **Loading indicator**: Show "Building graph..." during initial computation

### Edge Cases

- **No navigation properties**: Show message "No navigation relationships found in metadata"
- **1-2 entities only**: Still render, add note "Limited connectivity"
- **Graph computation fails**: Gracefully fall back to stats-only dashboard
- **Overlapping edges**: Use `┼` for crossings, accept some visual clutter at high zoom
- **Very large graphs (500+ nodes)**: Spring layout may be slow - show progress, cap iterations

### Error Handling

- Wrap NetworkX calls in try/except, log errors
- If layout fails, fall back to simple grid layout
- If rendering crashes, show error message in place of graph

## Dependencies

- **NetworkX**: Already used in the project for graph algorithms
- **No new external dependencies**: Use existing Textual widgets

## Testing Strategy

1. **Unit tests** for `build_navigation_graph()`:
   - Test with metadata containing 0, 1, 10, 100 connected entities
   - Verify node/edge counts match expected navigation properties
   - Check position bounds are reasonable

2. **Widget tests**:
   - Test viewport calculations (world → screen coordinates)
   - Test node filtering (visible bounds detection)
   - Test keyboard navigation (Tab cycles through nodes)
   - Test zoom level changes

3. **Manual testing**:
   - Load real SAP metadata (700+ entities)
   - Verify graph renders in <2 seconds
   - Test pan/zoom smoothness
   - Verify clicking nodes opens correct entity tabs

## Future Enhancements (Out of Scope)

- Edge labels showing navigation property names (toggle with key)
- Search/filter within graph (highlight matching nodes)
- Save/load viewport state (remember zoom/pan per metadata file)
- Export graph as image (SVG/PNG)
- Clustering/grouping by entity prefix (Emp*, Per*, etc.)
- Physics simulation (live spring-layout animation)

## Acceptance Criteria

- [ ] Welcome screen shows stats + interactive graph when no tabs open
- [ ] Graph includes only entities with navigation properties
- [ ] Force-directed layout positions nodes sensibly
- [ ] Pan (arrow keys) and zoom (+/-) work smoothly
- [ ] Clicking node opens entity in tab
- [ ] Tab/Enter keyboard navigation works
- [ ] Viewport only renders visible nodes (performant on 500+ entity graphs)
- [ ] Help overlay (h key) shows controls
- [ ] Home key resets to centered view
- [ ] Selected node has highlighted border
- [ ] Graph computation runs in background thread (non-blocking)

## Files to Create/Modify

**New Files:**
- `src/csdl_explore/widgets/nav_graph.py` - NavigationGraph widget
- `tests/test_nav_graph.py` - Widget tests

**Modified Files:**
- `src/csdl_explore/formatters.py` - Add `build_navigation_graph()`
- `src/csdl_explore/app.py` - Update welcome screen, add message handler
- `src/csdl_explore/widgets/__init__.py` - Export NavigationGraph
- `tests/test_formatters.py` - Add tests for graph builder

## Timeline Estimate

- Graph builder function: 2-3 hours
- NavigationGraph widget (rendering + interaction): 6-8 hours
- Integration + testing: 2-3 hours
- **Total: ~10-14 hours**

## Sign-off

Design validated through iterative Q&A:
- Graph structure: Connected entities only (nodes), nav properties (edges) ✓
- Layout: Force-directed (NetworkX spring_layout) ✓
- Interactivity: Pan, zoom, click, keyboard nav ✓
- Location: Welcome screen only, separate widget file ✓
- Rendering: Dynamic viewport (only visible nodes) ✓
- Visuals: Box-drawing ASCII art with zoom detail levels ✓
- Controls: Keyboard (arrows/+/-/Tab/Enter) + mouse click ✓

Ready for implementation.
