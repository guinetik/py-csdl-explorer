"""
CLI entry point for CSDL Explorer.
"""

import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console

from .explorer import CSDLExplorer
from . import repl


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
    --base-url <url>   OData service base URL (overrides .env)
    --auth-type <type> Auth type: none, bearer, basic, oauth2
    --bearer-token <t> Bearer token for authentication
    --username <user>  Username for basic auth
    --password <pass>  Password for basic auth

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
    picklists          List all picklist names and their entities (JSON)
    picklist <name>    Fetch picklist values as JSON (requires connection)
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

    # Fetch picklist values (reads connection from .env)
    csdl-explore metadata.xml picklist ecJobCode

    # Fetch picklist values with inline connection
    csdl-explore metadata.xml --base-url https://api.example.com/odata/v2 --auth-type bearer --bearer-token TOKEN picklist ecJobCode
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
    cli_env = {}

    # Connection flags that take a value → env key mapping
    _CONN_FLAGS = {
        '--base-url': 'SAP_BASE_URL',
        '--auth-type': 'SAP_AUTH_TYPE',
        '--bearer-token': 'SAP_BEARER_TOKEN',
        '--username': 'SAP_USERNAME',
        '--password': 'SAP_PASSWORD',
    }

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

        elif arg in _CONN_FLAGS:
            if i + 1 >= len(args):
                console.print(f"[red]Error: {arg} requires a value[/]")
                sys.exit(1)
            cli_env[_CONN_FLAGS[arg]] = args[i + 1]
            i += 2

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
        run_file_mode(metadata_file, command, cmd_args, use_textual_tui, cli_env)
    else:
        console.print(HELP_TEXT)
        sys.exit(1)


def run_file_mode(
    metadata_file: Path,
    command: str,
    cmd_args: list[str],
    use_textual_tui: bool = False,
    cli_env: dict[str, str] | None = None,
):
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
            repl.run_interactive(explorer)
    else:
        run_command(explorer, command, cmd_args, metadata_file, cli_env or {})


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


