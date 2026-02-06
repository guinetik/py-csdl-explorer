"""
Shared presentation logic for CSDL Explorer.

Pure data transformations consumed by both the Rich REPL (tui.py) and
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
