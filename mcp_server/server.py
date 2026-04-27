import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import secrets
import subprocess
import time

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.server.auth.provider import (
    OAuthAuthorizationServerProvider,
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(PROJECT_ROOT, "storage", "secrets.json"), "r") as f:
    _secrets = json.load(f)

ISSUER_URL = _secrets.get("mcp_server_url", "")
if not ISSUER_URL:
    raise RuntimeError("mcp_server_url missing from secrets.json — set it to your Cloudflare tunnel URL")


class SimpleOAuthProvider(OAuthAuthorizationServerProvider):
    """
    Minimal in-memory OAuth provider for the weekly reports MCP server.
    Auto-authorizes all requests — access control is handled by Claude enterprise
    org membership, so anyone in the org who connects gets a token automatically.
    Tokens are in-memory only; Claude enterprise will re-authorize on server restart.
    """

    def __init__(self):
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._access_tokens: dict[str, AccessToken] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clients[client_info.client_id] = client_info

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        code = secrets.token_urlsafe(32)
        self._auth_codes[code] = AuthorizationCode(
            code=code,
            client_id=client.client_id,
            scopes=params.scopes or [],
            expires_at=time.time() + 300,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._auth_codes.get(authorization_code)
        if code and code.client_id == client.client_id:
            return code
        return None

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        del self._auth_codes[authorization_code.code]
        access_token_str = secrets.token_urlsafe(32)
        refresh_token_str = secrets.token_urlsafe(32)
        self._access_tokens[access_token_str] = AccessToken(
            token=access_token_str,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 86400,
        )
        self._refresh_tokens[refresh_token_str] = RefreshToken(
            token=refresh_token_str,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
        )
        return OAuthToken(
            access_token=access_token_str,
            token_type="bearer",
            expires_in=86400,
            refresh_token=refresh_token_str,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        at = self._access_tokens.get(token)
        if at and (at.expires_at is None or at.expires_at > time.time()):
            return at
        return None

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rt = self._refresh_tokens.get(refresh_token)
        if rt and rt.client_id == client.client_id:
            return rt
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],  # noqa: ignored — we preserve the existing token scopes
    ) -> OAuthToken:
        del self._refresh_tokens[refresh_token.token]
        for token_str, at in list(self._access_tokens.items()):
            if at.client_id == client.client_id:
                del self._access_tokens[token_str]
        access_token_str = secrets.token_urlsafe(32)
        new_refresh_str = secrets.token_urlsafe(32)
        self._access_tokens[access_token_str] = AccessToken(
            token=access_token_str,
            client_id=client.client_id,
            scopes=refresh_token.scopes,
            expires_at=int(time.time()) + 86400,
        )
        self._refresh_tokens[new_refresh_str] = RefreshToken(
            token=new_refresh_str,
            client_id=client.client_id,
            scopes=refresh_token.scopes,
        )
        return OAuthToken(
            access_token=access_token_str,
            token_type="bearer",
            expires_in=86400,
            refresh_token=new_refresh_str,
            scope=" ".join(refresh_token.scopes),
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            self._access_tokens.pop(token.token, None)
        else:
            self._refresh_tokens.pop(token.token, None)


mcp = FastMCP(
    "weekly-reports",
    auth_server_provider=SimpleOAuthProvider(),
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    auth=AuthSettings(
        issuer_url=ISSUER_URL,
        resource_server_url=ISSUER_URL,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["mcp"],
            default_scopes=["mcp"],
        ),
    ),
)


@mcp.tool()
def list_clients() -> str:
    """List all available clients for weekly report generation."""
    config_path = os.path.join(PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        clients = json.load(f)
    return json.dumps([c["name"] for c in clients])


@mcp.tool()
def fetch_client_data(client_name: str) -> str:
    """Fetch all performance data for a client. Returns the full data JSON needed to generate commentary."""
    script = os.path.join(PROJECT_ROOT, "weekly_reports", "fetch_data.py")
    result = subprocess.run(
        [sys.executable, script, "--client", client_name],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        raise Exception(f"Data fetch failed: {result.stderr}")
    data_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def send_weekly_report(client_name: str, commentary: str) -> str:
    """Send the weekly report email for a client. commentary must be a JSON string matching the report schema."""
    commentary_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_commentary.json")
    with open(commentary_path, "w", encoding="utf-8") as f:
        json.dump(json.loads(commentary), f, ensure_ascii=False, indent=2)
    script = os.path.join(PROJECT_ROOT, "weekly_reports", "send_email.py")
    result = subprocess.run(
        [sys.executable, script, "--client", client_name],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        raise Exception(f"Email send failed: {result.stderr}")
    return f"Weekly report sent successfully for {client_name}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=8000)