def run_command(
    explorer: CSDLExplorer,
    command: str,
    args: list[str],
    metadata_file: Path | None = None,
    cli_env: dict[str, str] | None = None,
):
    """Execute a single CLI command and print results to stdout.

    Args:
        explorer: Initialised CSDL explorer instance.
        command: Command name (e.g. ``"entity"``, ``"search"``).
        args: Positional arguments for the command.
        metadata_file: Resolved path to the metadata XML file.
        cli_env: Connection overrides from CLI flags (``SAP_*`` keys).
    """
    try:
        if command == 'entities':
            repl.print_entities(explorer.list_entities())

        elif command in ('entity', 'e'):
            if not args:
                console.print("[yellow]Usage: entity <name>[/]")
                sys.exit(1)
            entity = explorer.get_entity(args[0])
            if entity:
                repl.print_entity_details(entity)
            else:
                suggestions = [r.entity for r in explorer.search(args[0]) if r.type == 'entity'][:5]
                repl.print_not_found(args[0], suggestions)
                sys.exit(1)

        elif command in ('search', 's'):
            if not args:
                console.print("[yellow]Usage: search <term>[/]")
                sys.exit(1)
            results = explorer.search(' '.join(args))
            repl.print_search_results(results)

        elif command in ('custom', 'c'):
            if not args:
                console.print("[yellow]Usage: custom <entity>[/]")
                sys.exit(1)
            fields = explorer.get_custom_fields(args[0])
            repl.print_custom_fields(fields, args[0])

        elif command == 'nav':
            if not args:
                console.print("[yellow]Usage: nav <entity>[/]")
                sys.exit(1)
            nav_props = explorer.get_navigation_properties(args[0])
            repl.print_navigation(nav_props, args[0])

        elif command == 'diff':
            if len(args) < 2:
                console.print("[yellow]Usage: diff <entity1> <entity2>[/]")
                sys.exit(1)
            comp = explorer.compare_entities(args[0], args[1])
            repl.print_comparison(comp)

        elif command in ('path', 'paths'):
            if not args:
                console.print("[yellow]Usage: path <entity>[/]")
                sys.exit(1)
            paths = explorer.suggest_json_paths(args[0])
            repl.print_json_paths(paths, args[0])

        elif command == 'emp':
            repl.print_entities(explorer.get_emp_entities())

        elif command == 'per':
            repl.print_entities(explorer.get_per_entities())

        elif command in ('tree', 't'):
            if not args:
                console.print("[yellow]Usage: tree <entity>[/]")
                sys.exit(1)
            entity = explorer.get_entity(args[0])
            if entity:
                repl.print_entity_tree(entity, explorer)
            else:
                suggestions = [r.entity for r in explorer.search(args[0]) if r.type == 'entity'][:5]
                repl.print_not_found(args[0], suggestions)
                sys.exit(1)

        elif command == 'model':
            if args:
                repl.print_data_model(explorer, args)
            else:
                repl.print_data_model(explorer)

        elif command == 'picklists':
            usage = explorer.get_picklist_usage()
            print(json.dumps(usage, indent=2, ensure_ascii=False))

        elif command in ('picklist', 'pk'):
            if not args:
                console.print("[yellow]Usage: picklist <name>[/]")
                sys.exit(1)
            run_picklist_command(args[0], metadata_file, cli_env or {})

        else:
            console.print(f"[red]Unknown command: {command}[/]")
            console.print("[dim]Run with --help for usage[/]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)


def run_picklist_command(
    picklist_name: str,
    metadata_file: Path | None,
    cli_env: dict[str, str],
):
    """Fetch picklist values from OData API and print JSON to stdout.

    Builds a connection from the ``.env`` file alongside the metadata XML
    (if it exists), with CLI flag overrides applied on top.

    Args:
        picklist_name: Picklist identifier (e.g. ``"ecJobCode"``).
        metadata_file: Resolved path to the metadata XML file.
        cli_env: Connection overrides from CLI flags (``SAP_*`` keys).
    """
    from .sap_client import SAPConnection, SAPClient, load_env_file

    # Build env dict: .env file as base, CLI flags as overrides
    env = {}
    if metadata_file:
        env_path = metadata_file.with_suffix('.env')
        if env_path.exists():
            env = load_env_file(env_path)
    env.update(cli_env)

    connection = SAPConnection.from_env_dict(env)
    if not connection.base_url:
        console.print(
            "[red]Error: No base URL configured.[/]\n"
            "[dim]Provide --base-url or create a .env file alongside your metadata XML "
            "with SAP_BASE_URL=...[/]"
        )
        sys.exit(1)

    async def _fetch():
        client = SAPClient(connection)
        try:
            await client.authenticate()
            return await client.get_picklist_values(picklist_name)
        finally:
            await client.close()

    try:
        results = asyncio.run(_fetch())
    except Exception as e:
        console.print(f"[red]Error fetching picklist: {e}[/]")
        sys.exit(1)

    print(json.dumps(results, indent=2, ensure_ascii=False))


def _parse_query_flags(args: list[str]) -> tuple[dict[str, str], list[str]]:
    """Parse query-specific CLI flags from args list.

    Returns:
        Tuple of (parsed_flags_dict, remaining_args).
        parsed_flags_dict keys: 'filter', 'select', 'orderby', 'orderby_dir',
        'top', 'expand', 'asof_date', 'from_date', 'to_date'.
    """
    query_flags = {
        '--filter': 'filter',
        '--select': 'select',
        '--orderby': 'orderby',
        '--orderby-dir': 'orderby_dir',
        '--top': 'top',
        '--expand': 'expand',
        '--asof-date': 'asof_date',
        '--from-date': 'from_date',
        '--to-date': 'to_date',
    }

    parsed = {}
    remaining = []
    i = 0

    while i < len(args):
        arg = args[i]

        if arg in query_flags:
            if i + 1 >= len(args):
                console.print(f"[red]Error: {arg} requires a value[/]")
                sys.exit(1)
            key = query_flags[arg]
            parsed[key] = args[i + 1]
            i += 2
        else:
            remaining.append(arg)
            i += 1

    return parsed, remaining


def _validate_query_flags(flags: dict[str, str]) -> None:
    """Validate query flags for conflicts and correctness.

    Raises:
        SystemExit: On validation errors.
    """
    # Check mutually exclusive date params
    if flags.get('asof_date') and (flags.get('from_date') or flags.get('to_date')):
        console.print(
            "[red]Error: --asof-date is mutually exclusive with --from-date/--to-date[/]"
        )
        sys.exit(1)

    # Validate $top is numeric
    if 'top' in flags:
        try:
            top_val = int(flags['top'])
            if top_val <= 0:
                raise ValueError("must be > 0")
        except (ValueError, TypeError):
            console.print(f"[red]Error: --top must be a positive integer, got '{flags['top']}'[/]")
            sys.exit(1)


if __name__ == "__main__":
    main()
