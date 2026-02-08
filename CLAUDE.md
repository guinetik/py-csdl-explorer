# CSDL Explorer

Terminal-based OData CSDL metadata explorer with a Rich REPL and Textual TUI.

## Project Overview

Parses OData `$metadata` XML files and lets users explore entities, properties, navigation, picklists, and run OData queries. Targets SAP SuccessFactors but works with any OData v2 provider.

**Entry point:** `csdl-explore <metadata.xml> [--tui]`

## Architecture

```
src/csdl_explore/
  parser.py        # XML → dataclasses (EntityType, Property, NavigationProperty)
  explorer.py      # Query/search layer over parsed metadata
  formatters.py    # Pure data transforms — NO UI imports, returns tuples/lists/dicts
  themes.py        # Textual Theme objects (ALL_THEMES) + Rich palette dicts (PALETTES)
  repl.py          # Rich-based interactive REPL
  cli.py           # CLI entry point, arg parsing, command dispatch
  app.py           # Textual App — layout, tabs, search, keybindings
  sap_client.py    # Async OData HTTP client (httpx), auth flows, .env persistence
  widgets/
    entity_pane.py   # Entity tab: Details, Properties, Query sub-tabs
    picklist_pane.py # Picklist tab: values viewer with OData fetch
    entity_tree.py   # Sidebar tree widget
    search_results.py# Sidebar search results DataTable
    filter_bar.py    # Bottom filter bar for fzf-style property filtering
    auth_modal.py    # Modal screen for credential input (bearer/basic/oauth2)
```

## Design Preferences

- **Ports and Adapters (Hexagonal)**: Keep domain logic (parser, explorer, formatters) free of framework imports. UI layers (repl, app, widgets) are adapters that consume pure domain interfaces.
- **Componentized Widgets**: Each TUI widget is a self-contained unit with its own `DEFAULT_CSS`, `compose()`, and event handlers. Widgets communicate via Textual messages (up) and attribute setting (down). Avoid god-widgets — extract reusable pieces into `widgets/`.
- **Pythonic style**: Prefer dataclasses over dicts, type hints, `@property` over getters, comprehensions over loops where readable, explicit over implicit.

## Key Patterns

### Separation of Concerns
- **`formatters.py`** is a pure-function module with zero UI imports. It returns plain data (tuples, lists, dicts). Both `repl.py` and TUI widgets consume it.
- **`themes.py`** exports `ALL_THEMES` (Textual Theme objects) and `PALETTES` (Rich markup color dicts). The REPL uses `PALETTES`; the TUI uses `ALL_THEMES`.
- **`sap_client.py`** is UI-agnostic. Both REPL and TUI import `SAPClient`/`SAPConnection`.

### Textual TUI Conventions
- App-level CSS lives in `app.py` (`CSDLExplorerApp.CSS`).
- Widget-level CSS uses `DEFAULT_CSS` inside each widget class.
- CSS class names for Query tab use `q-` prefix (e.g. `q-params-row`, `q-list-col`).
- Widget IDs include the entity name for uniqueness: `q-filter-{eid}`, `q-select-{eid}`.
- Use `$primary`, `$accent`, `$surface` tokens in CSS only — Rich markup in widget labels must use hex colors (e.g. `[#00dc82]`), NOT `$`-tokens.
- Event handlers use `@on(Widget.Event)` decorators with CSS selector filtering.
- Async work uses `@work(thread=False)` for httpx calls.
- Messages flow up (child `post_message()` → parent handler); data flows down (parent sets child attributes).

### Auth System
- 4 auth types: `none`, `bearer`, `basic`, `oauth2` (SAP SAML Bearer flow).
- `SAPConnection` dataclass holds all credentials. `SAPClient` wraps httpx.
- `_request()` centralizes auth header logic for all HTTP calls.
- `.env` files are saved alongside metadata XML (`{stem}.env`). Only save on explicit credential configuration, not on every query.
- `AuthModal` is a reusable modal screen parameterized by auth type.

### Docstrings
Google-style with `Args:` and `Returns:` sections.

## Textual CSS Gotchas

These are hard-won lessons — do not repeat these mistakes:

1. **`$`-tokens in Rich markup**: `$primary` etc. work in TCSS only. For `Text.from_markup()` or `Static("[bold $primary]...")`, use actual hex colors.
2. **`Input` scrollbar overlap**: The app sets `* { scrollbar-size-horizontal: 1; }` which makes Input fields show a scrollbar over text. Fix with `Input { scrollbar-size-horizontal: 0; }`.
3. **`RadioSet` layout**: Extends `VerticalScroll` — `layout: horizontal` breaks it. Don't put `RadioSet` inside `Horizontal` — it collapses. For horizontal auth selection, use `Select` dropdown instead.
4. **`SelectionList` border clipping**: Fixed `height` values on parent containers clip the bottom border. Use `height: auto; max-height: N;` or ensure fixed height includes border cells.
5. **`Collapsible` content indent**: Default `Contents` child has left padding. Override with `Collapsible > Contents { padding: 0; }` for flush alignment.
6. **`max-height` cascading**: Parent `max-height` clips children even if children have `height: auto`. Always check the full ancestor chain.

## Development

```bash
# Install in editable mode with TUI extra
# Note: The [tui] extra includes textual[syntax] for TextArea syntax highlighting
pip install -e ".[tui]"

# Run REPL mode
csdl-explore metadata.xml

# Run Textual TUI
csdl-explore metadata.xml --tui

# Run tests
pytest
```

## Dependencies

- **Core**: `rich` (formatting), `httpx` (HTTP client)
- **TUI extra**: `textual[syntax]` (includes tree-sitter parsers for JSON/XML syntax highlighting in TextArea)

## Environment

- Python 3.10+, Windows (MSYS2 shell)
- Windows MSYS2 has issues with multiline `python -c` commands — use temp `.py` files instead.
- Package must be `pip install -e .` from this directory after adding new modules.
