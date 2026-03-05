# Design: Add OData Query Command to CLI

**Date:** 2026-03-05
**Status:** Approved

## Overview

Add an OData `query` command to the CLI that mirrors TUI functionality, allowing users to query entities from the command line with full parameter control. Output results as JSON for scripting and automation.

## Motivation

Currently, the CLI entry point supports:
- Metadata exploration (entities, search, entity details, tree, diff, etc.)
- Picklist value fetching (`picklist` command)
- Interactive Rich REPL mode

But it does **not** support querying actual entity data from OData endpoints. This feature exists only in the TUI. Users who want to script or automate queries must use the TUI interactively.

## Requirements

1. Query OData entity sets with all standard parameters
2. Reuse auth/connection system from `picklist` command
3. Output JSON to stdout (machine-readable for scripts)
4. Default `$top` to 20 to prevent huge result sets
5. Validate mutually exclusive date parameters

## Design

### Command Syntax

```bash
csdl-explore metadata.xml query <entity> [query-flags] [auth-flags]
```

### Query Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--filter <expr>` | OData filter expression | `"startDate gt datetime'2024-01-01'"` |
| `--select <cols>` | Comma-separated columns | `"id,firstName,lastName"` |
| `--orderby <field>` | Sort field | `"createdDate"` |
| `--orderby-dir <asc\|desc>` | Sort direction | `"desc"` (default: `asc`) |
| `--top <n>` | Limit results | `50` (default: `20`) |
| `--expand <navs>` | Comma-separated nav properties | `"nav1,nav2"` |
| `--asof-date <date>` | Point-in-time query (YYYY-MM-DD) | `"2024-01-15"` |
| `--from-date <date>` | Date range start (YYYY-MM-DD) | `"2024-01-01"` |
| `--to-date <date>` | Date range end (YYYY-MM-DD) | `"2024-12-31"` |

**Constraints:**
- `--asof-date` and `--from-date`/`--to-date` are mutually exclusive
- `--orderby` requires an orderby direction (defaults to `asc`)

### Auth Flags

Identical to `picklist` command:

| Flag | Description |
|------|-------------|
| `--base-url <url>` | Override `.env` base URL |
| `--auth-type <type>` | Override `.env` auth type: `none`, `bearer`, `basic`, `oauth2` |
| `--bearer-token <token>` | Bearer token for auth |
| `--username <user>` | Username for basic auth |
| `--password <pass>` | Password for basic auth |

**Connection Resolution:**
1. Load `.env` file alongside metadata XML (if it exists)
2. Apply CLI flag overrides
3. Build `SAPConnection` and authenticate

### Output Format

- **Success:** JSON array to stdout (pretty-printed with 2-space indent)
- **Error:** Error message to stderr, non-zero exit code

Each result object preserves all fields from the OData response (excluding `__metadata`).

### Examples

```bash
# Simple query with defaults (top 20, no filter)
csdl-explore metadata.xml query EmpJob

# Complex query with multiple parameters
csdl-explore metadata.xml query EmpJob \
  --filter "startDate gt datetime'2024-01-01'" \
  --select "id,firstName,lastName" \
  --orderby "createdDate" \
  --orderby-dir "desc" \
  --top 50

# Query with inline auth
csdl-explore metadata.xml query PerPerson \
  --filter "personIdExternal eq '12345'" \
  --base-url https://api.sap.com/odata/v2 \
  --auth-type bearer \
  --bearer-token TOKEN

# Date range query
csdl-explore metadata.xml query EmpEmployment \
  --from-date "2024-01-01" \
  --to-date "2024-12-31" \
  --select "id,startDate,endDate"
```

## Implementation Approach

### Code Reuse

1. **`formatters.py`**: `build_odata_query_params()` — already used by TUI QueryBuilder
2. **`sap_client.py`**: `SAPClient.query_entity()` — existing async method
3. **`cli.py`**: Connection/auth logic from `run_picklist_command()`

### New Functions in `cli.py`

1. **`run_query_command()`** — Main entry point
   - Parse entity name from args
   - Build connection from `.env` + CLI flags
   - Call async function to execute query
   - Print JSON results

2. **`_build_query_params_from_args()`** — Helper
   - Parse flag values into dict
   - Validate mutually exclusive date parameters
   - Build params dict for `build_odata_query_params()`

### Integration

1. Add `query` to command routing in `run_command()`
2. Update help text in `HELP_TEXT`
3. Reuse auth handling from picklist (no new auth code needed)

## Testing

- Query with minimal params (defaults)
- Query with all params
- Error cases: missing entity, auth failure, invalid filter
- Mutually exclusive date params
- JSON output integrity

## Success Criteria

- ✓ Users can query entities from CLI with all OData parameters
- ✓ Output is JSON and machine-readable
- ✓ Auth works via `.env` + CLI overrides
- ✓ Reuses existing code (no duplication)
- ✓ Help text documents all flags
