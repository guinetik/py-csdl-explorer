"""
CLI entry point for CSDL Explorer.
"""

import sys
from pathlib import Path

from rich.console import Console

from .explorer import CSDLExplorer
from . import tui


console = Console()

HELP_TEXT = """
[bold cyan]CSDL Explorer[/] - OData Metadata Explorer

Explore OData $metadata to discover entities, fields, and navigation properties.

[bold]Usage:[/]
    csdl-explore <metadata.xml> [command] [args]
    csdl-explore --file <metadata.xml> [command] [args]

[bold]Options:[/]
    --file <file>      Path to metadata XML file
    --tui              Launch full Textual TUI (requires: pip install csdl-explore[tui])

[bold]Commands:[/]
    interactive        Start interactive mode (default, Rich-based)
    tui                Start full TUI app (Textual-based, same as --tui)
    entities           List all entity types
    entity <name>      Show properties of an entity
    tree <name>        Show entity as visual tree with relationships
    model [entities]   Show data model overview
    search <term>      Search for fields/entities matching term
    custom <name>      Show custom fields (customStringXX)
    nav <name>         Show navigation properties
    diff <e1> <e2>     Compare two entities
    path <name>        Suggest JSON paths
    emp                List Emp* entities (SAP SuccessFactors)
    per                List Per* entities (SAP SuccessFactors)

[bold]Examples:[/]
    # Start interactive explorer
    csdl-explore metadata.xml

    # Launch full TUI with tree navigation
    csdl-explore metadata.xml --tui

    # Search for fields (headless - great for scripts/AI)
    csdl-explore metadata.xml search contract

    # Show entity as visual tree
    csdl-explore metadata.xml tree EmpJob

    # Show data model relationships
    csdl-explore metadata.xml model EmpJob PerPerson

    # Compare two similar entities
    csdl-explore metadata.xml diff EmpCompensation EmpPayCompRecurring
"""


def main():
    """Main CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help', 'help'):
        console.print(HELP_TEXT)
        sys.exit(0)

    # Parse arguments
    metadata_file = None
    use_textual_tui = False
    command = 'interactive'
    cmd_args = []

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == '--file':
            if i + 1 >= len(args):
                console.print("[red]Error: --file requires a path[/]")
                sys.exit(1)
            metadata_file = Path(args[i + 1])
            i += 2

        elif arg == '--tui':
            use_textual_tui = True
            i += 1

        elif arg.startswith('--'):
            console.print(f"[red]Unknown option: {arg}[/]")
            sys.exit(1)

        else:
            # First non-option could be a metadata file or command
            if metadata_file is None and arg.endswith('.xml'):
                metadata_file = Path(arg)
                i += 1
            else:
                # Rest are command and args
                command = arg
                cmd_args = args[i + 1:]
                break

    # "tui" command is same as --tui flag
    if command == 'tui':
        use_textual_tui = True
        command = 'interactive'

    if metadata_file:
        run_file_mode(metadata_file, command, cmd_args, use_textual_tui)
    else:
        console.print(HELP_TEXT)
        sys.exit(1)


def run_file_mode(metadata_file: Path, command: str, cmd_args: list[str], use_textual_tui: bool = False):
    """Run using metadata file directly."""
    metadata_file = metadata_file.resolve()

    if not metadata_file.exists():
        console.print(f"[red]Error: File not found: {metadata_file}[/]")
        sys.exit(1)

    explorer = CSDLExplorer.from_file(metadata_file)
    console.print(f"[dim]Loaded {explorer.entity_count} entities from {metadata_file.name}[/]")

    if command == 'interactive':
        if use_textual_tui:
            run_textual_app(explorer)
        else:
            tui.run_interactive(explorer)
    else:
        run_command(explorer, command, cmd_args)


def run_textual_app(explorer: CSDLExplorer):
    """Launch the Textual TUI application."""
    try:
        from .app import run_app
        run_app(explorer)
    except ImportError:
        console.print("[red]Error: Textual not installed.[/]")
        console.print("\n[dim]Install the TUI extra:[/]")
        console.print("  pip install csdl-explore\\[tui]")
        sys.exit(1)


def run_command(explorer: CSDLExplorer, command: str, args: list[str]):
    """Execute a single CLI command and print results to stdout.

    Args:
        explorer: Initialised CSDL explorer instance.
        command: Command name (e.g. ``"entity"``, ``"search"``).
        args: Positional arguments for the command.
    """
    try:
        if command == 'entities':
            tui.print_entities(explorer.list_entities())

        elif command in ('entity', 'e'):
            if not args:
                console.print("[yellow]Usage: entity <name>[/]")
                sys.exit(1)
            entity = explorer.get_entity(args[0])
            if entity:
                tui.print_entity_details(entity)
            else:
                suggestions = [r.entity for r in explorer.search(args[0]) if r.type == 'entity'][:5]
                tui.print_not_found(args[0], suggestions)
                sys.exit(1)

        elif command in ('search', 's'):
            if not args:
                console.print("[yellow]Usage: search <term>[/]")
                sys.exit(1)
            results = explorer.search(' '.join(args))
            tui.print_search_results(results)

        elif command in ('custom', 'c'):
            if not args:
                console.print("[yellow]Usage: custom <entity>[/]")
                sys.exit(1)
            fields = explorer.get_custom_fields(args[0])
            tui.print_custom_fields(fields, args[0])

        elif command == 'nav':
            if not args:
                console.print("[yellow]Usage: nav <entity>[/]")
                sys.exit(1)
            nav_props = explorer.get_navigation_properties(args[0])
            tui.print_navigation(nav_props, args[0])

        elif command == 'diff':
            if len(args) < 2:
                console.print("[yellow]Usage: diff <entity1> <entity2>[/]")
                sys.exit(1)
            comp = explorer.compare_entities(args[0], args[1])
            tui.print_comparison(comp)

        elif command in ('path', 'paths'):
            if not args:
                console.print("[yellow]Usage: path <entity>[/]")
                sys.exit(1)
            paths = explorer.suggest_json_paths(args[0])
            tui.print_json_paths(paths, args[0])

        elif command == 'emp':
            tui.print_entities(explorer.get_emp_entities())

        elif command == 'per':
            tui.print_entities(explorer.get_per_entities())

        elif command in ('tree', 't'):
            if not args:
                console.print("[yellow]Usage: tree <entity>[/]")
                sys.exit(1)
            entity = explorer.get_entity(args[0])
            if entity:
                tui.print_entity_tree(entity, explorer)
            else:
                suggestions = [r.entity for r in explorer.search(args[0]) if r.type == 'entity'][:5]
                tui.print_not_found(args[0], suggestions)
                sys.exit(1)

        elif command == 'model':
            if args:
                tui.print_data_model(explorer, args)
            else:
                tui.print_data_model(explorer)

        else:
            console.print(f"[red]Unknown command: {command}[/]")
            console.print("[dim]Run with --help for usage[/]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
