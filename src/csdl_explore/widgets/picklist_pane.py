"""Picklist tab pane — shows Overview, Entities, Impact Analysis, and Get Values."""

from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, DataTable, TabbedContent, TabPane, Button, Input, RadioSet, RadioButton
from textual import on, work
from textual.message import Message

from rich.console import Group
from rich.panel import Panel
from rich.tree import Tree as RichTree
from rich import box

from ..explorer import CSDLExplorer
from ..parser import Property
from ..formatters import format_flag_check
from ..themes import VERCEL_THEME


class PicklistTabPane(TabPane):
    """A tab pane displaying Overview, Entities, Impact Analysis, and Get Values for one picklist.

    Args:
        name: The picklist name.
        picklist_data: Mapping of entity name to list of properties referencing this picklist.
        explorer: The CSDL explorer instance.
    """

    DEFAULT_CSS = """
    .getval-conn-row {
        height: 3;
        padding: 0 1;
        align: left middle;
    }

    .getval-conn-row Static {
        width: auto;
        padding: 0 1 0 0;
    }

    .getval-url-input {
        width: 1fr;
    }

    .getval-auth-label {
        padding: 0 1;
        height: 1;
    }

    .getval-auth-radio {
        height: auto;
        max-height: 6;
        padding: 0 1;
    }

    .getval-bar {
        height: 3;
        padding: 0 1;
        align: left middle;
    }

    .getval-bar Button {
        margin: 0 1 0 0;
    }

    .getval-status {
        padding: 0 1;
        height: auto;
    }
    """

    class EntitySelected(Message):
        """Posted when a user selects an entity row in the Entities sub-tab."""

        def __init__(self, entity_name: str) -> None:
            super().__init__()
            self.entity_name = entity_name

    def __init__(self, name: str, picklist_data: dict[str, list[Property]], explorer: CSDLExplorer):
        pane_id = f"picklist-{name}"
        super().__init__(name, id=pane_id)
        self.picklist_name = name
        self.picklist_data = picklist_data
        self.explorer = explorer

    def compose(self):
        pid = self.picklist_name
        with TabbedContent(id=f"pick-sub-{pid}"):
            with TabPane("Overview", id=f"pick-overview-{pid}"):
                with VerticalScroll():
                    yield Static(id=f"pick-details-{pid}")
            with TabPane("Entities", id=f"pick-entities-{pid}"):
                yield DataTable(
                    id=f"pick-entity-table-{pid}",
                    zebra_stripes=True,
                    cursor_type="row",
                )
            with TabPane("Impact Analysis", id=f"pick-impact-{pid}"):
                with VerticalScroll():
                    yield Static(id=f"pick-impact-summary-{pid}")
                    yield DataTable(
                        id=f"pick-impact-table-{pid}",
                        zebra_stripes=True,
                        cursor_type="row",
                    )
            with TabPane("Get Values", id=f"pick-getval-{pid}"):
                with Horizontal(classes="getval-conn-row"):
                    yield Static("Base URL")
                    yield Input(
                        placeholder="https://api.sap.com/odata/v2",
                        id=f"input-base-url-{pid}",
                        classes="getval-url-input",
                    )
                yield Static("Auth Type", classes="getval-auth-label")
                with RadioSet(id=f"auth-type-{pid}", classes="getval-auth-radio"):
                    yield RadioButton("None", value=True)
                    yield RadioButton("Bearer")
                    yield RadioButton("Basic")
                    yield RadioButton("OAuth2")
                with Horizontal(classes="getval-bar"):
                    yield Button(
                        "Configure Credentials",
                        id=f"btn-configure-{pid}",
                        variant="primary",
                    )
                    yield Button(
                        "Fetch Values",
                        id=f"btn-fetch-{pid}",
                        variant="default",
                    )
                yield Static(
                    "[dim]Not connected[/]",
                    id=f"pick-getval-status-{pid}",
                    classes="getval-status",
                )
                yield DataTable(
                    id=f"pick-getval-table-{pid}",
                    zebra_stripes=True,
                    cursor_type="row",
                )

    def on_mount(self) -> None:
        """Render all sub-tabs after mount."""
        self._render_overview()
        self._setup_entities_table()
        self._setup_impact_table()
        self._prefill_connection()
        self._update_connection_status()

    # ── Get Values sub-tab ─────────────────────────────────────────

    _AUTH_INDEX = {"none": 0, "bearer": 1, "basic": 2, "oauth2": 3}
    _AUTH_NAMES = {v: k for k, v in _AUTH_INDEX.items()}

    def _prefill_connection(self) -> None:
        """Pre-fill Base URL and auth type from existing app.sap_connection."""
        conn = getattr(self.app, "sap_connection", None)
        if not conn:
            return
        pid = self.picklist_name
        if conn.base_url:
            self.query_one(f"#input-base-url-{pid}", Input).value = conn.base_url
        idx = self._AUTH_INDEX.get(conn.auth_type, 0)
        if idx != 0:
            try:
                radio = self.query_one(f"#auth-type-{pid}", RadioSet)
                radio.query(RadioButton)[idx].value = True
            except Exception:
                pass

    def _get_auth_type(self) -> str:
        """Read current auth type from the radio set."""
        pid = self.picklist_name
        radio = self.query_one(f"#auth-type-{pid}", RadioSet)
        return self._AUTH_NAMES.get(radio.pressed_index, "none")

    def _build_connection(self, creds: dict | None = None) -> "SAPConnection":
        """Build a SAPConnection from the inline fields + optional modal creds."""
        from ..sap_client import SAPConnection
        pid = self.picklist_name
        base_url = self.query_one(f"#input-base-url-{pid}", Input).value.strip()
        auth_type = self._get_auth_type()

        existing = getattr(self.app, "sap_connection", None)
        # Start from existing creds if no new ones provided
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

    def _update_connection_status(self) -> None:
        """Update the Get Values status label based on app.sap_connection."""
        status = self.query_one(f"#pick-getval-status-{self.picklist_name}", Static)
        conn = getattr(self.app, "sap_connection", None)
        if conn and conn.base_url:
            status.update(f"Connected to [bold]{conn.base_url}[/]")
        else:
            status.update("[dim]Not connected[/]")

    def _save_connection(self, conn) -> None:
        """Persist connection to app state and .env file."""
        self.app.sap_connection = conn
        self._update_connection_status()

        metadata_path = getattr(self.app, "metadata_path", None)
        if metadata_path:
            from ..sap_client import save_env_file
            env_path = metadata_path.parent / f"{metadata_path.stem}.env"
            save_env_file(env_path, conn)
            self.app.notify(f"Saved credentials to {env_path.name}", timeout=3)

    @on(Button.Pressed)
    def _on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Configure Credentials and Fetch Values buttons."""
        pid = self.picklist_name
        if event.button.id == f"btn-configure-{pid}":
            self._open_auth_modal()
        elif event.button.id == f"btn-fetch-{pid}":
            self._fetch_values()

    def _open_auth_modal(self) -> None:
        """Open the credentials modal for the selected auth type."""
        from .auth_modal import AuthModal

        auth_type = self._get_auth_type()
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
        self.app.push_screen(modal, self._on_auth_modal_dismiss)

    def _on_auth_modal_dismiss(self, creds) -> None:
        """Callback when the auth modal is dismissed."""
        if creds is None:
            return
        conn = self._build_connection(creds)
        self._save_connection(conn)

    @work(thread=False)
    async def _fetch_values(self) -> None:
        """Fetch picklist values from the SAP API."""
        pid = self.picklist_name
        base_url = self.query_one(f"#input-base-url-{pid}", Input).value.strip()
        if not base_url:
            self.app.notify("Enter a Base URL first", severity="warning")
            return

        # Build connection from current inline fields + stored creds
        conn = self._build_connection()
        # Save so base_url / auth_type changes are persisted
        self._save_connection(conn)

        status = self.query_one(f"#pick-getval-status-{pid}", Static)
        table = self.query_one(f"#pick-getval-table-{pid}", DataTable)

        status.update("[dim]Fetching...[/]")

        try:
            from ..sap_client import SAPClient

            client = SAPClient(conn)
            await client.authenticate()
            results = await client.get_picklist_values(self.picklist_name)
            await client.close()

            # Clear existing table
            table.clear(columns=True)

            if not results:
                status.update(f"Connected to [bold]{conn.base_url}[/] — no values found")
                return

            # Build columns dynamically: ID, Code, then one per locale
            locales = sorted({loc for item in results for loc in item["labels"]})
            table.add_column("ID", width=8, key="id")
            table.add_column("Code", width=10, key="code")
            for loc in locales:
                table.add_column(loc, width=18, key=f"label-{loc}")

            for item in results:
                table.add_row(
                    item["id"],
                    item["externalCode"],
                    *[item["labels"].get(loc, "") for loc in locales],
                )

            status.update(
                f"Connected to [bold]{conn.base_url}[/] — "
                f"[bold]{len(results)}[/] values, [bold]{len(locales)}[/] locales"
            )

        except Exception as e:
            status.update(f"[red]Error: {e}[/]")

    # ── Overview sub-tab ──────────────────────────────────────────

    def _render_overview(self) -> None:
        """Populate the Overview sub-tab with a panel and Rich tree."""
        wc = VERCEL_THEME.warning
        pc = VERCEL_THEME.primary

        entity_count = len(self.picklist_data)
        prop_count = sum(len(props) for props in self.picklist_data.values())

        header_text = f"[bold {wc}]{self.picklist_name}[/]"
        panel = Panel(header_text, title="Picklist", box=box.ROUNDED)

        summary = f"  Used by [bold]{entity_count}[/] entities across [bold]{prop_count}[/] properties\n"

        rtree = RichTree(f"[bold {wc}]{self.picklist_name}[/]")
        for entity_name in sorted(self.picklist_data):
            branch = rtree.add(f"[{pc}]{entity_name}[/]")
            for prop in self.picklist_data[entity_name]:
                label_hint = f' "{prop.label}"' if prop.label else ""
                branch.add(f"{prop.name} [dim]{prop.type}{label_hint}[/]")

        widget = self.query_one(f"#pick-details-{self.picklist_name}", Static)
        widget.update(Group(panel, summary, rtree))

    # ── Entities sub-tab ──────────────────────────────────────────

    def _setup_entities_table(self) -> None:
        """Populate the Entities DataTable."""
        table = self.query_one(f"#pick-entity-table-{self.picklist_name}", DataTable)
        table.add_column("Entity", width=25, key="entity")
        table.add_column("Property", width=20, key="property")
        table.add_column("Type", width=15, key="type")
        table.add_column("Label", width=20, key="label")
        table.add_column("Req", width=3, key="req")
        table.add_column("C", width=3, key="create")
        table.add_column("U", width=3, key="update")

        self._entity_rows: list[str] = []
        for entity_name in sorted(self.picklist_data):
            for prop in self.picklist_data[entity_name]:
                table.add_row(
                    entity_name,
                    prop.name,
                    prop.type,
                    prop.label or "",
                    format_flag_check(prop.required),
                    format_flag_check(prop.creatable),
                    format_flag_check(prop.updatable),
                )
                self._entity_rows.append(entity_name)

    @on(DataTable.RowSelected)
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the Entities table — post EntitySelected."""
        table_id = f"pick-entity-table-{self.picklist_name}"
        if event.data_table.id != table_id:
            return
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._entity_rows):
            self.post_message(self.EntitySelected(self._entity_rows[row_idx]))

    # ── Impact Analysis sub-tab ───────────────────────────────────

    def _setup_impact_table(self) -> None:
        """Populate the Impact Analysis summary and DataTable."""
        wc = VERCEL_THEME.warning

        # Compute stats
        required_props = []
        create_entities = set()
        for entity_name, props in self.picklist_data.items():
            for prop in props:
                if prop.required:
                    required_props.append((entity_name, prop))
                if prop.creatable:
                    create_entities.add(entity_name)

        summary_text = (
            f"  [{wc}]{len(required_props)}[/] required properties — "
            f"changes affect create operations on [{wc}]{len(create_entities)}[/] entities\n"
        )
        self.query_one(f"#pick-impact-summary-{self.picklist_name}", Static).update(summary_text)

        table = self.query_one(f"#pick-impact-table-{self.picklist_name}", DataTable)
        table.add_column("Entity", width=25, key="entity")
        table.add_column("Property", width=20, key="property")
        table.add_column("Req", width=3, key="req")
        table.add_column("C", width=3, key="create")
        table.add_column("U", width=3, key="update")
        table.add_column("Up", width=3, key="upsert")
        table.add_column("Filt", width=4, key="filt")
        table.add_column("Sort", width=4, key="sort")

        for entity_name in sorted(self.picklist_data):
            for prop in self.picklist_data[entity_name]:
                table.add_row(
                    entity_name,
                    prop.name,
                    format_flag_check(prop.required),
                    format_flag_check(prop.creatable),
                    format_flag_check(prop.updatable),
                    format_flag_check(prop.upsertable),
                    format_flag_check(prop.filterable),
                    format_flag_check(prop.sortable),
                )
