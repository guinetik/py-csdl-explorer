"""
SAP SuccessFactors OData client.

Async HTTP client supporting Basic and OAuth2 SAML Bearer authentication
for fetching picklist values from SAP SuccessFactors OData APIs.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx


AUTH_TYPES = ("none", "bearer", "basic", "oauth2")
"""Supported authentication types."""


@dataclass
class SAPConnection:
    """OData connection configuration.

    Supports four authentication types:
    - ``none``: No authentication.
    - ``bearer``: Static Bearer token.
    - ``basic``: Username/password authentication.
    - ``oauth2``: OAuth2 SAML Bearer assertion flow.

    Args:
        base_url: Base URL of the OData service (e.g. ``https://api.sap.com/odata/v2``).
        auth_type: Authentication type — ``"none"``, ``"bearer"``, ``"basic"``, or ``"oauth2"``.
        bearer_token: Static Bearer token.
        username: Username for Basic auth.
        password: Password for Basic auth.
        idp_url: Identity Provider URL for SAML assertion (OAuth2).
        token_url: Token endpoint URL (OAuth2).
        client_id: OAuth2 client ID.
        user_id: SAP user ID (OAuth2).
        company_id: SAP company ID (OAuth2).
        private_key: Private key for signing SAML assertion (OAuth2).
        grant_type: OAuth2 grant type.
    """

    base_url: str = ""
    auth_type: str = "none"
    # Bearer token
    bearer_token: str = ""
    # Basic
    username: str = ""
    password: str = ""
    # OAuth2 SAML Bearer
    idp_url: str = ""
    token_url: str = ""
    client_id: str = ""
    user_id: str = ""
    company_id: str = ""
    private_key: str = ""
    grant_type: str = "urn:ietf:params:oauth:grant-type:saml2-bearer-assertion"

    _ENV_MAP = {
        "SAP_BASE_URL": "base_url",
        "SAP_AUTH_TYPE": "auth_type",
        "SAP_BEARER_TOKEN": "bearer_token",
        "SAP_USERNAME": "username",
        "SAP_PASSWORD": "password",
        "SAP_IDP_URL": "idp_url",
        "SAP_TOKEN_URL": "token_url",
        "SAP_CLIENT_ID": "client_id",
        "SAP_USER_ID": "user_id",
        "SAP_COMPANY_ID": "company_id",
        "SAP_PRIVATE_KEY": "private_key",
        "SAP_GRANT_TYPE": "grant_type",
    }

    def to_env_dict(self) -> dict[str, str]:
        """Serialize connection to env-file key=value pairs.

        Returns:
            Dict mapping ``SAP_*`` keys to their values.
        """
        inv = {v: k for k, v in self._ENV_MAP.items()}
        return {inv[attr]: getattr(self, attr) for attr in inv if getattr(self, attr)}

    @classmethod
    def from_env_dict(cls, d: dict[str, str]) -> "SAPConnection":
        """Deserialize connection from env-file key=value pairs.

        Args:
            d: Dict mapping ``SAP_*`` keys to values.

        Returns:
            SAPConnection instance.
        """
        kwargs = {}
        for env_key, attr in cls._ENV_MAP.items():
            if env_key in d:
                kwargs[attr] = d[env_key]
        return cls(**kwargs)


def save_env_file(path, connection: SAPConnection) -> None:
    """Write a ``.env`` file from a SAPConnection.

    Args:
        path: File path to write.
        connection: Connection to serialize.
    """
    lines = []
    for key, value in connection.to_env_dict().items():
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_env_file(path) -> dict[str, str]:
    """Read a ``.env`` file into a dict.

    Args:
        path: File path to read.

    Returns:
        Dict mapping keys to values (comments and blank lines skipped).
    """
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


class SAPClient:
    """Async HTTP client for SAP SuccessFactors OData.

    Args:
        connection: SAP connection configuration.
    """

    def __init__(self, connection: SAPConnection):
        self.connection = connection
        self._access_token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def authenticate(self) -> None:
        """Authenticate with the OData service.

        - ``none`` / ``basic`` / ``bearer``: No-op (credentials sent per-request).
        - ``oauth2``: Performs SAML Bearer assertion flow to obtain access token.

        Raises:
            RuntimeError: On authentication failure.
        """
        if self.connection.auth_type in ("none", "basic", "bearer"):
            return

        if self.connection.auth_type == "oauth2":
            client = await self._get_client()
            form_headers = {"Content-Type": "application/x-www-form-urlencoded"}

            # Step 1: POST to IDP to get SAML assertion
            idp_payload = {
                "client_id": self.connection.client_id,
                "user_id": self.connection.user_id,
                "token_url": self.connection.token_url,
                "private_key": self.connection.private_key,
            }
            idp_resp = await client.post(
                self.connection.idp_url, data=idp_payload, headers=form_headers,
            )
            if idp_resp.status_code >= 400:
                body = idp_resp.text[:500]
                raise RuntimeError(f"IDP error {idp_resp.status_code}: {body}")
            assertion = idp_resp.text

            # Step 2: Exchange assertion for access token
            token_payload = {
                "client_id": self.connection.client_id,
                "user_id": self.connection.user_id,
                "grant_type": self.connection.grant_type,
                "company_id": self.connection.company_id,
                "assertion": assertion,
            }
            token_resp = await client.post(
                self.connection.token_url, data=token_payload, headers=form_headers,
            )
            if token_resp.status_code >= 400:
                body = token_resp.text[:500]
                raise RuntimeError(f"Token error {token_resp.status_code}: {body}")
            token_data = token_resp.json()
            self._access_token = token_data.get("access_token", "")

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Send an authenticated HTTP request.

        Applies auth credentials based on connection type. All API methods
        should use this instead of calling the client directly.
        """
        client = await self._get_client()
        headers = dict(headers or {})
        auth = None

        if self.connection.auth_type == "basic":
            auth = httpx.BasicAuth(self.connection.username, self.connection.password)
        elif self.connection.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self.connection.bearer_token}"
        elif self.connection.auth_type == "oauth2":
            headers["Authorization"] = f"Bearer {self._access_token}"
        # "none" — no auth added

        return await client.request(
            method, url, params=params, headers=headers, auth=auth,
        )

    async def query_entity(
        self,
        entity_set: str,
        params: dict[str, str],
    ) -> tuple[list[dict], str]:
        """Execute an OData GET query against an entity set.

        Args:
            entity_set: The entity set name (e.g. ``"PerPerson"``).
            params: OData query parameters (``$select``, ``$filter``, etc.).

        Returns:
            Tuple of (results list of dicts, full URL string for preview).

        Raises:
            RuntimeError: On HTTP errors.
        """
        url = f"{self.connection.base_url.rstrip('/')}/{entity_set}"
        query = {"$format": "json"}
        if "$top" not in params:
            query["$top"] = "20"
        query.update(params)

        resp = await self._request(
            "GET", url, params=query, headers={"Accept": "application/json"},
        )
        full_url = str(resp.url)

        if resp.status_code >= 400:
            try:
                body = resp.text[:500]
            except Exception:
                body = ""
            raise RuntimeError(
                f"HTTP {resp.status_code} from {full_url}\n{body}"
            )

        data = resp.json()
        results = data.get("d", {}).get("results", [])
        return results, full_url

    async def get_picklist_values(self, picklist_name: str) -> list[dict]:
        """Fetch picklist option values from the SAP OData API.

        Args:
            picklist_name: The picklist identifier (e.g. ``"ecJobCode"``).

        Returns:
            List of dicts with keys ``id``, ``externalCode``, and ``labels``
            (a dict mapping locale codes to label strings).

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        url = (
            f"{self.connection.base_url.rstrip('/')}"
            f"/Picklist('{picklist_name}')/picklistOptions"
        )
        params = {
            "$format": "json",
            "$select": "id,externalCode,picklistLabels/label",
            "$expand": "picklistLabels",
        }

        resp = await self._request(
            "GET", url, params=params, headers={"Accept": "application/json"},
        )

        if resp.status_code >= 400:
            try:
                body = resp.text[:500]
            except Exception:
                body = ""
            raise RuntimeError(
                f"HTTP {resp.status_code} from {resp.url}\n{body}"
            )
        data = resp.json()

        results = []
        for option in data.get("d", {}).get("results", []):
            labels = {}
            for lbl in option.get("picklistLabels", {}).get("results", []):
                # Extract locale from __metadata.uri: .../locale='en_US'...
                meta_uri = lbl.get("__metadata", {}).get("uri", "")
                locale_match = re.search(r"locale='([^']+)'", meta_uri)
                locale = locale_match.group(1) if locale_match else "unknown"
                labels[locale] = lbl.get("label", "")
            results.append({
                "id": str(option.get("id", "")),
                "externalCode": option.get("externalCode", ""),
                "labels": labels,
            })

        return results

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
