"""Query builder widget — $filter, $orderby, $top, $select, $expand, URL preview."""

from pathlib import Path

from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Input, Select, SelectionList, Button
from textual.suggester import Suggester
from textual.message import Message
from textual import on

from ..parser import EntityType
from ..formatters import sort_properties, build_odata_url, build_odata_query_params, fuzzy_match

_CSS = (Path(__file__).parent / "query_builder.tcss").read_text()


class FilterSuggester(Suggester):
    """Suggester for OData $filter expressions — suggests property names.

    Args:
        property_names: List of valid property names to suggest.
    """

    def __init__(self, property_names: list[str]) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        self._property_names = property_names

    async def get_suggestion(self, value: str) -> str | None:
        """Get suggestion for the current filter input value.

        Extracts the last word being typed and suggests matching property names.

        Args:
            value: Current input value.

        Returns:
            Suggestion string or None.
        """
        if not value:
            return None

        # Extract the last word (after spaces, operators, quotes, parens)
        import re
        # Split on common OData operators and delimiters
        parts = re.split(r"[\s()'\",]", value)
        last_word = parts[-1] if parts else ""

        if not last_word:
            return None

        # Find first matching property (case-insensitive prefix match)
        last_word_lower = last_word.lower()
        for prop_name in self._property_names:
            if prop_name.lower().startswith(last_word_lower):
                # Build suggestion by replacing the last word with the full property name
                prefix = value[:-len(last_word)]
                return prefix + prop_name

        return None


class FilterInput(Input):
    """Custom Input that uses Tab to accept suggestions."""

    def __init__(self, *args, **kwargs):
        self._filter_suggester = kwargs.pop('filter_suggester', None)
        super().__init__(*args, **kwargs)

    async def on_key(self, event) -> None:
        """Intercept Tab to accept suggestions."""
        if event.key == "tab" and self._filter_suggester:
            suggestion = await self._filter_suggester.get_suggestion(self.value)
            if suggestion and suggestion != self.value:
                self.value = suggestion
                self.cursor_position = len(suggestion)
                event.prevent_default()
                event.stop()
                return
        await super().on_key(event)


