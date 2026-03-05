# Query Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `query` command to the CLI that allows users to query OData entities with full parameter control, outputting results as JSON.

**Architecture:** Add two new functions to `cli.py` that parse query flags and execute OData queries using existing `SAPClient.query_entity()` and `build_odata_query_params()`. Reuse auth logic from the picklist command.

**Tech Stack:** Python 3.10+, httpx (async), Rich (CLI output), argparse-like custom flag parsing

---

## Task 1: Add Query Flag Parser Function

**Files:**
- Modify: `src/csdl_explore/cli.py`

**Description:** Add a helper function to parse query-specific CLI flags (--filter, --select, --orderby, etc.) and return a dict of OData parameters.

**Step 1: Read the current cli.py to understand the pattern**

Read the area around `run_picklist_command()` to see how flags are parsed.

**Step 2: Add `_parse_query_flags()` helper function**

Insert after the `_CONN_FLAGS` dict definition (around line 102) in `cli.py`:

```python
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
```

**Step 3: Verify the code is syntactically correct**

Run: `python -m py_compile src/csdl_explore/cli.py`
Expected: No output (success) or syntax error message

**Step 4: Commit**

```bash
git add src/csdl_explore/cli.py
git commit -m "feat: add query flag parser and validator functions"
```

---

## Task 2: Add Main Query Command Function

**Files:**
- Modify: `src/csdl_explore/cli.py`

**Description:** Add `run_query_command()` function that builds a connection, authenticates, executes the query, and outputs JSON.

**Step 1: Add the main query function**

Insert before `if __name__ == "__main__":` at the end of `cli.py`:

```python
def run_query_command(
    entity_name: str,
    query_flags: dict[str, str],
    metadata_file: Path | None,
    cli_env: dict[str, str],
) -> None:
    """Execute an OData query and print JSON results to stdout.

    Args:
        entity_name: The entity set name (e.g. ``"EmpJob"``).
        query_flags: Parsed query flags (filter, select, orderby, etc.).
        metadata_file: Resolved path to the metadata XML file.
        cli_env: Connection overrides from CLI flags (``SAP_*`` keys).
    """
    from .sap_client import SAPConnection, SAPClient, load_env_file
    from .formatters import build_odata_query_params

    # Validate flags
    _validate_query_flags(query_flags)

    # Build env dict: .env file as base, CLI flags as overrides
    env = {}
    if metadata_file:
        env_path = metadata_file.with_suffix('.env')
        if env_path.exists():
            env = load_env_file(env_path)
    env.update(cli_env)

    # Build connection
    connection = SAPConnection.from_env_dict(env)
    if not connection.base_url:
        console.print(
            "[red]Error: No base URL configured.[/]\n"
            "[dim]Provide --base-url or create a .env file alongside your metadata XML "
            "with SAP_BASE_URL=...[/]"
        )
        sys.exit(1)

    # Convert query flags to OData params
    params_dict = {
        'selected': [s.strip() for s in query_flags.get('select', '').split(',')
                     if s.strip()],
        'filter_expr': query_flags.get('filter', ''),
        'orderby_prop': query_flags.get('orderby', ''),
        'orderby_dir': query_flags.get('orderby_dir', 'asc'),
        'expanded': [e.strip() for e in query_flags.get('expand', '').split(',')
                     if e.strip()],
        'top': query_flags.get('top', '20'),
        'asof_date': query_flags.get('asof_date', ''),
        'from_date': query_flags.get('from_date', ''),
        'to_date': query_flags.get('to_date', ''),
    }

    params = build_odata_query_params(**params_dict)

    # Execute query
    async def _fetch():
        client = SAPClient(connection)
        try:
            await client.authenticate()
            return await client.query_entity(entity_name, params)
        finally:
            await client.close()

    try:
        results, full_url, raw_text, content_type = asyncio.run(_fetch())
    except Exception as e:
        console.print(f"[red]Error executing query: {e}[/]")
        sys.exit(1)

    # Output JSON to stdout
    print(json.dumps(results, indent=2, ensure_ascii=False))
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/csdl_explore/cli.py`
Expected: No output

**Step 3: Commit**

```bash
git add src/csdl_explore/cli.py
git commit -m "feat: add run_query_command to execute OData queries"
```

