"""JSON Viewer Modal — popup for viewing row data as formatted JSON."""

import json
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button
from textual import on

from rich.syntax import Syntax


class JsonViewerModal(ModalScreen):
    """Modal screen for viewing JSON data with copy/close actions.

    Args:
        title: Modal title.
        data: Data to display as JSON (dict or any JSON-serializable object).
    """

    DEFAULT_CSS = """
    JsonViewerModal {
        align: center middle;
    }

    JsonViewerModal > Vertical {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
    }

    JsonViewerModal .modal-title {
        dock: top;
        height: 3;
        width: 100%;
        background: $primary;
        color: $text;
        content-align: center middle;
        text-style: bold;
    }

    JsonViewerModal .modal-content {
        height: 1fr;
        width: 100%;
        padding: 1;
        overflow: auto;
    }

    JsonViewerModal .modal-buttons {
        dock: bottom;
        height: 3;
        width: 100%;
        layout: horizontal;
        align: center middle;
    }

    JsonViewerModal .modal-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    def __init__(self, title: str, data: dict | list | str) -> None:
        super().__init__()
        self._title = title
        self._data = data
        self._json_text = ""

    def compose(self):
        with Vertical():
            yield Static(self._title, classes="modal-title")
            with VerticalScroll(classes="modal-content"):
                yield Static(id="json-content")
            with Horizontal(classes="modal-buttons"):
                yield Button("Copy", id="btn-copy", variant="primary")
                yield Button("Close", id="btn-close", variant="default")

    def on_mount(self) -> None:
        """Format and display the JSON data."""
        # Convert data to pretty JSON
        if isinstance(self._data, str):
            self._json_text = self._data
        else:
            self._json_text = json.dumps(self._data, indent=2, default=str)

        # Display with syntax highlighting
        syntax = Syntax(
            self._json_text,
            "json",
            line_numbers=True,
            theme="monokai",
            word_wrap=False,
        )
        self.query_one("#json-content", Static).update(syntax)

    @on(Button.Pressed, "#btn-copy")
    def _on_copy(self) -> None:
        """Copy JSON to clipboard."""
        self.app.copy_to_clipboard(self._json_text)
        self.app.notify("JSON copied to clipboard", timeout=2)

    @on(Button.Pressed, "#btn-close")
    def _on_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    def action_dismiss(self) -> None:
        """Close modal with ESC."""
        self.dismiss()
