"""
Shared presentation logic for CSDL Explorer.

Pure data transformations consumed by both the Rich REPL (repl.py) and
Textual TUI (app.py).  These functions return plain data (strings, lists
of tuples, dicts) and never import any UI framework.
"""

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import networkx as nx

from .parser import EntityType, Property

if TYPE_CHECKING:
    from .explorer import CSDLExplorer

# SAP OData date pattern: /Date(1234567890)/ or /Date(1234567890+0000)/
_SAP_DATE_RE = re.compile(r"^/Date\((-?\d+)([+-]\d{4})?\)/$")


def format_property_flags(prop: Property, entity_keys: list[str]) -> list[tuple[str, str]]:
    """Return property flag badges as (flag_text, semantic_role) tuples.

    Args:
        prop: The property to inspect.
        entity_keys: List of key property names for the owning entity.

    Returns:
        List of (flag_text, role) pairs. Roles are: ``"key"``, ``"required"``,
        ``"crud"``, ``"hidden"``, ``"no_filter"``.
    """
    flags: list[tuple[str, str]] = []
    if prop.name in entity_keys:
        flags.append(("KEY", "key"))
    if prop.creatable and prop.required:
        flags.append(("REQ+C", "required"))
    elif prop.required:
        flags.append(("REQ", "required"))
    if prop.creatable and prop.name not in entity_keys:
        flags.append(("C", "crud"))
    if prop.updatable:
        flags.append(("U", "crud"))
    if prop.upsertable:
        flags.append(("UP", "crud"))
    if not prop.visible:
        flags.append(("hidden", "hidden"))
    if not prop.filterable:
        flags.append(("!filter", "no_filter"))
    return flags


def format_search_result_row(result) -> tuple[str, str, str, str, str]:
    """Convert a ``SearchResult`` into a plain 5-column tuple.

    Args:
        result: A ``SearchResult`` instance from ``explorer.py``.

    Returns:
        ``(tag, entity, match, details, picklist)`` tuple of strings.
    """
    picklist = result.picklist or ""
    if result.type == "entity":
        return ("ENTITY", result.entity, result.match, "", "")
    elif result.type in ("property", "picklist"):
        details = result.prop_type or ""
        if result.label:
            details += f' "{result.label}"'
        tag = "PICK" if result.type == "picklist" else "PROP"
        return (tag, result.entity, f".{result.property}", details, picklist)
    elif result.type == "property_label":
        return ("LABEL", result.entity, f".{result.property}", f'"{result.label}"', picklist)
    elif result.type == "navigation":
        return ("NAV", result.entity, f".{result.navigation}", "", "")
    return ("", result.entity, "", "", "")


def sort_properties(properties: dict[str, Property], entity_keys: list[str]) -> list[Property]:
    """Sort properties: keys first, then alphabetical.

    Args:
        properties: Dict mapping property names to Property objects.
        entity_keys: List of key property names.

    Returns:
        Sorted list of Property objects.
    """
    return sorted(
        properties.values(),
        key=lambda p: (p.name not in entity_keys, p.name.lower()),
    )


def group_entity_properties(entity: EntityType) -> dict[str, list]:
    """Group entity properties into display categories.

    Categories: ``keys``, ``standard``, ``custom``, ``lookups``, ``other_nav``.
    Each lookup entry is a ``(prop, nav_name, target)`` tuple.

    Args:
        entity: The entity type to group.

    Returns:
        Dict with keys ``"keys"``, ``"standard"``, ``"custom"``, ``"lookups"``,
        ``"other_nav"``.
    """
    keys: list[Property] = []
    custom: list[Property] = []
    lookups: list[tuple[Property, str, str]] = []
    standard: list[Property] = []

    for prop in entity.properties.values():
        if prop.name in entity.keys:
            keys.append(prop)
        elif prop.name.startswith("custom"):
            custom.append(prop)
        elif f"{prop.name}Nav" in entity.navigation:
            nav_name = f"{prop.name}Nav"
            nav = entity.navigation.get(nav_name)
            target = nav.target_entity if nav else "?"
            lookups.append((prop, nav_name, target))
        else:
            standard.append(prop)

    # Navigation properties that aren't property lookups
    other_nav = [
        nav
        for nav in entity.navigation.values()
        if not nav.name.endswith("Nav") or nav.name[:-3] not in entity.properties
    ]

    return {
        "keys": sorted(keys, key=lambda p: p.name),
        "standard": sorted(standard, key=lambda p: p.name),
        "custom": sorted(custom, key=lambda p: p.name),
        "lookups": sorted(lookups, key=lambda t: t[0].name),
        "other_nav": sorted(other_nav, key=lambda n: n.name),
    }


def format_flag_check(val: bool) -> str:
    """Return a checkmark for truthy values, empty string otherwise.

    Args:
        val: Boolean value to represent.

    Returns:
        ``"\u2713"`` or ``""``.
    """
    return "\u2713" if val else ""


