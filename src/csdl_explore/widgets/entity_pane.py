"""Entity tab pane — shows Details, Properties, and Query for a single entity."""

from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.widgets import (
    Static, DataTable, TabbedContent, TabPane, Button, Input,
    Select, SelectionList, Collapsible,
)
from textual import on, work

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree as RichTree
from rich import box

from ..explorer import CSDLExplorer
from ..parser import EntityType
from ..formatters import sort_properties, group_entity_properties, format_flag_check
from ..themes import VERCEL_THEME


class EntityTabPane(TabPane):
    """A tab pane displaying Details, Properties, and Query sub-tabs for one entity.

    Args:
        entity: The entity type to display.
        explorer: The CSDL explorer instance.
    """

    DEFAULT_CSS = """
    /* ── Collapsible: remove content indent ──────────── */
    Collapsible > Contents {
        padding: 0;
    }

    /* ── Auth section ────────────────────────────────── */
    .q-base-url {
        width: 1fr;
        margin: 0 1;
    }

    .q-spacer {
        height: 1;
    }

    .q-auth-row {
        height: 3;
        padding: 0 1;
    }

    .q-auth-select {
        width: 20;
    }

    .q-auth-row Button {
        margin: 0 0 0 1;
    }

    /* ── Query builder ───────────────────────────────── */
    .q-params-row {
        height: auto;
        max-height: 12;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    .q-param-col {
        width: 1fr;
        height: auto;
        max-height: 11;
        padding: 0 1 0 0;
    }

    .q-section-label {
        height: 1;
        padding: 0 0 0 1;
        text-style: bold;
        color: $primary;
    }

    .q-hint {
        height: 1;
        padding: 0 0 0 1;
        color: $text-muted;
    }

    .q-orderby-row {
        height: 3;
    }

    .q-top-label {
        width: auto;
        height: 3;
        content-align-vertical: middle;
        padding: 0 1;
        text-style: bold;
        color: $primary;
    }

    .q-top-input {
        width: 10;
    }

    .q-lists-spacer {
        height: 1;
    }

    .q-lists-row {
        height: 24;
        padding: 0 1;
    }

    .q-list-col {
        width: 1fr;
        height: 100%;
        padding: 0 1 0 0;
    }

    .q-list-search {
        height: 3;
        margin: 0 0 1 0;
    }

    /* ── URL bar ─────────────────────────────────────── */
    .q-url-bar {
        height: 3;
        margin: 1 1 0 1;
    }

    .q-url-input {
        width: 1fr;
    }

    .q-btn-run {
        width: auto;
    }

    .q-btn-copy {
        width: auto;
        min-width: 4;
    }

    /* ── Results ─────────────────────────────────────── */
    .q-status {
        padding: 0 1;
        height: 1;
    }
    """

    def __init__(self, entity: EntityType, explorer: CSDLExplorer):
        pane_id = f"entity-{entity.name}"
        super().__init__(entity.name, id=pane_id)
        self.entity = entity
        self.explorer = explorer
        self._prop_rows: list[tuple] = []
        self._table_filter: str = ""
        # Full item lists for $select / $expand fuzzy filtering
        self._select_items: list[tuple[str, str, bool]] = [
            (prop.name, prop.name, False)
            for prop in sort_properties(entity.properties, entity.keys)
        ]
        self._expand_items: list[tuple[str, str, bool]] = [
            (nav.name, nav.name, False)
            for nav in entity.navigation.values()
        ]

    def compose(self):
        eid = self.entity.name
        with TabbedContent(id=f"sub-tabs-{eid}"):
            with TabPane("Details", id=f"detail-{eid}"):
                with VerticalScroll():
                    yield Static(id=f"details-{eid}")
            with TabPane("Properties", id=f"props-{eid}"):
                yield DataTable(
                    id=f"prop-table-{eid}",
                    zebra_stripes=True,
                    cursor_type="row",
                )
            with TabPane("Query", id=f"query-{eid}"):
                with VerticalScroll():
                    yield from self._compose_query_tab()

    def _compose_query_tab(self):
        """Yield widgets for the Query sub-tab."""
        eid = self.entity.name

        # ── Auth collapsible ──────────────────────────────────
        with Collapsible(title="Auth", id=f"q-auth-section-{eid}"):
            yield Static("Base URL", classes="q-section-label")
            yield Input(
                placeholder="https://api.sap.com/odata/v2",
                id=f"q-base-url-{eid}",
                classes="q-base-url",
            )
            yield Static(" ", classes="q-spacer")
            with Horizontal(classes="q-auth-row"):
                yield Select(
                    [
                        ("None", "none"),
                        ("Bearer Token", "bearer"),
                        ("Basic Auth", "basic"),
                        ("OAuth2 SAML", "oauth2"),
                    ],
                    value="none",
                    id=f"q-auth-type-{eid}",
                    allow_blank=False,
                    classes="q-auth-select",
                )
                yield Button(
                    "Configure Credentials",
                    id=f"q-btn-configure-{eid}",
                    variant="primary",
                )

        # ── Query collapsible ─────────────────────────────────
        with Collapsible(title="Query", id=f"q-query-section-{eid}", collapsed=False):
            # Row 1: $filter (left) + $orderby / $top (right)
            with Horizontal(classes="q-params-row"):
                with Vertical(classes="q-param-col"):
                    yield Static("$filter", classes="q-section-label")
                    yield Input(
                        placeholder="e.g. startDate gt datetime'2024-01-01'",
                        id=f"q-filter-{eid}",
                    )
                    filterable_names = [
                        p.name for p in self.entity.properties.values() if p.filterable
                    ]
                    hint_text = ", ".join(filterable_names[:8])
                    if len(filterable_names) > 8:
                        hint_text += f" +{len(filterable_names) - 8} more"
                    yield Static(f"Filterable: {hint_text}", classes="q-hint")

                with Vertical(classes="q-param-col"):
                    yield Static("$orderby", classes="q-section-label")
                    sortable_props = [
                        (p.name, p.name)
                        for p in self.entity.properties.values() if p.sortable
                    ]
                    with Horizontal(classes="q-orderby-row"):
                        yield Select(
                            [("(none)", "")] + sortable_props,
                            value="",
                            id=f"q-orderby-prop-{eid}",
                            allow_blank=False,
                        )
                        yield Select(
                            [("asc", "asc"), ("desc", "desc")],
                            value="asc",
                            id=f"q-orderby-dir-{eid}",
                            allow_blank=False,
                        )
                        yield Static("$top", classes="q-top-label")
                        yield Input(
                            value="20",
                            id=f"q-top-{eid}",
                            classes="q-top-input",
                        )

            # Spacer between params and lists
            yield Static(" ", classes="q-lists-spacer")

            # Row 2: $select (left) + $expand (right)
            with Horizontal(classes="q-lists-row"):
                with Vertical(classes="q-list-col"):
                    yield Static("$select", classes="q-section-label")
                    yield Input(
                        placeholder="Filter properties\u2026",
                        id=f"q-select-search-{eid}",
                        classes="q-list-search",
                    )
                    yield SelectionList[str](
                        *self._select_items,
                        id=f"q-select-{eid}",
                    )

                nav_props = list(self.entity.navigation.values())
                with Vertical(classes="q-list-col"):
                    yield Static("$expand", classes="q-section-label")
                    if nav_props:
                        yield Input(
                            placeholder="Filter nav properties\u2026",
                            id=f"q-expand-search-{eid}",
                            classes="q-list-search",
                        )
                        yield SelectionList[str](
                            *self._expand_items,
                            id=f"q-expand-{eid}",
                        )
                    else:
                        yield Static("[dim]No navigation properties[/]", classes="q-hint")

            # URL bar: input + Run Query + copy emoji button
            with Horizontal(classes="q-url-bar"):
                yield Input(
                    placeholder="URL preview",
                    id=f"q-url-preview-{eid}",
                    classes="q-url-input",
                    disabled=True,
                )
                yield Button(
                    "Run Query",
                    id=f"q-btn-run-{eid}",
                    variant="primary",
                    classes="q-btn-run",
                )
                yield Button(
                    "\U0001f4cb",
                    id=f"q-btn-copy-{eid}",
                    variant="default",
                    classes="q-btn-copy",
                )

        # ── Results collapsible ───────────────────────────────
        with Collapsible(title="Results", id=f"q-results-section-{eid}", collapsed=False):
            yield Static(
                "[dim]Not connected[/]",
                id=f"q-status-{eid}",
                classes="q-status",
            )
            yield DataTable(
                id=f"q-results-{eid}",
                zebra_stripes=True,
                cursor_type="row",
            )

    def on_mount(self) -> None:
        """Render details and set up property table after mount."""
        self._render_details()
        self._setup_property_table()
        self._prefill_query_connection()
        self._update_url_preview()

    # ── Query sub-tab: connection ─────────────────────────────────

    def _prefill_query_connection(self) -> None:
        """Pre-fill Base URL and auth type from existing app.sap_connection."""
        conn = getattr(self.app, "sap_connection", None)
        if not conn:
            return
        eid = self.entity.name
        if conn.base_url:
            self.query_one(f"#q-base-url-{eid}", Input).value = conn.base_url
        if conn.auth_type and conn.auth_type != "none":
            try:
                self.query_one(f"#q-auth-type-{eid}", Select).value = conn.auth_type
            except Exception:
                pass

    def _get_query_auth_type(self) -> str:
        """Read current auth type from the auth dropdown."""
        auth_select = self.query_one(f"#q-auth-type-{self.entity.name}", Select)
        return auth_select.value or "none"

    def _build_query_connection(self, creds: dict | None = None):
        """Build a SAPConnection from the query tab fields + optional modal creds."""
        from ..sap_client import SAPConnection
        eid = self.entity.name
        base_url = self.query_one(f"#q-base-url-{eid}", Input).value.strip()
        auth_type = self._get_query_auth_type()

        existing = getattr(self.app, "sap_connection", None)
        kwargs = {}
        if existing:
            kwargs = {
                "bearer_token": existing.bearer_token,
                "username": existing.username, "password": existing.password,
                "idp_url": existing.idp_url, "token_url": existing.token_url,
                "client_id": existing.client_id, "user_id": existing.user_id,
                "company_id": existing.company_id, "private_key": existing.private_key,
                "grant_type": existing.grant_type,
            }
        if creds:
            kwargs.update(creds)

        return SAPConnection(base_url=base_url, auth_type=auth_type, **kwargs)

    def _save_query_connection(self, conn) -> None:
        """Persist connection to app state and .env file."""
        self.app.sap_connection = conn

        metadata_path = getattr(self.app, "metadata_path", None)
        if metadata_path:
            from ..sap_client import save_env_file
            env_path = metadata_path.parent / f"{metadata_path.stem}.env"
            save_env_file(env_path, conn)
            self.app.notify(f"Saved credentials to {env_path.name}", timeout=3)

    def _open_query_auth_modal(self) -> None:
        """Open the credentials modal for the selected auth type."""
        from .auth_modal import AuthModal

        auth_type = self._get_query_auth_type()
        if auth_type == "none":
            self.app.notify("No credentials needed for 'None' auth", timeout=2)
            return

        conn = getattr(self.app, "sap_connection", None)
        prefill = {}
        if conn:
            if auth_type == "bearer":
                prefill = {"bearer_token": conn.bearer_token}
            elif auth_type == "basic":
                prefill = {"username": conn.username, "password": conn.password}
            elif auth_type == "oauth2":
                prefill = {
                    "idp_url": conn.idp_url, "token_url": conn.token_url,
                    "client_id": conn.client_id, "user_id": conn.user_id,
                    "company_id": conn.company_id, "private_key": conn.private_key,
                    "grant_type": conn.grant_type,
                }

        modal = AuthModal(auth_type, prefill)
        self.app.push_screen(modal, self._on_query_auth_dismiss)

    def _on_query_auth_dismiss(self, creds) -> None:
        """Callback when the auth modal is dismissed."""
        if creds is None:
            return
        conn = self._build_query_connection(creds)
        self._save_query_connection(conn)

    # ── Query sub-tab: query builder ──────────────────────────────

    def _get_top_value(self) -> str:
        """Read $top from the input, falling back to 20."""
        eid = self.entity.name
        try:
            raw = self.query_one(f"#q-top-{eid}", Input).value.strip()
            if raw.isdigit() and int(raw) > 0:
                return raw
        except Exception:
            pass
        return "20"

    def _build_query_params(self) -> dict[str, str]:
        """Read $select, $filter, $orderby, $expand, $top from widgets into a params dict."""
        eid = self.entity.name
        params: dict[str, str] = {}

        # $select — omit if none selected (returns all fields)
        try:
            select_list = self.query_one(f"#q-select-{eid}", SelectionList)
            selected = list(select_list.selected)
            if selected:
                params["$select"] = ",".join(selected)
        except Exception:
            pass

        # $filter
        try:
            filter_val = self.query_one(f"#q-filter-{eid}", Input).value.strip()
            if filter_val:
                params["$filter"] = filter_val
        except Exception:
            pass

        # $orderby
        try:
            prop_select = self.query_one(f"#q-orderby-prop-{eid}", Select)
            prop_val = prop_select.value
            if prop_val:
                dir_select = self.query_one(f"#q-orderby-dir-{eid}", Select)
                dir_val = dir_select.value or "asc"
                params["$orderby"] = f"{prop_val} {dir_val}"
        except Exception:
            pass

        # $expand
        try:
            expand_list = self.query_one(f"#q-expand-{eid}", SelectionList)
            expanded = list(expand_list.selected)
            if expanded:
                params["$expand"] = ",".join(expanded)
        except Exception:
            pass

        # $top
        params["$top"] = self._get_top_value()

        return params

    def _update_url_preview(self) -> None:
        """Build URL string from base_url + entity name + params, update Input."""
        eid = self.entity.name
        try:
            base_url = self.query_one(f"#q-base-url-{eid}", Input).value.strip()
        except Exception:
            base_url = ""

        if not base_url:
            base_url = "https://api.sap.com/odata/v2"

        params = self._build_query_params()
        params.setdefault("$format", "json")

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{base_url.rstrip('/')}/{eid}?{param_str}"

        try:
            preview = self.query_one(f"#q-url-preview-{eid}", Input)
            preview.value = url
        except Exception:
            pass

    def _filter_selection_list(
        self,
        selector: str,
        all_items: list[tuple[str, str, bool]],
        term: str,
    ) -> None:
        """Filter a SelectionList to show only items matching *term*.

        Preserves checked state of items that remain visible.
        """
        try:
            sel_list = self.query_one(selector, SelectionList)
        except Exception:
            return

        # Remember currently checked values
        checked = set(sel_list.selected)

        sel_list.clear_options()
        term_lower = term.strip().lower()
        for label, value, _default in all_items:
            if term_lower and term_lower not in label.lower():
                continue
            sel_list.add_option((label, value, value in checked))

    # ── Query sub-tab: run query ──────────────────────────────────

    @work(thread=False)
    async def _run_query(self) -> None:
        """Build connection, authenticate, call client.query_entity()."""
        eid = self.entity.name
        base_url = self.query_one(f"#q-base-url-{eid}", Input).value.strip()
        if not base_url:
            self.app.notify("Enter a Base URL first", severity="warning")
            return

        conn = self._build_query_connection()
        self.app.sap_connection = conn

        status = self.query_one(f"#q-status-{eid}", Static)
        table = self.query_one(f"#q-results-{eid}", DataTable)

        status.update("[dim]Querying...[/]")
        self.app.notify("Sending query\u2026", timeout=2)

        # Auto-expand results section
        try:
            results_section = self.query_one(f"#q-results-section-{eid}", Collapsible)
            results_section.collapsed = False
        except Exception:
            pass

        try:
            from ..sap_client import SAPClient

            client = SAPClient(conn)
            await client.authenticate()

            params = self._build_query_params()
            results, full_url = await client.query_entity(eid, params)
            await client.close()

            # Update URL preview with actual URL used
            try:
                preview = self.query_one(f"#q-url-preview-{eid}", Input)
                preview.value = full_url
            except Exception:
                pass

            # Populate results table
            table.clear(columns=True)

            if not results:
                status.update(f"Connected to [bold]{conn.base_url}[/] \u2014 no results")
                self.app.notify("Query returned no results", severity="warning", timeout=3)
                return

            # Build columns from first result's keys (skip __metadata)
            columns = [k for k in results[0].keys() if k != "__metadata"]
            for col in columns:
                table.add_column(col, key=col)

            for row in results:
                table.add_row(*[str(row.get(col, "")) for col in columns])

            status.update(
                f"Connected to [bold]{conn.base_url}[/] \u2014 "
                f"[bold]{len(results)}[/] results, [bold]{len(columns)}[/] columns"
            )
            self.app.notify(f"{len(results)} results, {len(columns)} columns", timeout=3)

        except Exception as e:
            status.update(f"[red]Error: {e}[/]")
            self.app.notify(f"Query failed: {e}", severity="error", timeout=5)

    # ── Event handlers ────────────────────────────────────────────

    @on(Button.Pressed)
    def _on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button presses for the Query sub-tab."""
        eid = self.entity.name
        btn_id = event.button.id or ""
        if btn_id == f"q-btn-configure-{eid}":
            self._open_query_auth_modal()
        elif btn_id == f"q-btn-run-{eid}":
            self._run_query()
        elif btn_id == f"q-btn-copy-{eid}":
            self._copy_url()

    def _copy_url(self) -> None:
        """Copy the URL preview text to clipboard."""
        eid = self.entity.name
        try:
            preview = self.query_one(f"#q-url-preview-{eid}", Input)
            self.app.copy_to_clipboard(preview.value)
            self.app.notify("URL copied to clipboard", timeout=2)
        except Exception as e:
            self.app.notify(f"Copy failed: {e}", severity="warning")

    @on(SelectionList.SelectedChanged)
    def _on_selection_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Update URL preview when $select or $expand changes."""
        self._update_url_preview()

    @on(Input.Changed)
    def _on_input_changed(self, event: Input.Changed) -> None:
        """Update URL preview or filter selection lists on input change."""
        eid = self.entity.name
        input_id = event.input.id or ""
        if input_id in (f"q-filter-{eid}", f"q-base-url-{eid}", f"q-top-{eid}"):
            self._update_url_preview()
        elif input_id == f"q-select-search-{eid}":
            self._filter_selection_list(
                f"#q-select-{eid}", self._select_items, event.value,
            )
        elif input_id == f"q-expand-search-{eid}":
            self._filter_selection_list(
                f"#q-expand-{eid}", self._expand_items, event.value,
            )

    @on(Select.Changed)
    def _on_select_changed(self, event: Select.Changed) -> None:
        """Update URL preview when $orderby changes."""
        self._update_url_preview()

    # ── Details sub-tab ───────────────────────────────────────────

    def _render_details(self) -> None:
        """Populate the Details sub-tab with a Rich panel and tree."""
        entity = self.entity
        pc = VERCEL_THEME.primary
        ac = VERCEL_THEME.accent
        sc = VERCEL_THEME.success

        details_widget = self.query_one(f"#details-{entity.name}", Static)

        header_text = f"[bold {pc}]{entity.name}[/]"
        if entity.base_type:
            header_text += f"\n[dim]Base: {entity.base_type}[/]"
        header_text += f"\n[dim]Keys: {', '.join(entity.keys)}[/]"
        panel = Panel(header_text, title="Entity", box=box.ROUNDED)

        custom_count = len(entity.custom_fields)
        nav_count = len(entity.navigation)

        groups = group_entity_properties(entity)
        rtree = RichTree(f"[bold {pc}]{entity.name}[/]")

        if groups["keys"]:
            keys_branch = rtree.add(f"[{ac}]Keys[/]")
            for prop in groups["keys"]:
                keys_branch.add(f"[{pc}]{prop.name}[/] [dim]{prop.type}[/]")

        if groups["other_nav"]:
            nav_branch = rtree.add(f"[blue]Navigation[/] ({nav_count})")
            for nav in groups["other_nav"][:15]:
                target = nav.target_entity or "?"
                nav_branch.add(f"[{pc}]{nav.name}[/] -> [{sc}]{target}[/]")
            if len(groups["other_nav"]) > 15:
                nav_branch.add(f"[dim]... and {len(groups['other_nav']) - 15} more[/]")

        if groups["custom"]:
            custom_branch = rtree.add(f"[{ac}]Custom Fields[/] ({custom_count})")
            for prop in groups["custom"][:10]:
                label_hint = f' [dim]"{prop.label}"[/]' if prop.label else ""
                pick_hint = f' [magenta]{prop.picklist}[/]' if prop.picklist else ""
                custom_branch.add(f"[{pc}]{prop.name}[/] {prop.type}{label_hint}{pick_hint}")
            if custom_count > 10:
                custom_branch.add(f"[dim]... and {custom_count - 10} more[/]")

        summary = Text.from_markup(
            f"  [bold]{len(entity.properties)}[/] properties"
            f"  |  [bold]{custom_count}[/] custom fields"
            f"  |  [bold]{nav_count}[/] navigation\n"
        )

        details_widget.update(Group(panel, summary, rtree))

    # ── Properties sub-tab ────────────────────────────────────────

    def _setup_property_table(self) -> None:
        """Populate the Properties sub-tab DataTable."""
        entity = self.entity
        ac = VERCEL_THEME.accent

        prop_table = self.query_one(f"#prop-table-{entity.name}", DataTable)
        prop_table.add_column("Property", width=25, key="name")
        prop_table.add_column("Type", width=15, key="type")
        prop_table.add_column("Len", width=5, key="len")
        prop_table.add_column("Label", width=20, key="label")
        prop_table.add_column("Picklist", width=18, key="picklist")
        prop_table.add_column("Req", width=3, key="req")
        prop_table.add_column("C", width=3, key="create")
        prop_table.add_column("U", width=3, key="update")
        prop_table.add_column("Up", width=3, key="upsert")
        prop_table.add_column("Vis", width=3, key="vis")
        prop_table.add_column("Sort", width=4, key="sort")
        prop_table.add_column("Filt", width=4, key="filt")

        self._prop_rows = []
        for prop in sort_properties(entity.properties, entity.keys):
            is_key = prop.name in entity.keys
            row = (
                f"[{ac}]{prop.name}[/]" if is_key else prop.name,
                prop.type,
                prop.max_length or "",
                prop.label or "",
                prop.picklist or "",
                format_flag_check(prop.required or is_key),
                format_flag_check(prop.creatable),
                format_flag_check(prop.updatable),
                format_flag_check(prop.upsertable),
                format_flag_check(prop.visible),
                format_flag_check(prop.sortable),
                format_flag_check(prop.filterable),
            )
            self._prop_rows.append(row)
            prop_table.add_row(*row)

    def apply_filter(self, term: str) -> tuple[int, int]:
        """Filter the property table by fuzzy match.

        Args:
            term: The filter string (lowercase).

        Returns:
            Tuple of (matched_count, total_count).
        """
        self._table_filter = term
        try:
            prop_table = self.query_one(f"#prop-table-{self.entity.name}", DataTable)
        except Exception:
            return (0, 0)

        prop_table.clear()

        if not term:
            for row in self._prop_rows:
                prop_table.add_row(*row)
            return (len(self._prop_rows), len(self._prop_rows))

        matched = 0
        for row in self._prop_rows:
            row_text = " ".join(str(c) for c in row).lower()
            if _fuzzy_match(term, row_text):
                prop_table.add_row(*row)
                matched += 1
        return (matched, len(self._prop_rows))


def _fuzzy_match(pattern: str, text: str) -> bool:
    """Check if all characters in *pattern* appear in order in *text*.

    Args:
        pattern: Lowercase search pattern.
        text: Lowercase text to match against.

    Returns:
        ``True`` if every character of *pattern* appears sequentially in *text*.
    """
    it = iter(text)
    return all(c in it for c in pattern)
