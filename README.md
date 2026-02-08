# CSDL Explorer

A terminal explorer for OData CSDL metadata. Parse any `$metadata` XML and discover entities, properties, relationships, and field attributes through a rich interactive interface.

**Features:**
- Interactive terminal UI with Rich tables and panels
- Full Textual TUI with tree navigation (optional)
- Headless mode for scripting and AI assistants
- Search across entity names, property names, labels, and picklist values
- Entity comparison, custom field discovery, visual trees

## The Problem

OData services expose their schema through `$metadata` but those XML documents can be enormous (10MB+, 700+ entities). This tool parses the CSDL and gives you fast, searchable access to every entity, property, navigation relationship, and annotation.

Particularly useful with **SAP**, where documentation says "Worker Category" but the actual field is `customString17`.

## Installation

```bash
pip install csdl-explore
```

For the full Textual TUI (tree navigation, split panes):
```bash
pip install csdl-explore[tui]
```

Or from source:
```bash
git clone https://github.com/guinetik/csdl-explore
cd csdl-explore
pip install -e .        # Basic install
pip install -e ".[tui]" # With Textual TUI
```

## Quick Start

```bash
# Point at any OData $metadata XML file
csdl-explore metadata.xml

# Search for fields
csdl-explore metadata.xml search contract

# Show entity details
csdl-explore metadata.xml entity EmpJob

# Launch full TUI with tree navigation
csdl-explore metadata.xml --tui
```

## Usage

```bash
# Start interactive explorer
csdl-explore metadata.xml

# Or with --file flag
csdl-explore --file metadata.xml entity EmpJob
```

## Interactive Mode

```
$ csdl-explore metadata.xml

╭─────────────────────────────────────────╮
│             CSDL Explorer               │
│         Loaded 735 entities             │
╰─────────────────────────────────────────╯

csdl> search contract
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Search Results (4)                             ┃
┣━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━┫
┃ Type   ┃ Entity    ┃ Match           ┃ Details ┃
┣━━━━━━━━╋━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━╋━━━━━━━━━┫
┃ PROP   ┃ EmpJob    ┃ .contractType   ┃ String  ┃
┃ NAV    ┃ EmpJob    ┃ .contractTypeNav┃         ┃
┗━━━━━━━━┻━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━┻━━━━━━━━━┛

csdl> tree EmpJob
EmpJob
├── Keys
│   ├── seqNumber Edm.Int64
│   ├── startDate Edm.DateTime
│   └── userId Edm.String
├── Properties (45)
│   ├── businessUnit Edm.String
│   ├── company Edm.String
│   └── ... and 42 more
├── Lookups (12)
│   ├── businessUnit -> FOBusinessUnit
│   └── ... and 9 more
├── Custom Fields (24)
│   ├── customString7 Edm.String
│   └── ... and 23 more
└── Navigation (8)
    ├── employmentNav -> EmpEmployment
    └── ... and 7 more
```

## Commands

| Command | Description |
|---------|-------------|
| `entities` | List all entity types (multi-column on wide terminals) |
| `entity <name>` | Show all properties of an entity |
| `tree <name>` | Show entity as visual tree with relationships |
| `model [entities]` | Show data model overview |
| `search <term>` | Search entities and properties |
| `custom <entity>` | Show custom fields (customStringXX) |
| `nav <entity>` | Show navigation properties |
| `diff <e1> <e2>` | Compare two entities |
| `path <entity>` | Suggest JSON paths |
| `emp` | List Emp* entities (SAP SuccessFactors) |
| `per` | List Per* entities (SAP SuccessFactors) |

## Options

| Option | Description |
|--------|-------------|
| `--file <file>` | Path to metadata XML file |
| `--tui` | Launch full Textual TUI |

## Full Textual TUI

For the best experience on large monitors, use the Textual TUI:

```bash
pip install csdl-explore[tui]
csdl-explore metadata.xml --tui
```

Features:
- **Tree navigation** - Browse entities by category (Emp*, Per*, alphabetical)
- **Split pane view** - Entity tree on left, details on right
- **Live search** - Filter as you type
- **Keyboard shortcuts** - `/` to search, `t` to toggle tree, `?` for help
- **Tabbed views** - Details, Properties table, Search results
- **Fuzzy filter** - Type in any table to filter rows (fzf-style)

## Headless Mode (for AI/Scripts)

All commands work without interactive mode, making it easy for AI assistants and scripts to discover fields:

```bash
csdl-explore metadata.xml search benefit
csdl-explore metadata.xml entity EmpJob
csdl-explore metadata.xml diff EmpCompensation EmpPayCompRecurring
csdl-explore metadata.xml tree EmpJob
```

## Python API

```python
from csdl_explore import CSDLExplorer
from pathlib import Path

# Load from file
explorer = CSDLExplorer.from_file(Path("metadata.xml"))

# Search
results = explorer.search("worker")
for r in results:
    print(f"{r.entity}.{r.property}: {r.prop_type}")

# Get entity details
entity = explorer.get_entity("EmpJob")
for prop in entity.properties.values():
    print(f"{prop.name}: {prop.type} (label={prop.label})")

# Get custom fields
for prop in explorer.get_custom_fields("EmpJob"):
    print(f"{prop.name}: {prop.label} picklist={prop.picklist}")

# Compare entities
comp = explorer.compare_entities("EmpCompensation", "EmpPayCompRecurring")
print(f"Only in first: {comp.only_in_entity1[:5]}")
```

## Supported OData Services

Any OData service that exposes CSDL `$metadata` should work. Tested with:
- **SAP SuccessFactors** (full annotation support: labels, picklists, CRUD flags)
- **SAP S/4HANA OData**
- Standard OData v2/v3 services

The parser auto-detects annotation namespaces, so vendor-specific attributes (like `sap:label`, `sap:filterable`) are extracted automatically.

## Project Structure

```
csdl-explore/
├── pyproject.toml
├── README.md
└── src/
    └── csdl_explore/
        ├── __init__.py       # Package exports
        ├── cli.py            # CLI entry point
        ├── explorer.py       # High-level exploration API
        ├── parser.py         # CSDL metadata parser
        ├── tui.py            # Rich-based terminal UI
        └── app.py            # Textual full TUI (optional)
```

## License

MIT