def detect_syntax_lexer(content_type: str) -> str:
    """Map a Content-Type header to a Rich Syntax lexer name.

    Args:
        content_type: HTTP Content-Type header value.

    Returns:
        Lexer name string (``"json"``, ``"xml"``, etc.).
    """
    ct = content_type.lower()
    if "xml" in ct:
        return "xml"
    return "json"


def detect_file_extension(content_type: str) -> str:
    """Map a Content-Type header to a file extension.

    Args:
        content_type: HTTP Content-Type header value.

    Returns:
        File extension string without dot (``"json"`` or ``"xml"``).
    """
    ct = content_type.lower()
    if "xml" in ct:
        return "xml"
    return "json"


def build_tree_structure(data, max_depth: int = 10) -> list[tuple[str, str, list]]:
    """Convert nested dicts/lists into a renderable tree structure.

    Each node is a ``(label, type_hint, children)`` tuple where *children*
    is a list of the same shape.  ``__metadata`` keys are skipped.
    Lists are capped at 10 displayed items.

    Args:
        data: Parsed JSON data (dict, list, or primitive).
        max_depth: Maximum recursion depth.

    Returns:
        List of ``(label, type_hint, children)`` tuples.
    """

    def _build(value, depth: int) -> list[tuple[str, str, list]]:
        if depth <= 0:
            return [("...", "max depth", [])]

        if isinstance(value, dict):
            nodes = []
            for k, v in value.items():
                if k == "__metadata":
                    continue
                children = _build(v, depth - 1)
                type_hint = _type_hint(v)
                nodes.append((str(k), type_hint, children))
            return nodes

        if isinstance(value, list):
            nodes = []
            shown = value[:10]
            for i, item in enumerate(shown):
                children = _build(item, depth - 1)
                type_hint = _type_hint(item)
                nodes.append((f"[{i}]", type_hint, children))
            if len(value) > 10:
                nodes.append((f"… {len(value) - 10} more", "", []))
            return nodes

        # Primitive leaf
        return []

    def _type_hint(value) -> str:
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return f"array[{len(value)}]"
        if value is None:
            return "null"
        return repr(value)

    if isinstance(data, list):
        root_nodes = []
        shown = data[:10]
        for i, item in enumerate(shown):
            children = _build(item, max_depth - 1)
            type_hint = _type_hint(item)
            root_nodes.append((f"[{i}]", type_hint, children))
        if len(data) > 10:
            root_nodes.append((f"… {len(data) - 10} more", "", []))
        return root_nodes

    if isinstance(data, dict):
        return _build(data, max_depth)

    return [(_type_hint(data), "", [])]


def fuzzy_match(pattern: str, text: str) -> bool:
    """Check if all characters in *pattern* appear in order in *text*.

    Args:
        pattern: Lowercase search pattern.
        text: Lowercase text to match against.

    Returns:
        ``True`` if every character of *pattern* appears sequentially in *text*.
    """
    it = iter(text)
    return all(c in it for c in pattern)


def build_odata_url(base_url: str, entity_name: str, params: dict[str, str]) -> str:
    """Build an OData URL from base URL, entity name, and query params.

    Always appends ``$format=json`` unless already present.

    Args:
        base_url: API base URL (trailing slash stripped).
        entity_name: OData entity set name.
        params: Query parameters dict.

    Returns:
        Full URL string.
    """
    if not base_url:
        base_url = "https://api.sap.com/odata/v2"
    params_with_format = dict(params)
    params_with_format.setdefault("$format", "json")
    param_str = "&".join(f"{k}={v}" for k, v in params_with_format.items())
    return f"{base_url.rstrip('/')}/{entity_name}?{param_str}"


def build_odata_query_params(
    *,
    selected: list[str],
    filter_expr: str,
    orderby_prop: str,
    orderby_dir: str,
    expanded: list[str],
    top: str,
    asof_date: str = "",
    from_date: str = "",
    to_date: str = "",
) -> dict[str, str]:
    """Build OData query parameters from individual field values.

    Only includes parameters that have non-empty values.

    Args:
        selected: List of selected property names for ``$select``.
        filter_expr: Raw ``$filter`` expression.
        orderby_prop: Property name for ``$orderby``.
        orderby_dir: Sort direction (``"asc"`` or ``"desc"``).
        expanded: List of navigation property names for ``$expand``.
        top: Number of results to return.
        asof_date: As-of date for point-in-time queries.
        from_date: Start date for date range queries.
        to_date: End date for date range queries.

    Returns:
        Dict of OData query parameter names to values.
    """
    params: dict[str, str] = {}
    if selected:
        params["$select"] = ",".join(selected)
    if filter_expr:
        params["$filter"] = filter_expr
    if orderby_prop:
        params["$orderby"] = f"{orderby_prop} {orderby_dir}"
    if expanded:
        params["$expand"] = ",".join(expanded)
    params["$top"] = top or "20"

    # Date parameters are mutually exclusive: asof_date OR (from_date + to_date)
    if asof_date:
        params["$asOfDate"] = asof_date
    elif from_date and to_date:
        params["$fromDate"] = from_date
        params["$toDate"] = to_date
    elif from_date:
        params["$fromDate"] = from_date
    elif to_date:
        params["$toDate"] = to_date

    return params