---

## Task 3: Integrate Query Command into CLI Routing

**Files:**
- Modify: `src/csdl_explore/cli.py` (HELP_TEXT, run_command, run_file_mode)

**Description:** Add the `query` command to the command router and update help text.

**Step 1: Update HELP_TEXT**

In the `HELP_TEXT` variable (around line 36-52), update the `[bold]Commands:[/]` section to include:

```
    query <name>       Execute OData query on entity (see examples below)
```

And add to the `[bold]Examples:[/]` section (after line 73):

```
    # Query with defaults (top 20)
    csdl-explore metadata.xml query EmpJob

    # Query with filters and selection
    csdl-explore metadata.xml query EmpJob \
      --filter "startDate gt datetime'2024-01-01'" \
      --select "id,firstName,lastName" \
      --orderby "createdDate" \
      --orderby-dir "desc" \
      --top 50
```

**Step 2: Modify run_file_mode() to parse query flags**

Update the `run_file_mode()` function to detect and parse query flags when command is `'query'`:

Find the line `run_command(explorer, command, cmd_args, metadata_file, cli_env or {})` (around line 176) and replace it with:

```python
    else:
        # Parse query-specific flags from cmd_args if command is 'query'
        if command == 'query':
            query_flags, remaining_args = _parse_query_flags(cmd_args)
            if not remaining_args:
                console.print("[yellow]Usage: query <entity> [flags][/]")
                sys.exit(1)
            entity_name = remaining_args[0]
            run_query_command(entity_name, query_flags, metadata_file, cli_env or {})
        else:
            run_command(explorer, command, cmd_args, metadata_file, cli_env or {})
```

**Step 3: Verify syntax**

Run: `python -m py_compile src/csdl_explore/cli.py`
Expected: No output

**Step 4: Commit**

```bash
git add src/csdl_explore/cli.py
git commit -m "feat: integrate query command into CLI routing and help text"
```

---

## Task 4: Manual Integration Test - Simple Query

**Files:**
- Test: Manual CLI execution

**Description:** Test that the query command works with minimal parameters.

**Step 1: Install the package in editable mode**

Run: `pip install -e .`
Expected: Package installed successfully

**Step 2: Create a simple test metadata file if needed**

If you have a test metadata file, use it. Otherwise, skip this step.

**Step 3: Run a simple query with help output**

Run: `csdl-explore --help | grep -A 2 "query"`
Expected: See the query command in help text with brief description

**Step 4: Try a query command (will fail without proper connection, but should parse correctly)**

Run: `csdl-explore test-metadata.xml query EmpJob --top 10 --select "id,firstName" 2>&1 | head -20`
Expected: Either results (if connection available) or an error about missing base URL (which means the command was parsed correctly)

**Step 5: Commit test results**

If manual testing was successful, no commit needed. If you found issues, fix them in Task 2 or 3 and recommit.

---

## Task 5: Code Review and Cleanup

**Files:**
- Review: `src/csdl_explore/cli.py`

**Description:** Review the implementation for code quality and consistency.

**Checklist:**
- [ ] All function signatures match existing style (docstrings, type hints)
- [ ] Error messages are consistent with existing CLI errors
- [ ] Flag parsing matches picklist pattern
- [ ] JSON output uses same indent/formatting as picklist
- [ ] No duplicate code — validate reuse of `SAPConnection`, `SAPClient`
- [ ] Comments explain non-obvious logic (flag parsing, param building)

**Step 1: Review changes**

Run: `git diff HEAD~2 src/csdl_explore/cli.py | head -100`

**Step 2: If changes look good, create a final summary commit**

If all code review items pass, run:

```bash
git log --oneline -5
```

Expected: See your query command commits in recent history

---

## Success Criteria

- ✓ `csdl-explore metadata.xml query EmpJob` runs without syntax errors
- ✓ `csdl-explore --help` shows query command with examples
- ✓ Query flags are parsed correctly (--filter, --select, --orderby, etc.)
- ✓ Mutually exclusive date params trigger error
- ✓ JSON output is valid and parseable
- ✓ Auth reuses picklist pattern (reads .env, allows CLI overrides)
- ✓ All commits are atomic and descriptive

