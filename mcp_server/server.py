import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import secrets
import smtplib
import subprocess
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
TOKENS_PATH = os.path.join(PROJECT_ROOT, "storage", "tokens.json")

with open(os.path.join(PROJECT_ROOT, "storage", "secrets.json"), "r") as f:
    _secrets = json.load(f)

ISSUER_URL = _secrets.get("mcp_server_url", "")
if not ISSUER_URL:
    raise RuntimeError("mcp_server_url missing from secrets.json — set it to your Cloudflare tunnel URL")


class SimpleOAuthProvider(OAuthAuthorizationServerProvider):
    """
    OAuth provider for the weekly reports MCP server. Auto-authorizes all requests —
    access control is enforced upstream by Cloudflare Access (door4.com Google accounts only).
    Tokens are persisted to storage/tokens.json and survive server restarts.
    """

    def __init__(self):
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._access_tokens: dict[str, AccessToken] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}
        self._load()

    def _load(self):
        if not os.path.exists(TOKENS_PATH):
            return
        try:
            with open(TOKENS_PATH, "r") as f:
                data = json.load(f)
            now = time.time()
            for k, v in data.get("access_tokens", {}).items():
                if v.get("expires_at") and v["expires_at"] > now:
                    self._access_tokens[k] = AccessToken.model_validate(v)
            for k, v in data.get("refresh_tokens", {}).items():
                self._refresh_tokens[k] = RefreshToken.model_validate(v)
            for k, v in data.get("clients", {}).items():
                self._clients[k] = OAuthClientInformationFull.model_validate(v)
        except Exception:
            pass

    def _save(self):
        data = {
            "access_tokens": {k: v.model_dump(mode="json") for k, v in self._access_tokens.items()},
            "refresh_tokens": {k: v.model_dump(mode="json") for k, v in self._refresh_tokens.items()},
            "clients": {k: v.model_dump(mode="json") for k, v in self._clients.items()},
        }
        with open(TOKENS_PATH, "w") as f:
            json.dump(data, f, indent=2)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clients[client_info.client_id] = client_info
        self._save()

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
        self._save()
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
        self._save()
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
        self._save()


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


