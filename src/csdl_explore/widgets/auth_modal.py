"""Modal screen for configuring SAP authentication credentials."""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button
from textual import on


class AuthModal(ModalScreen[dict | None]):
    """Modal dialog for entering auth credentials only.

    The auth_type determines which fields are shown:
    - ``"basic"``: Username + Password
    - ``"oauth2"``: IDP URL, Token URL, Client ID, User ID, Company ID,
      Private Key, Grant Type

    On Save, dismisses with a dict of credential fields.
    On Cancel, dismisses with ``None``.
    """

    DEFAULT_CSS = """
    AuthModal {
        align: center middle;
    }

    #auth-modal-container {
        width: 64;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        overflow-y: auto;
    }

    #auth-modal-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
        height: 1;
    }

    .field-label {
        margin-top: 1;
        height: 1;
        color: $text-muted;
    }

    .auth-input {
        height: 3;
    }

    #auth-buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    #auth-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, auth_type: str, prefill: dict | None = None):
        """
        Args:
            auth_type: ``"basic"`` or ``"oauth2"``.
            prefill: Optional dict of field values to pre-populate.
        """
        super().__init__()
        self._auth_type = auth_type
        self._prefill = prefill or {}

    def compose(self) -> ComposeResult:
        title = "Basic Credentials" if self._auth_type == "basic" else "OAuth2 SAML Bearer"
        with Vertical(id="auth-modal-container"):
            yield Static(title, id="auth-modal-title")

            if self._auth_type == "basic":
                yield Static("Username", classes="field-label")
                yield Input(placeholder="SAP username", id="input-username", classes="auth-input")
                yield Static("Password", classes="field-label")
                yield Input(placeholder="SAP password", id="input-password", password=True, classes="auth-input")
            else:
                yield Static("IDP URL", classes="field-label")
                yield Input(placeholder="https://idp.example.com/oauth/token", id="input-idp-url", classes="auth-input")
                yield Static("Token URL", classes="field-label")
                yield Input(placeholder="https://api.example.com/oauth/token", id="input-token-url", classes="auth-input")
                yield Static("Client ID", classes="field-label")
                yield Input(placeholder="OAuth2 client identifier", id="input-client-id", classes="auth-input")
                yield Static("User ID", classes="field-label")
                yield Input(placeholder="SAP user ID for assertion", id="input-user-id", classes="auth-input")
                yield Static("Company ID", classes="field-label")
                yield Input(placeholder="SAP company ID", id="input-company-id", classes="auth-input")
                yield Static("Private Key", classes="field-label")
                yield Input(placeholder="PEM private key for signing", id="input-private-key", password=True, classes="auth-input")
                yield Static("Grant Type", classes="field-label")
                yield Input(
                    placeholder="urn:ietf:params:oauth:grant-type:saml2-bearer-assertion",
                    id="input-grant-type",
                    classes="auth-input",
                )

            with Horizontal(id="auth-buttons"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        """Pre-fill fields from existing credentials."""
        field_map = {
            "username": "#input-username",
            "password": "#input-password",
            "idp_url": "#input-idp-url",
            "token_url": "#input-token-url",
            "client_id": "#input-client-id",
            "user_id": "#input-user-id",
            "company_id": "#input-company-id",
            "private_key": "#input-private-key",
            "grant_type": "#input-grant-type",
        }
        for key, selector in field_map.items():
            if key in self._prefill and self._prefill[key]:
                try:
                    self.query_one(selector, Input).value = self._prefill[key]
                except Exception:
                    pass

    @on(Button.Pressed, "#btn-save")
    def _on_save(self) -> None:
        """Collect field values and dismiss."""
        result = {}
        if self._auth_type == "basic":
            result["username"] = self.query_one("#input-username", Input).value.strip()
            result["password"] = self.query_one("#input-password", Input).value.strip()
        else:
            result["idp_url"] = self.query_one("#input-idp-url", Input).value.strip()
            result["token_url"] = self.query_one("#input-token-url", Input).value.strip()
            result["client_id"] = self.query_one("#input-client-id", Input).value.strip()
            result["user_id"] = self.query_one("#input-user-id", Input).value.strip()
            result["company_id"] = self.query_one("#input-company-id", Input).value.strip()
            result["private_key"] = self.query_one("#input-private-key", Input).value.strip()
            result["grant_type"] = self.query_one("#input-grant-type", Input).value.strip()
            # Default grant type if left empty
            if not result["grant_type"]:
                result["grant_type"] = "urn:ietf:params:oauth:grant-type:saml2-bearer-assertion"
        self.dismiss(result)

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self) -> None:
        """Dismiss without saving."""
        self.dismiss(None)
