"""Filter bar widget for displaying the active fzf-style filter."""

from textual.widgets import Static


class FilterBar(Static):
    """Bottom bar showing the active filter text.

    Call ``show_filter(text)`` to display the filter and ``hide()`` to
    dismiss it.
    """

    def show_filter(self, text: str) -> None:
        """Show the filter bar with the given filter text.

        Args:
            text: Current filter string to display.
        """
        self.update(f" Filter: [bold]{text}[/]  [dim](esc to clear)[/]")
        self.add_class("visible")

    def hide(self) -> None:
        """Hide the filter bar."""
        self.remove_class("visible")
