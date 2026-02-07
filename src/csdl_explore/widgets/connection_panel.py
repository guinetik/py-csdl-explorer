"""Reusable OData connection panel — Base URL, auth type, and credential configuration."""

from textual.containers import Horizontal
from textual.widgets import Static, Input, Select, Button, Collapsible
from textual.message import Message
from textual import on


class ConnectionPanel(Collapsible):
    """Base URL + auth type selector + configure button.

    Posts ``ConnectionPanel.ConnectionChanged`` when credentials are saved.
    The parent widget reads ``connection`` to get the current ``SAPConnection``.

    Args:
        panel_id: Unique ID suffix for namespacing child widgets.
        title: Collapsible title (default ``"Auth"``).
    """

    DEFAULT_CSS = """
    ConnectionPanel .cp-base-url {
        width: 1fr;
        margin: 0 1;
    }

    ConnectionPanel .cp-spacer {
        height: 1;
    }

    ConnectionPanel .cp-auth-row {
        height: 3;
        padding: 0 1;
    }

    ConnectionPanel .cp-auth-select {
        width: 20;
    }

    ConnectionPanel .cp-auth-row Button {
        margin: 0 0 0 2;
    }
    """

    class ConnectionChanged(Message):
        """Posted when credentials are configured and saved."""

        def __init__(self, connection) -> None:
            super().__init__()
            self.connection = connection

    def __init__(self, panel_id: str, title: str = "Auth") -> None:
        super().__init__(title=title, id=f"cp-section-{panel_id}")
        self._panel_id = panel_id

    def compose(self):
        pid = self._panel_id
        yield Static("Base URL", classes="q-section-label")
        yield Input(
            placeholder="https://api.sap.com/odata/v2",
            id=f"cp-base-url-{pid}",
            classes="cp-base-url",
        )
        yield Static(" ", classes="cp-spacer")
        with Horizontal(classes="cp-auth-row"):
            yield Select(
                [
                    ("None", "none"),
                    ("Bearer Token", "bearer"),
                    ("Basic Auth", "basic"),
                    ("OAuth2 SAML", "oauth2"),
                ],
                value="none",
                id=f"cp-auth-type-{pid}",
                allow_blank=False,
                classes="cp-auth-select",
            )
            yield Button(
                "Configure Credentials",
                id=f"cp-btn-configure-{pid}",
                variant="primary",
            )

    def on_mount(self) -> None:
        """Pre-fill from existing app.sap_connection."""
        conn = getattr(self.app, "sap_connection", None)
        if not conn:
            return
        pid = self._panel_id
        if conn.base_url:
            self.query_one(f"#cp-base-url-{pid}", Input).value = conn.base_url
        if conn.auth_type and conn.auth_type != "none":
            try:
                self.query_one(f"#cp-auth-type-{pid}", Select).value = conn.auth_type
            except Exception:
                pass

    @property
    def base_url(self) -> str:
        """Current base URL value."""
        return self.query_one(f"#cp-base-url-{self._panel_id}", Input).value.strip()

    @property
    def auth_type(self) -> str:
        """Current auth type selection."""
        sel = self.query_one(f"#cp-auth-type-{self._panel_id}", Select)
        return sel.value or "none"

    def build_connection(self, creds: dict | None = None):
        """Build a SAPConnection from current widget state + optional creds.

        Args:
            creds: Optional dict of credential fields from AuthModal.

        Returns:
            A ``SAPConnection`` instance.
        """
        from ..sap_client import SAPConnection

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

        return SAPConnection(
            base_url=self.base_url, auth_type=self.auth_type, **kwargs
        )

    def save_connection(self, conn) -> None:
        """Persist connection to app state and .env file, post message.

        Args:
            conn: ``SAPConnection`` to save.
        """
        self.app.sap_connection = conn

        metadata_path = getattr(self.app, "metadata_path", None)
        if metadata_path:
            from ..sap_client import save_env_file
            env_path = metadata_path.parent / f"{metadata_path.stem}.env"
            save_env_file(env_path, conn)
            self.app.notify(f"Saved credentials to {env_path.name}", timeout=3)

        self.post_message(self.ConnectionChanged(conn))

    @on(Button.Pressed)
    def _on_configure_pressed(self, event: Button.Pressed) -> None:
        """Open auth modal when Configure Credentials is clicked."""
        pid = self._panel_id
        if event.button.id != f"cp-btn-configure-{pid}":
            return

        from .auth_modal import AuthModal

        auth_type = self.auth_type
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
        self.app.push_screen(modal, self._on_auth_dismiss)

    def _on_auth_dismiss(self, creds) -> None:
        """Callback when auth modal is dismissed with credentials."""
        if creds is None:
            return
        conn = self.build_connection(creds)
        self.save_connection(conn)