class QueryBuilder(Vertical):
    """Query parameter builder with URL preview and run/copy buttons.

    Posts ``QueryBuilder.RunRequested`` when the Run Query button is clicked.
    Posts ``QueryBuilder.CopyRequested`` when the Copy button is clicked.

    Args:
        entity: The entity type to build queries for.
        builder_id: Unique ID suffix for namespacing child widgets.
    """

    DEFAULT_CSS = _CSS

    class RunRequested(Message):
        """Posted when the user clicks Run Query."""

        def __init__(self, params: dict[str, str], url: str) -> None:
            super().__init__()
            self.params = params
            self.url = url

    class CopyRequested(Message):
        """Posted when the user clicks Copy URL."""

        def __init__(self, url: str) -> None:
            super().__init__()
            self.url = url

    def __init__(self, entity: EntityType, builder_id: str) -> None:
        super().__init__(id=f"qb-panel-{builder_id}")
        self._entity = entity
        self._builder_id = builder_id
        self._select_items: list[tuple[str, str, bool]] = [
            (prop.name, prop.name, False)
            for prop in sort_properties(entity.properties, entity.keys)
        ]
        self._expand_items: list[tuple[str, str, bool]] = [
            (nav.name, nav.name, False)
            for nav in entity.navigation.values()
        ]
        # Create filter suggester with all property names (prioritize filterable)
        filterable_props = [p.name for p in entity.properties.values() if p.filterable]
        other_props = [p.name for p in entity.properties.values() if not p.filterable]
        self._filter_suggester = FilterSuggester(filterable_props + other_props)

    def compose(self):
        bid = self._builder_id
        entity = self._entity

        # Row 1: $filter (left) + $orderby / $top (right)
        with Horizontal(classes="q-params-row"):
            with Vertical(classes="q-param-col"):
                yield Static("$filter", classes="q-section-label")
                yield FilterInput(
                    placeholder="e.g. startDate gt datetime'2024-01-01'",
                    id=f"qb-filter-{bid}",
                    suggester=self._filter_suggester,
                    filter_suggester=self._filter_suggester,
                )
                filterable_names = [
                    p.name for p in entity.properties.values() if p.filterable
                ]
                hint_text = ", ".join(filterable_names[:8])
                if len(filterable_names) > 8:
                    hint_text += f" +{len(filterable_names) - 8} more"
                yield Static(f"Filterable: {hint_text}", classes="q-hint")

            with Vertical(classes="q-param-col"):
                with Horizontal(classes="q-labels-row"):
                    yield Static("$orderby", classes="q-section-label")
                    yield Static("$top", classes="q-top-label")
                sortable_props = [
                    (p.name, p.name)
                    for p in entity.properties.values() if p.sortable
                ]
                with Horizontal(classes="q-orderby-row"):
                    yield Select(
                        [("(none)", "")] + sortable_props,
                        value="",
                        id=f"qb-orderby-prop-{bid}",
                        allow_blank=False,
                    )
                    yield Select(
                        [("asc", "asc"), ("desc", "desc")],
                        value="asc",
                        id=f"qb-orderby-dir-{bid}",
                        allow_blank=False,
                    )
                    yield Input(
                        value="20",
                        id=f"qb-top-{bid}",
                        classes="q-top-input",
                    )

        # Row 1.5: Date parameters (mutually exclusive)
        with Horizontal(classes="q-dates-row"):
            with Vertical(classes="q-param-col"):
                yield Static("$asOfDate", classes="q-section-label")
                yield Input(
                    placeholder="YYYY-MM-DD or datetime'...'",
                    id=f"qb-asof-{bid}",
                )
                yield Static("[dim]Point-in-time query (exclusive with date range)[/]", classes="q-hint")

            with Vertical(classes="q-param-col"):
                with Horizontal(classes="q-labels-row"):
                    yield Static("$fromDate", classes="q-section-label")
                    yield Static("$toDate", classes="q-section-label")
                with Horizontal(classes="q-dates-inputs"):
                    yield Input(
                        placeholder="YYYY-MM-DD",
                        id=f"qb-from-{bid}",
                        classes="q-date-input",
                    )
                    yield Input(
                        placeholder="YYYY-MM-DD",
                        id=f"qb-to-{bid}",
                        classes="q-date-input",
                    )
                yield Static("[dim]Date range (exclusive with as-of date)[/]", classes="q-hint")

        # Spacer between params and lists
        yield Static(" ", classes="q-lists-spacer")

        # Row 2: $select (left) + $expand (right)
        with Horizontal(classes="q-lists-row"):
            with Vertical(classes="q-list-col"):
                yield Static("$select", classes="q-section-label")
                yield Input(
                    placeholder="Filter properties\u2026",
                    id=f"qb-select-search-{bid}",
                    classes="q-list-search",
                )
                yield SelectionList[str](
                    *self._select_items,
                    id=f"qb-select-{bid}",
                )

            nav_props = list(entity.navigation.values())
            with Vertical(classes="q-list-col"):
                yield Static("$expand", classes="q-section-label")
                if nav_props:
                    yield Input(
                        placeholder="Filter nav properties\u2026",
                        id=f"qb-expand-search-{bid}",
                        classes="q-list-search",
                    )
                    yield SelectionList[str](
                        *self._expand_items,
                        id=f"qb-expand-{bid}",
                    )
                else:
                    yield Static("[dim]No navigation properties[/]", classes="q-hint")

        # URL bar: input + Run Query + copy button
        with Horizontal(classes="q-url-bar"):
            yield Input(
                placeholder="URL preview",
                id=f"qb-url-preview-{bid}",
                classes="q-url-input",
                disabled=True,
            )
            yield Button(
                "Run Query",
                id=f"qb-btn-run-{bid}",
                variant="primary",
                classes="q-btn-run",
            )
            yield Button(
                "\uf0c5",
                id=f"qb-btn-copy-{bid}",
                variant="default",
                classes="q-btn-copy",
            )

    def on_mount(self) -> None:
        """Initial URL preview."""
        self.update_url_preview("")

    def _get_top_value(self) -> str:
        """Read $top from input, defaulting to 20."""
        try:
            raw = self.query_one(f"#qb-top-{self._builder_id}", Input).value.strip()
            if raw.isdigit() and int(raw) > 0:
                return raw
        except Exception:
            pass
        return "20"

    def get_query_params(self) -> dict[str, str]:
        """Read all query parameter widgets and return an OData params dict."""
        bid = self._builder_id

        selected = []
        try:
            select_list = self.query_one(f"#qb-select-{bid}", SelectionList)
            selected = list(select_list.selected)
        except Exception:
            pass

        filter_expr = ""
        try:
            filter_expr = self.query_one(f"#qb-filter-{bid}", Input).value.strip()
        except Exception:
            pass

        orderby_prop = ""
        orderby_dir = "asc"
        try:
            orderby_prop = self.query_one(f"#qb-orderby-prop-{bid}", Select).value or ""
            orderby_dir = self.query_one(f"#qb-orderby-dir-{bid}", Select).value or "asc"
        except Exception:
            pass

        expanded = []
        try:
            expand_list = self.query_one(f"#qb-expand-{bid}", SelectionList)
            expanded = list(expand_list.selected)
        except Exception:
            pass

        asof_date = ""
        from_date = ""
        to_date = ""
        try:
            asof_date = self.query_one(f"#qb-asof-{bid}", Input).value.strip()
            from_date = self.query_one(f"#qb-from-{bid}", Input).value.strip()
            to_date = self.query_one(f"#qb-to-{bid}", Input).value.strip()
        except Exception:
            pass

        return build_odata_query_params(
            selected=selected,
            filter_expr=filter_expr,
            orderby_prop=orderby_prop,
            orderby_dir=orderby_dir,
            expanded=expanded,
            top=self._get_top_value(),
            asof_date=asof_date,
            from_date=from_date,
            to_date=to_date,
        )

    def update_url_preview(self, base_url: str) -> None:
        """Rebuild and display the URL preview.

        Args:
            base_url: Current base URL from ConnectionPanel.
        """
        if not base_url:
            base_url = "https://api.sap.com/odata/v2"
        params = self.get_query_params()
        url = build_odata_url(base_url, self._entity.name, params)
        try:
            preview = self.query_one(f"#qb-url-preview-{self._builder_id}", Input)
            preview.value = url
        except Exception:
            pass

    def set_url_preview(self, url: str) -> None:
        """Directly set the URL preview text (e.g. after query execution).

        Args:
            url: URL string to display.
        """
        try:
            preview = self.query_one(f"#qb-url-preview-{self._builder_id}", Input)
            preview.value = url
        except Exception:
            pass

    @property
    def url_preview(self) -> str:
        """Current URL preview text."""
        try:
            return self.query_one(f"#qb-url-preview-{self._builder_id}", Input).value
        except Exception:
            return ""

    def _filter_selection_list(
        self, selector: str, all_items: list[tuple[str, str, bool]], term: str,
    ) -> None:
        """Filter a SelectionList, preserving checked state."""
        try:
            sel_list = self.query_one(selector, SelectionList)
        except Exception:
            return
        checked = set(sel_list.selected)
        sel_list.clear_options()
        term_lower = term.strip().lower()
        for label, value, _default in all_items:
            if term_lower and term_lower not in label.lower():
                continue
            sel_list.add_option((label, value, value in checked))

    @on(Button.Pressed)
    def _on_button_pressed(self, event: Button.Pressed) -> None:
        """Route Run Query and Copy button presses."""
        bid = self._builder_id
        btn_id = event.button.id or ""
        if btn_id == f"qb-btn-run-{bid}":
            params = self.get_query_params()
            self.post_message(self.RunRequested(params, self.url_preview))
        elif btn_id == f"qb-btn-copy-{bid}":
            self.post_message(self.CopyRequested(self.url_preview))

    @on(SelectionList.SelectedChanged)
    def _on_selection_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Update URL preview when $select or $expand changes."""
        try:
            from .connection_panel import ConnectionPanel
            cp = self.screen.query_one(ConnectionPanel)
            base_url = cp.base_url
        except Exception:
            base_url = ""
        self.update_url_preview(base_url)

    @on(Input.Changed)
    def _on_input_changed(self, event: Input.Changed) -> None:
        """Update URL preview or filter selection lists on input change."""
        bid = self._builder_id
        input_id = event.input.id or ""
        if input_id in (f"qb-filter-{bid}", f"qb-top-{bid}", f"qb-asof-{bid}", f"qb-from-{bid}", f"qb-to-{bid}"):
            try:
                from .connection_panel import ConnectionPanel
                cp = self.screen.query_one(ConnectionPanel)
                base_url = cp.base_url
            except Exception:
                base_url = ""
            self.update_url_preview(base_url)
        elif input_id == f"qb-select-search-{bid}":
            self._filter_selection_list(
                f"#qb-select-{bid}", self._select_items, event.value,
            )
        elif input_id == f"qb-expand-search-{bid}":
            self._filter_selection_list(
                f"#qb-expand-{bid}", self._expand_items, event.value,
            )

    @on(Select.Changed)
    def _on_select_changed(self, event: Select.Changed) -> None:
        """Update URL preview when $orderby changes."""
        try:
            from .connection_panel import ConnectionPanel
            cp = self.screen.query_one(ConnectionPanel)
            base_url = cp.base_url
        except Exception:
            base_url = ""
        self.update_url_preview(base_url)
