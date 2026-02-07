"""
Shared presentation logic for CSDL Explorer.

Pure data transformations consumed by both the Rich REPL (repl.py) and
Textual TUI (app.py).  These functions return plain data (strings, lists
of tuples, dicts) and never import any UI framework.
"""

from .parser import EntityType, Property


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
