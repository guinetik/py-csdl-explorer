"""Filterable DataTable widget with built-in fzf-style filtering."""

from textual.widgets import DataTable
from textual.reactive import var

from ..formatters import fuzzy_match


class FilterableDataTable(DataTable):
    """DataTable with built-in fuzzy filtering.

    Stores all rows and provides apply_filter() for fzf-style filtering.
    Use add_filtered_row() instead of add_row() to enable filtering.

    Example:
        table = FilterableDataTable()
        table.add_column("Name")
        table.add_filtered_row("Alice", row_key="alice")
        table.apply_filter("al")  # Shows only Alice
        table.apply_filter("")    # Shows all rows
    """

    _filter_term = var("")

    def __init__(self, **kwargs):
        """Initialize the filterable table."""
        super().__init__(**kwargs)
        self._all_rows: list[tuple[list, str | None]] = []  # (row_data, row_key)

    def add_filtered_row(self, *cells, key=None) -> None:
        """Add a row that participates in filtering.

        Args:
            *cells: Cell values for the row.
            key: Optional row key.
        """
        self._all_rows.append((list(cells), key))
        self.add_row(*cells, key=key)

    def clear_filtered_rows(self) -> None:
        """Clear all filtered rows and reset the table."""
        self._all_rows.clear()
        self.clear()
        self._filter_term = ""

    def apply_filter(self, term: str) -> tuple[int, int]:
        """Filter rows by fuzzy match.

        Args:
            term: The filter string (case-insensitive).

        Returns:
            Tuple of (matched_count, total_count).
        """
        self._filter_term = term.lower()
        self.clear()

        if not self._filter_term:
            # Show all rows
            for cells, row_key in self._all_rows:
                self.add_row(*cells, key=row_key)
            return (len(self._all_rows), len(self._all_rows))

        # Filter rows
        matched = 0
        for cells, row_key in self._all_rows:
            row_text = " ".join(str(c) for c in cells).lower()
            if fuzzy_match(self._filter_term, row_text):
                self.add_row(*cells, key=row_key)
                matched += 1

        return (matched, len(self._all_rows))

    @property
    def filter_term(self) -> str:
        """Current filter term."""
        return self._filter_term

    @property
    def total_rows(self) -> int:
        """Total number of rows (before filtering)."""
        return len(self._all_rows)

    @property
    def visible_rows(self) -> int:
        """Number of currently visible rows (after filtering)."""
        return self.row_count
