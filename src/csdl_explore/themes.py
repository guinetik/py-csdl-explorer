"""
Theme definitions for CSDL Explorer.

Provides Textual themes for the TUI and a color palette dict for the Rich REPL
so both interfaces stay visually consistent.
"""

from textual.theme import Theme

# ── Textual themes ─────────────────────────────────────────────────────

VERCEL_THEME = Theme(
    name="terminal-vercel-green",
    primary="#00dc82",
    secondary="#333333",
    accent="#00dc82",
    foreground="#e1e1e1",
    background="#0a0a0a",
    surface="#171717",
    panel="#1a1a1a",
    warning="#f5a623",
    error="#ee0000",
    success="#00dc82",
    dark=True,
)

CLASSIC_THEME = Theme(
    name="classic",
    primary="#00bfff",
    secondary="#9370db",
    accent="#ffd700",
    foreground="#e1e1e1",
    background="#1e1e1e",
    surface="#2d2d2d",
    panel="#333333",
    warning="#ffa500",
    error="#ff4444",
    success="#44ff44",
    dark=True,
)

ALL_THEMES = [VERCEL_THEME, CLASSIC_THEME]
THEME_NAMES = [t.name for t in ALL_THEMES]

# ── Rich REPL palettes ────────────────────────────────────────────────
# Simple role→Rich-markup-color mappings used by tui.py.

PALETTES: dict[str, dict[str, str]] = {
    "terminal-vercel-green": {
        "primary": "#00dc82",
        "secondary": "#888888",
        "accent": "#00dc82",
        "entity": "#00dc82",
        "property": "#e1e1e1",
        "key": "#f5a623",
        "required": "#ee0000",
        "crud": "#00dc82",
        "hidden": "dim",
        "no_filter": "#ee0000",
        "nav": "#00dc82",
        "picklist": "#9370db",
        "dim": "dim",
        "label": "dim",
    },
    "classic": {
        "primary": "cyan",
        "secondary": "magenta",
        "accent": "yellow",
        "entity": "cyan",
        "property": "cyan",
        "key": "yellow",
        "required": "red",
        "crud": "green",
        "hidden": "dim",
        "no_filter": "red",
        "nav": "blue",
        "picklist": "magenta",
        "dim": "dim",
        "label": "dim",
    },
}

DEFAULT_PALETTE = "terminal-vercel-green"
