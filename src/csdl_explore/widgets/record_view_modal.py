"""Record View Modal — form-style popup for viewing a table row's values."""

from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button, Input, Label
from textual import on


class RecordViewModal(ModalScreen):
    """Modal screen showing a table row as a vertical form with selectable fields.

    Each column is displayed as a label + read-only Input so users can
    select and copy individual values.  Similar to the "record view"
    found in database GUIs like DBeaver or DataGrip.

    Args:
        title: Modal title.
        fields: List of (label, value) pairs to display.
    """

    DEFAULT_CSS = """
    RecordViewModal {
        align: center middle;
    }

    RecordViewModal > Vertical {
        width: 60;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
    }

    RecordViewModal .modal-title {
        dock: top;
        height: 3;
        width: 100%;
        background: $primary;
        color: $text;
        content-align: center middle;
        text-style: bold;
    }

    RecordViewModal .modal-content {
        height: auto;
        max-height: 100%;
        width: 100%;
        padding: 1 2;
    }

    RecordViewModal .field-row {
        height: auto;
        width: 100%;
        layout: horizontal;
        margin-bottom: 1;
    }

    RecordViewModal .field-label {
        width: 16;
        height: 3;
        content-align: left middle;
        color: $text-muted;
        text-style: bold;
    }

    RecordViewModal .field-value {
        width: 1fr;
        height: 3;
    }

    RecordViewModal .field-value Input {
        scrollbar-size-horizontal: 0;
    }

    RecordViewModal .modal-buttons {
        dock: bottom;
        height: 3;
        width: 100%;
        layout: horizontal;
        align: center middle;
    }

    RecordViewModal .modal-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    def __init__(self, title: str, fields: list[tuple[str, str]]) -> None:
        super().__init__()
        self._title = title
        self._fields = fields

    def compose(self):
        with Vertical():
            yield Static(self._title, classes="modal-title")
            with VerticalScroll(classes="modal-content"):
                for label, value in self._fields:
                    with Horizontal(classes="field-row"):
                        yield Label(f"{label}", classes="field-label")
                        yield Input(
                            value=str(value),
                            id=f"rv-field-{label.lower().replace(' ', '-')}",
                            classes="field-value",
                        )
            with Horizontal(classes="modal-buttons"):
                yield Button("Copy All", id="btn-copy-all", variant="primary")
                yield Button("Close", id="btn-close", variant="default")

    def on_mount(self) -> None:
        """Make all inputs read-only after mount."""
        for inp in self.query(Input):
            inp.read_only = True

    @on(Button.Pressed, "#btn-copy-all")
    def _on_copy_all(self) -> None:
        """Copy all field values to clipboard as key: value lines."""
        lines = [f"{label}: {value}" for label, value in self._fields]
        self.app.copy_to_clipboard("\n".join(lines))
        self.app.notify("Copied to clipboard", timeout=2)

    @on(Button.Pressed, "#btn-close")
    def _on_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    def action_dismiss(self) -> None:
        """Close modal with ESC."""
        self.dismiss()
