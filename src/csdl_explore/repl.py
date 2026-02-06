"""
Rich-based TUI for CSDL Metadata Explorer.

Provides an interactive terminal interface with nice formatting.
Optimized for varying terminal widths (adapts columns).
"""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.tree import Tree
from rich.prompt import Prompt
from rich import box

from .explorer import CSDLExplorer, SearchResult, EntityComparison
from .parser import EntityType, Property
from .formatters import (
    format_property_flags,
    format_search_result_row,
    sort_properties,
    group_entity_properties,
)
from .themes import PALETTES, DEFAULT_PALETTE


console = Console()

# Active Rich palette (role -> Rich markup color).
_palette = PALETTES[DEFAULT_PALETTE]


def set_palette(name: str) -> None:
    """Switch the active Rich color palette.

    Args:
        name: Palette name (``"terminal-vercel-green"`` or ``"classic"``).
    """
    global _palette
    _palette = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])


def _c(role: str) -> str:
    """Shorthand: return the Rich color string for a semantic role."""
    return _palette.get(role, "")


def get_column_count() -> int:
    """Determine optimal column count based on terminal width."""
    width = console.width
    if width >= 200:
        return 5
    elif width >= 160:
        return 4
    elif width >= 120:
        return 3
    elif width >= 80:
        return 2
    return 1


def print_welcome(explorer: CSDLExplorer):
    """Print welcome banner."""
    title = "CSDL Explorer"

    console.print()
    console.print(Panel(
        f"[bold {_c('primary')}]{title}[/]\n"
        f"[dim]Loaded {explorer.entity_count} entities[/]",
        box=box.ROUNDED,
    ))
    console.print()
    print_help_short()


def print_help_short():
    """Print short help."""
    console.print("[dim]Commands: entities, entity <name>, search <term>, custom <name>, "
                  "diff <e1> <e2>, nav <name>, emp, per, help, quit[/]")