def format_property_table_row(
    prop: Property,
    *,
    keys: list[str],
    accent_color: str,
) -> tuple:
    """Format a property into a 12-column table row tuple.

    Args:
        prop: The property to format.
        keys: Entity key property names.
        accent_color: Hex color for key name markup.

    Returns:
        12-element tuple of display strings.
    """
    is_key = prop.name in keys
    return (
        f"[{accent_color}]{prop.name}[/]" if is_key else prop.name,
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


def compute_picklist_impact(
    picklist_data: dict[str, list[Property]],
) -> dict:
    """Compute impact analysis stats for a picklist.

    Args:
        picklist_data: Mapping of entity name to list of properties using the picklist.

    Returns:
        Dict with ``required_count``, ``create_entity_count``,
        ``required_props`` (list of (entity, prop) tuples),
        ``create_entities`` (set of entity names).
    """
    required_props = []
    create_entities = set()
    for entity_name, props in picklist_data.items():
        for prop in props:
            if prop.required:
                required_props.append((entity_name, prop))
            if prop.creatable:
                create_entities.add(entity_name)
    return {
        "required_count": len(required_props),
        "create_entity_count": len(create_entities),
        "required_props": required_props,
        "create_entities": create_entities,
    }


def format_odata_value(value: str) -> str:
    """Format an OData cell value for display.

    Converts SAP ``/Date(timestamp)/`` strings to ``YYYY-MM-DD``.
    All other values pass through unchanged.

    Args:
        value: Raw string value from the OData response.

    Returns:
        Formatted display string.
    """
    m = _SAP_DATE_RE.match(value)
    if m:
        ts_ms = int(m.group(1))
        # Use epoch + timedelta to avoid Windows negative-timestamp errors
        from datetime import timedelta
        dt = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=ts_ms)
        return dt.strftime("%Y-%m-%d")
    return value


def build_navigation_graph(explorer: "CSDLExplorer") -> dict:
    """Build navigation graph structure from metadata.

    Creates a directed graph where nodes are entities and edges are navigation
    properties. Only includes entities that have at least one navigation property
    (incoming or outgoing). Uses NetworkX spring_layout for positioning.

    Args:
        explorer: The CSDL explorer instance containing metadata.

    Returns:
        Dict with:
        - ``nodes``: List of dicts with ``{id, name, incoming_count, outgoing_count}``
        - ``edges``: List of dicts with ``{source, target, nav_name}``
        - ``positions``: Dict mapping entity name to ``(x, y)`` coordinates
        - ``bounds``: Dict with ``{min_x, max_x, min_y, max_y}``
    """
    # Build directed graph
    graph = nx.DiGraph()

    # First pass: identify all entities with navigation properties
    entities_with_navs = set()
    nav_edges = []

    for entity_name, entity in explorer.entities.items():
        # Check if entity has any outgoing navigation
        if entity.navigation:
            entities_with_navs.add(entity_name)
            for nav in entity.navigation.values():
                if nav.target_entity:
                    entities_with_navs.add(nav.target_entity)
                    nav_edges.append((entity_name, nav.target_entity, nav.name))

    # Add nodes to graph
    for entity_name in entities_with_navs:
        graph.add_node(entity_name)

    # Add edges to graph
    for source, target, nav_name in nav_edges:
        if source in graph and target in graph:
            graph.add_edge(source, target, nav_name=nav_name)

    # If no connected entities, return empty graph
    if not graph.nodes():
        return {
            "nodes": [],
            "edges": [],
            "positions": {},
            "bounds": {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0},
        }

    # Compute layout using spring/force-directed algorithm
    # For large graphs, increase k to prevent overlapping
    positions = nx.spring_layout(
        graph,
        k=4.0,  # Optimal distance between nodes (increased for large graphs)
        iterations=100,  # More iterations for better convergence
        scale=2.0,  # Scale layout to spread nodes further
        seed=42,  # Reproducible layouts
    )

    # Build node list with metadata
    nodes = []
    for node_id in graph.nodes():
        incoming_count = graph.in_degree(node_id)
        outgoing_count = graph.out_degree(node_id)
        nodes.append({
            "id": node_id,
            "name": node_id,
            "incoming_count": incoming_count,
            "outgoing_count": outgoing_count,
        })

    # Build edge list
    edges = []
    for source, target, data in graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "nav_name": data.get("nav_name", ""),
        })

    # Convert positions to plain Python floats (NetworkX returns numpy types)
    positions = {k: (float(v[0]), float(v[1])) for k, v in positions.items()}

    # Calculate bounds
    if positions:
        x_coords = [pos[0] for pos in positions.values()]
        y_coords = [pos[1] for pos in positions.values()]
        bounds = {
            "min_x": float(min(x_coords)),
            "max_x": float(max(x_coords)),
            "min_y": float(min(y_coords)),
            "max_y": float(max(y_coords)),
        }
    else:
        bounds = {"min_x": 0.0, "max_x": 0.0, "min_y": 0.0, "max_y": 0.0}

    return {
        "nodes": nodes,
        "edges": edges,
        "positions": positions,
        "bounds": bounds,
    }