def _validate_client_name(client_name: str) -> None:
    config_path = os.path.join(PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        clients = json.load(f)
    known = [c["name"] for c in clients]
    if client_name not in known:
        raise ValueError(f"Unknown client '{client_name}'. Known clients: {known}")


@mcp.tool()
def fetch_client_data(client_name: str) -> str:
    """Fetch all performance data for a client. Returns the full data JSON needed to generate commentary."""
    _validate_client_name(client_name)
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
def fetch_monthly_client_data(client_name: str) -> str:
    """Fetch monthly performance data for a client. Returns MoM, YoY, and 90-day timeseries as three top-level sections."""
    _validate_client_name(client_name)
    script = os.path.join(PROJECT_ROOT, "monthly_reports", "main.py")
    result = subprocess.run(
        [sys.executable, script, "--client", client_name, "--data-only"],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        raise Exception(f"Monthly data fetch failed: {result.stderr}")
    data_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_monthly_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        client = json.load(f)
    structured = {
        "mom": {
            "paid_data": client.get("paid_data_mom"),
            "llm_data": client.get("llm_data_mom"),
            "overall_data": client.get("overall_data_mom"),
        },
        "yoy": {
            "paid_data": client.get("paid_data_yoy"),
            "llm_data": client.get("llm_data_yoy"),
            "overall_data": client.get("overall_data_yoy"),
        },
        "timeseries": client.get("timeseries_data"),
    }
    return json.dumps(structured, ensure_ascii=False)


@mcp.tool()
def send_weekly_report(client_name: str, commentary: str) -> str:
    """Send the weekly report email for a client. commentary must be a JSON string matching the report schema."""
    _validate_client_name(client_name)
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


@mcp.tool()
def send_weekly_report_html(client_name: str, html_body: str) -> str:
    """Send the weekly report email with a pre-rendered HTML body. Use this with the interactive weekly-report skill — call it once the user has approved the draft."""
    _validate_client_name(client_name)
    secrets_path = os.path.join(PROJECT_ROOT, "storage", "secrets.json")
    with open(secrets_path, "r", encoding="utf-8") as f:
        _secrets_data = json.load(f)

    msg = MIMEMultipart()
    msg['From'] = _secrets_data["email"]
    msg['Subject'] = f"{client_name} Weekly Report"
    msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(_secrets_data["email"], _secrets_data["password"])
        smtp.sendmail(_secrets_data["email"], _secrets_data["send_email"], msg.as_string())

    return f"Weekly report sent successfully for {client_name}"


@mcp.tool()
def get_available_dimensions(client_name: str) -> str:
    """Return the dimension options available for a client's raw data export.
    Reads the client's Google Sheet headers and cross-references against the
    dimension allowlist in storage/dimension_config.json.
    Returns a JSON array of {column_name, label, requires_channel_filter} objects."""
    _validate_client_name(client_name)
    config_path = os.path.join(PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        clients = json.load(f)
    client = next(c for c in clients if c["name"] == client_name)
    from monthly_reports.dimension_cuts import get_available_dimensions as _get_dims
    dimensions = _get_dims(client)
    return json.dumps(dimensions, ensure_ascii=False)


@mcp.tool()
def fetch_dimension_cut(client_name: str, dimension: str, channel_filter: str = "") -> str:
    """Fetch MoM comparison data for a dimension cut and append it to the cached monthly JSON.
    dimension: the column_name from dimension_config.json (e.g. 'Campaign').
    channel_filter: optional JSON string with shape {"type": "include"|"exclude", "channels": [...]}.
                    Pass an empty string for no filter.
    Returns a JSON object with the fetched data_mom and generated commentary."""
    _validate_client_name(client_name)
    parsed_filter = None
    if channel_filter and channel_filter.strip():
        parsed_filter = json.loads(channel_filter)
    from monthly_reports.dimension_cuts import fetch_and_append_dimension_cut
    cut_entry = fetch_and_append_dimension_cut(client_name, dimension, parsed_filter)
    return json.dumps(cut_entry, ensure_ascii=False)


@mcp.tool()
def generate_monthly_pptx(client_name: str, slide_content: str) -> str:
    """Generate the monthly PPTX for a client from pre-generated slide content.
    slide_content must be a JSON string with keys: overview (summary, bullets),
    trends (list of title/summary/bullets/graph objects), and actions (list of
    task/summary/status/graph objects). Returns a JSON object with 'path' and
    'download_url' — share the download_url with the user so they can download
    the file directly."""
    _validate_client_name(client_name)
    from monthly_reports.generate_ppt import generate_ppt
    content = json.loads(slide_content)
    output_path = generate_ppt(client_name, slide_content=content)
    filename = os.path.basename(output_path)
    download_url = f"{ISSUER_URL}/files/{filename}"
    return json.dumps({"path": output_path, "download_url": download_url}, ensure_ascii=False)


if __name__ == "__main__":
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import FileResponse, JSONResponse
    from starlette.requests import Request

    async def download_file(request: Request):
        filename = request.path_params["filename"]
        slides_dir = os.path.join(PROJECT_ROOT, "slides")
        file_path = os.path.join(slides_dir, filename)
        if not os.path.abspath(file_path).startswith(os.path.abspath(slides_dir)):
            return JSONResponse({"error": "Not found"}, status_code=404)
        if not os.path.isfile(file_path) or not filename.endswith(".pptx"):
            return JSONResponse({"error": "Not found"}, status_code=404)
        return FileResponse(file_path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")

    app = Starlette(routes=[
        Route("/files/{filename}", download_file),
        Mount("/", app=mcp.streamable_http_app()),
    ])
    uvicorn.run(app, host="0.0.0.0", port=8000)