def print_help():
    """Print full help."""
    table = Table(title="Commands", box=box.SIMPLE)
    table.add_column("Command", style=_c("primary"))
    table.add_column("Description")

    commands = [
        ("entities", "List all entity types (multi-column on wide terminals)"),
        ("entity <name>", "Show properties of an entity (shortcut: e)"),
        ("tree <name>", "Show entity as visual tree (shortcut: t)"),
        ("model", "Show data model overview with relationships"),
        ("search <term>", "Search for fields/entities (shortcut: s)"),
        ("custom <name>", "Show custom fields (customStringXX) (shortcut: c)"),
        ("nav <name>", "Show navigation properties"),
        ("diff <e1> <e2>", "Compare two entities"),
        ("path <name>", "Suggest JSON paths for an entity"),
        ("emp", "List Emp* entities"),
        ("per", "List Per* entities"),
        ("help", "Show this help"),
        ("quit", "Exit (shortcuts: q, exit)"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print(table)


def print_entities(entities: list[str]):
    """Print entity list with adaptive columns based on terminal width."""
    count = len(entities)
    col_count = get_column_count()

    if col_count == 1 or count <= 10:
        table = Table(title=f"Entities ({count})", box=box.SIMPLE)
        table.add_column("Entity Name", style=_c("entity"))
        for name in entities:
            table.add_row(name)
        console.print(table)
    else:
        console.print(f"\n[bold]Entities ({count})[/]\n")
        renderables = [Text(name, style=_c("entity")) for name in entities]
        console.print(Columns(renderables, equal=True, expand=True))


def _flags_markup(flags: list[tuple[str, str]]) -> str:
    """Convert flag tuples from ``format_property_flags`` into Rich markup."""
    parts = []
    for text, role in flags:
        color = _c(role)
        if role == "required":
            parts.append(f"[bold {color}]{text}[/]" if "+" in text else f"[{color}]{text}[/]")
        else:
            parts.append(f"[{color}]{text}[/]")
    return " ".join(parts)


def print_entity_details(entity: EntityType):
    """Print detailed entity information."""
    console.print()
    console.print(Panel(
        f"[bold {_c('primary')}]{entity.name}[/]" +
        (f"\n[dim]Base: {entity.base_type}[/]" if entity.base_type else "") +
        f"\n[dim]Keys: {', '.join(entity.keys)}[/]",
        title="Entity",
        box=box.ROUNDED,
    ))

    table = Table(title=f"Properties ({len(entity.properties)})", box=box.SIMPLE)
    table.add_column("Name", style=_c("property"))
    table.add_column("Type")
    table.add_column("Len", style="dim", justify="right")
    table.add_column("Flags", style="dim")
    table.add_column("Picklist", style=_c("picklist"))
    table.add_column("Info", style="dim")

    for prop in sort_properties(entity.properties, entity.keys):
        flags = format_property_flags(prop, entity.keys)
        info_parts = []
        if prop.label:
            info_parts.append(f'"{prop.label}"')

        table.add_row(
            prop.name,
            prop.type,
            prop.max_length or "",
            _flags_markup(flags),
            prop.picklist or "",
            " ".join(info_parts),
        )

    console.print(table)

    if entity.navigation:
        nav_table = Table(title=f"Navigation ({len(entity.navigation)})", box=box.SIMPLE)
        nav_table.add_column("Name", style=_c("property"))
        nav_table.add_column("Target", style=_c("nav"))

        for nav in sorted(entity.navigation.values(), key=lambda n: n.name):
            nav_table.add_row(nav.name, nav.target_entity or "[dim]?[/]")

        console.print(nav_table)


def print_search_results(results: list[SearchResult]):
    """Print search results."""
    if not results:
        console.print(f"[{_c('key')}]No results found.[/]")
        return

    table = Table(title=f"Search Results ({len(results)})", box=box.SIMPLE)
    table.add_column("Type", style="dim", width=8)
    table.add_column("Entity", style=_c("entity"))
    table.add_column("Match", style=_c("nav"))
    table.add_column("Details", style="dim")
    table.add_column("Picklist", style=_c("picklist"))

    for r in results:
        tag, entity, match, details, picklist = format_search_result_row(r)
        if tag:
            table.add_row(tag, entity, match, details, picklist)

    console.print(table)


def print_custom_fields(fields: list[Property], entity_name: str):
    """Print custom fields."""
    if not fields:
        console.print(f"[{_c('key')}]No custom fields found for {entity_name}[/]")
        return

    table = Table(title=f"Custom Fields - {entity_name} ({len(fields)})", box=box.SIMPLE)
    table.add_column("Name", style=_c("property"))
    table.add_column("Type")
    table.add_column("Len", style="dim", justify="right")
    table.add_column("Label", style="dim")
    table.add_column("Picklist", style=_c("picklist"))
    table.add_column("Flags", style="dim")
    table.add_column("Filter", style="dim")

    for prop in fields:
        filterable = f"[{_c('crud')}]Yes[/]" if prop.filterable else f"[{_c('no_filter')}]No[/]"
        flags = []
        if prop.creatable:
            flags.append(f"[{_c('crud')}]C[/]")
        if prop.updatable:
            flags.append(f"[{_c('crud')}]U[/]")
        if prop.upsertable:
            flags.append(f"[{_c('crud')}]UP[/]")
        table.add_row(
            prop.name,
            prop.type,
            prop.max_length or "",
            prop.label or "",
            prop.picklist or "",
            " ".join(flags),
            filterable,
        )

    console.print(table)


def print_comparison(comp: EntityComparison):
    """Print entity comparison."""
    console.print()
    console.print(Panel(
        f"[{_c('primary')}]{comp.entity1}[/] vs [{_c('primary')}]{comp.entity2}[/]",
        title="Entity Comparison",
        box=box.ROUNDED,
    ))

    if comp.only_in_entity1:
        table = Table(title=f"Only in {comp.entity1} ({len(comp.only_in_entity1)})", box=box.SIMPLE)
        table.add_column("Property", style=_c("property"))
        for p in comp.only_in_entity1[:25]:
            table.add_row(p)
        if len(comp.only_in_entity1) > 25:
            table.add_row(f"[dim]... and {len(comp.only_in_entity1) - 25} more[/]")
        console.print(table)

    if comp.only_in_entity2:
        table = Table(title=f"Only in {comp.entity2} ({len(comp.only_in_entity2)})", box=box.SIMPLE)
        table.add_column("Property", style=_c("nav"))
        for p in comp.only_in_entity2[:25]:
            table.add_row(p)
        if len(comp.only_in_entity2) > 25:
            table.add_row(f"[dim]... and {len(comp.only_in_entity2) - 25} more[/]")
        console.print(table)

    console.print(f"\n[dim]Common properties: {len(comp.common)}[/]")
    console.print(f"[dim]Navigation in {comp.entity1}: {', '.join(comp.nav1[:8])}{'...' if len(comp.nav1) > 8 else ''}[/]")
    console.print(f"[dim]Navigation in {comp.entity2}: {', '.join(comp.nav2[:8])}{'...' if len(comp.nav2) > 8 else ''}[/]")


def print_navigation(nav_props: list[dict], entity_name: str):
    """Print navigation properties."""
    if not nav_props:
        console.print(f"[{_c('key')}]No navigation properties for {entity_name}[/]")
        return

    table = Table(title=f"Navigation - {entity_name}", box=box.SIMPLE)
    table.add_column("Name", style=_c("property"))
    table.add_column("Target Entity", style=_c("nav"))

    for nav in nav_props:
        table.add_row(nav['name'], nav['target_entity'] or "[dim]?[/]")

    console.print(table)


def print_json_paths(paths: list[dict], entity_name: str):
    """Print suggested JSON paths."""
    if not paths:
        console.print(f"[{_c('key')}]No paths for {entity_name}[/]")
        return

    table = Table(title=f"JSON Paths - {entity_name}", box=box.SIMPLE)
    table.add_column("Path", style=_c("property"))
    table.add_column("Note", style="dim")

    for p in paths[:40]:
        note = p.get('note', '')
        table.add_row(p['path'], note)

    if len(paths) > 40:
        console.print(f"[dim]... and {len(paths) - 40} more[/]")

    console.print(table)


def print_not_found(name: str, suggestions: list[str]):
    """Print entity not found message with suggestions."""
    console.print(f"[{_c('no_filter')}]Entity '{name}' not found.[/]")
    if suggestions:
        console.print("\n[dim]Did you mean:[/]")
        for s in suggestions[:5]:
            console.print(f"  [{_c('primary')}]{s}[/]")


def print_entity_tree(entity: EntityType, explorer: Optional[CSDLExplorer] = None):
    """
    Print entity as a visual tree showing structure and relationships.

    This gives a "data model" feel showing:
    - Entity name at root
    - Keys branch
    - Properties branch (grouped by type)
    - Navigation branch with targets
    """
    groups = group_entity_properties(entity)

    tree = Tree(f"[bold {_c('primary')}]{entity.name}[/]")

    # Keys
    if groups["keys"]:
        keys_branch = tree.add(f"[{_c('key')}]Keys[/]")
        for prop in groups["keys"]:
            keys_branch.add(f"[{_c('property')}]{prop.name}[/] [dim]{prop.type}[/]")

    # Standard properties
    if groups["standard"]:
        props_branch = tree.add(f"[{_c('nav')}]Properties[/] ({len(groups['standard'])})")
        for prop in groups["standard"][:15]:
            label_hint = f' [dim]"{prop.label}"[/]' if prop.label else ""
            props_branch.add(f"[{_c('property')}]{prop.name}[/] [dim]{prop.type}[/]{label_hint}")
        if len(groups["standard"]) > 15:
            props_branch.add(f"[dim]... and {len(groups['standard']) - 15} more[/]")

    # Lookups
    if groups["lookups"]:
        nav_refs_branch = tree.add(f"[{_c('picklist')}]Lookups[/] ({len(groups['lookups'])})")
        for prop, nav_name, target in groups["lookups"][:10]:
            picklist_hint = f' [{_c("picklist")}]picklist:{prop.picklist}[/]' if prop.picklist else ""
            nav_refs_branch.add(
                f"[{_c('property')}]{prop.name}[/] -> [{_c('nav')}]{target}[/]{picklist_hint}"
            )
        if len(groups["lookups"]) > 10:
            nav_refs_branch.add(f"[dim]... and {len(groups['lookups']) - 10} more[/]")

    # Custom fields
    if groups["custom"]:
        custom_branch = tree.add(f"[{_c('key')}]Custom Fields[/] ({len(groups['custom'])})")
        for prop in groups["custom"][:10]:
            label_hint = f' [dim]"{prop.label}"[/]' if prop.label else ""
            custom_branch.add(f"[{_c('property')}]{prop.name}[/] [dim]{prop.type}[/]{label_hint}")
        if len(groups["custom"]) > 10:
            custom_branch.add(f"[dim]... and {len(groups['custom']) - 10} more[/]")

    # Other navigation
    if groups["other_nav"]:
        nav_branch = tree.add(f"[{_c('nav')}]Navigation[/] ({len(groups['other_nav'])})")
        for nav in groups["other_nav"][:10]:
            target = nav.target_entity or "?"
            nav_branch.add(f"[{_c('property')}]{nav.name}[/] -> [{_c('nav')}]{target}[/]")
        if len(groups["other_nav"]) > 10:
            nav_branch.add(f"[dim]... and {len(groups['other_nav']) - 10} more[/]")

    console.print()
    console.print(tree)


def print_data_model(explorer: CSDLExplorer, root_entities: list[str] = None):
    """
    Print a visual overview of the data model.

    Shows key entities and their relationships.
    """
    if root_entities is None:
        all_entities = explorer.list_entities()
        root_entities = all_entities[:4] if all_entities else []

    tree = Tree("[bold]Data Model[/]")

    for entity_name in root_entities:
        entity = explorer.get_entity(entity_name)
        if not entity:
            continue

        entity_branch = tree.add(f"[{_c('primary')}]{entity_name}[/]")

        navs = sorted(entity.navigation.values(), key=lambda n: n.name)[:5]
        for nav in navs:
            if nav.target_entity:
                entity_branch.add(f"-> [{_c('nav')}]{nav.target_entity}[/] [dim]({nav.name})[/]")

        if len(entity.navigation) > 5:
            entity_branch.add(f"[dim]... +{len(entity.navigation) - 5} more[/]")

    console.print()
    console.print(tree)


def run_interactive(explorer: CSDLExplorer):
    """Run interactive TUI session."""
    print_welcome(explorer)

    while True:
        try:
            user_input = Prompt.ask(f"\n[bold {_c('primary')}]csdl>[/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/]")
            break

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ('quit', 'exit', 'q'):
                console.print("[dim]Goodbye![/]")
                break

            elif cmd == 'help':
                print_help()

            elif cmd == 'entities':
                print_entities(explorer.list_entities())

            elif cmd in ('entity', 'e'):
                if not args:
                    console.print(f"[{_c('key')}]Usage: entity <name>[/]")
                else:
                    entity = explorer.get_entity(args[0])
                    if entity:
                        print_entity_details(entity)
                    else:
                        suggestions = [r.entity for r in explorer.search(args[0]) if r.type == 'entity'][:5]
                        print_not_found(args[0], suggestions)

            elif cmd in ('search', 's'):
                if not args:
                    console.print(f"[{_c('key')}]Usage: search <term>[/]")
                else:
                    results = explorer.search(' '.join(args))
                    print_search_results(results)

            elif cmd in ('custom', 'c'):
                if not args:
                    console.print(f"[{_c('key')}]Usage: custom <entity>[/]")
                else:
                    fields = explorer.get_custom_fields(args[0])
                    print_custom_fields(fields, args[0])

            elif cmd == 'nav':
                if not args:
                    console.print(f"[{_c('key')}]Usage: nav <entity>[/]")
                else:
                    nav_props = explorer.get_navigation_properties(args[0])
                    print_navigation(nav_props, args[0])

            elif cmd == 'diff':
                if len(args) < 2:
                    console.print(f"[{_c('key')}]Usage: diff <entity1> <entity2>[/]")
                else:
                    comp = explorer.compare_entities(args[0], args[1])
                    print_comparison(comp)

            elif cmd in ('path', 'paths'):
                if not args:
                    console.print(f"[{_c('key')}]Usage: path <entity>[/]")
                else:
                    paths = explorer.suggest_json_paths(args[0])
                    print_json_paths(paths, args[0])

            elif cmd == 'emp':
                print_entities(explorer.get_emp_entities())

            elif cmd == 'per':
                print_entities(explorer.get_per_entities())

            elif cmd in ('tree', 't'):
                if not args:
                    console.print(f"[{_c('key')}]Usage: tree <entity>[/]")
                else:
                    entity = explorer.get_entity(args[0])
                    if entity:
                        print_entity_tree(entity, explorer)
                    else:
                        suggestions = [r.entity for r in explorer.search(args[0]) if r.type == 'entity'][:5]
                        print_not_found(args[0], suggestions)

            elif cmd == 'model':
                if args:
                    print_data_model(explorer, args)
                else:
                    print_data_model(explorer)

            else:
                # Try as entity name shortcut
                entity = explorer.get_entity(cmd)
                if entity:
                    print_entity_details(entity)
                else:
                    console.print(f"[{_c('no_filter')}]Unknown command: {cmd}[/]. Type 'help' for commands.")

        except Exception as e:
            console.print(f"[{_c('no_filter')}]Error: {e}[/]")
