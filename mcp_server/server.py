import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base64
import glob as _glob
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
        "mtd": {
            "paid_data": client.get("paid_data_mtd"),
            "llm_data": client.get("llm_data_mtd"),
            "overall_data": client.get("overall_data_mtd"),
            "start_date": client.get("mtd_start_date_string"),
            "end_date": client.get("mtd_end_date_string"),
        },
        "plan": client.get("plan_json"),
    }
    return json.dumps(structured, ensure_ascii=False)


@mcp.tool()
def fetch_plan_data(client_name: str) -> str:
    """Fetch the current 90-day plan for a client with per-week hour allocations across all
    task categories (BAU, Active Workstream, Reporting). Used by ppc-90day-import and
    ppc-90day-check skills. Returns a dict keyed by sheet tab name; use the entry where
    plan_status == 'current'. Each task includes a 'schedule' dict of {YYYY-MM-DD: hours}."""
    _validate_client_name(client_name)
    from core.get_plans import get_client_plan_with_schedule
    plan = get_client_plan_with_schedule(client_name)
    if plan is None:
        raise Exception(f"No 90-day plan configured for client: {client_name}")
    return json.dumps(plan, ensure_ascii=False)


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
def fetch_custom_overview_data(client_name: str, start_date: str, end_date: str) -> str:
    """Fetch overview data for a Custom Date Window and append it to the cached monthly JSON.

    Runs both comparison passes for the window:
      - Same-length prior period (MoM-equivalent)
      - Same window one year prior (YoY)

    Results are stored under paid_data_custom_{start_date}_{end_date} with mom/yoy sub-keys.
    Matching llm_data_* and overall_data_* keys are also written. Resolved date strings are
    stored so the PPTX generator can build date labels without recomputing them.

    client_name: the client name as it appears in config.json.
    start_date:  Custom Date Window start in YYYY-MM-DD format.
    end_date:    Custom Date Window end in YYYY-MM-DD format.

    Returns a JSON object listing the stored data keys and resolved date strings."""
    _validate_client_name(client_name)
    script = os.path.join(PROJECT_ROOT, "monthly_reports", "main.py")
    result = subprocess.run(
        [sys.executable, script, "--client", client_name,
         "--start-date", start_date, "--end-date", end_date],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        raise Exception(f"Custom overview fetch failed: {result.stderr}")
    data_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_monthly_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        client = json.load(f)
    window_prefix = f"custom_{start_date}_{end_date}"
    response = {
        "paid_data_key":    f"paid_data_{window_prefix}",
        "llm_data_key":     f"llm_data_{window_prefix}",
        "overall_data_key": f"overall_data_{window_prefix}",
        "start_date_string":         client.get(f"{window_prefix}_start_date_string"),
        "end_date_string":           client.get(f"{window_prefix}_end_date_string"),
        "compare_start_mom_string":  client.get(f"{window_prefix}_compare_start_mom_string"),
        "compare_end_mom_string":    client.get(f"{window_prefix}_compare_end_mom_string"),
        "compare_start_yoy_string":  client.get(f"{window_prefix}_compare_start_yoy_string"),
        "compare_end_yoy_string":    client.get(f"{window_prefix}_compare_end_yoy_string"),
    }
    return json.dumps(response, ensure_ascii=False)


@mcp.tool()
def fetch_trend_data(client_name: str, dimension: str, filters: str = "", time_dimension: str = "",
                     date_range: str = "mtd", start_date: str = "", end_date: str = "") -> str:
    """Fetch Previous Period, Previous Year, and timeseries data for a Trend Topic (Data Cut)
    broken down by dimension, with optional pre-aggregation scope filters.
    Use this once per trend slide during the slide-by-slide workflow.

    client_name: the client name as it appears in config.json.
    dimension: the column name to break down by (e.g. 'Campaign', 'Asset', 'Campaign Group', 'Ad Platform').
    filters: optional JSON array of filter objects applied to raw rows before grouping.
             Each filter: {"column": "<col>", "op": "<op>", "value": "<val>"}.
             column: any column in the raw data (e.g. 'Ad Channel', 'Ad Platform', 'Campaign').
             op: one of =, !=, contains, not_contains, >, <, >=, <=
             value: string, number, or array of strings (for = and !=).
             Example: [{"column": "Ad Channel", "op": "=", "value": "Paid Social"},
                       {"column": "Campaign", "op": "contains", "value": "MOFU"}]
             Leave empty to include all data.
    time_dimension: column to group the timeseries by. One of: 'Week number (ISO)', 'Month', 'Year', 'Date'.
                    Leave empty to use the recommended default for the selected date_range.
                    The graph spec's dimensions.x must match the time_dimension returned in the response.
    date_range: Templated Date Range for this slide. One of: 'previous_7_days', 'mtd' (default),
                'previous_month', 'ytd', 'last_90_days'. Controls the current period, previous period,
                and previous year windows — all with 2-day GA4 lag applied. 'ytd' omits the previous
                period comparison. Ignored when start_date and end_date are both provided.
    start_date: Custom Date Window start (YYYY-MM-DD). When provided with end_date, overrides date_range.
                Comparison windows are derived as same-length prior period + YoY.
    end_date:   Custom Date Window end (YYYY-MM-DD). See start_date.

    Persists the result to dimension_data[data_key] in the cached monthly JSON so the graph renderer
    can access it at PPTX build time.

    Returns a JSON envelope: {dimension, filters, date_range, date_range_label, data_key,
    time_dimension, default_time_dimension, prev_period_available, resolved_dates,
    previous_period, previous_year, timeseries}."""
    _validate_client_name(client_name)
    parsed_filters = None
    if filters and filters.strip():
        parsed_filters = json.loads(filters)
    from monthly_reports.dimension_cuts import fetch_trend_data as _fetch
    result = _fetch(
        client_name, dimension,
        parsed_filters, time_dimension or None, date_range,
        start_date=start_date or None, end_date=end_date or None,
    )
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def list_dimension_values(client_name: str, column: str, filters: str = "") -> str:
    """List unique values for a dimension column in the raw client data.

    Call this before fetch_trend_data when the user wants to filter by a specific dimension value
    (e.g. 'filter by the MOFU campaign') so you can see real values before constructing filters.

    client_name: the client name as it appears in config.json.
    column: the column to list values for (e.g. 'Campaign', 'Ad Channel', 'Ad Platform', 'Asset').
    filters: optional JSON array of filter objects to narrow the list before returning.
             Same schema as fetch_trend_data filters.
             Example: [{"column": "Ad Channel", "op": "=", "value": "Paid Social"}]
             Use this to scope the list (e.g. only show Paid Social campaigns).

    Returns a sorted list of unique non-null string values."""
    _validate_client_name(client_name)
    parsed_filters = None
    if filters and filters.strip():
        parsed_filters = json.loads(filters)
    from monthly_reports.dimension_cuts import list_dimension_values as _list
    values = _list(client_name, column, parsed_filters)
    return json.dumps(values, ensure_ascii=False)


def _render_markdown_table(headers, rows, totals_row):
    sep = ['---'] * len(headers)
    lines = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(sep) + ' |',
    ]
    for row in rows:
        lines.append('| ' + ' | '.join(str(c) for c in row) + ' |')
    if totals_row:
        lines.append('| ' + ' | '.join(f'**{c}**' for c in totals_row) + ' |')
    return '\n'.join(lines)


@mcp.tool()
def preview_graph(client_name: str, graph_spec: str) -> list:
    """Render a graph preview for a trend slide.

    For table and table_comparison graph types: returns a markdown table as text so it
    renders inline in the conversation. Filters, sort, and totals from the spec are applied.

    For all other graph types: returns the chart as an inline image.

    client_name: the client name as it appears in config.json.
    graph_spec: the graph spec JSON object serialised as a string — must match the Graph Schema
                in the monthly report instructions exactly.

    Raises an error (do not offer confirmation) if the spec is invalid or metrics are missing.
    """
    _validate_client_name(client_name)

    data_path = os.path.join(PROJECT_ROOT, "storage", f"{client_name}_monthly_data.json")
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"No cached data for '{client_name}' — run fetch_monthly_client_data first")

    with open(data_path, encoding="utf-8") as f:
        client_data = json.load(f)

    spec = json.loads(graph_spec)

    if spec.get('graph_type') in ('table', 'table_comparison'):
        from mcp.types import TextContent
        from monthly_reports.generate_ppt import render_table_data
        comparison = spec.get('graph_type') == 'table_comparison'
        headers, rows, totals_row = render_table_data(spec, client_data, comparison=comparison)
        if not headers:
            raise ValueError(
                "render_table_data returned empty — check that data_source and metrics exist in the fetched data"
            )
        md = _render_markdown_table(headers, rows, totals_row)
        return [TextContent(type="text", text=md)]

    from mcp.types import ImageContent
    from monthly_reports.generate_visualisation import render_graph, initialise_brand
    initialise_brand()

    path = render_graph(client_data, spec)
    if path is None:
        raise ValueError(
            "render_graph returned None — check that all metrics exist in the data "
            "and the graph_type is valid"
        )

    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    return [ImageContent(type="image", data=image_data, mimeType="image/png")]


@mcp.tool()
def generate_monthly_pptx(client_name: str, slide_content: str) -> str:
    """Generate the monthly PPTX for a client from pre-generated slide content.
    slide_content must be a JSON string with keys: overviews (list of paid overview slide
    items — each with data_key, section_title, title, summary, bullets,
    bullets_presentation, template, kpi_count, comparison), organic_overviews (optional
    list — single item with data_key='organic_data'; omit key entirely when not requested),
    cro_overviews (optional list — single item with data_key='cro_data'; omit key entirely
    when not requested), trends (list of title/summary/bullets/bullets_presentation/graph
    objects), and actions (list of task/summary/status objects). Organic and CRO sections
    are rendered after the 90-day plan Gantt. Always produces two decks: a detailed deck
    (full metric bullets) and a presentation deck (narrative-only bullets, data-free).
    Returns a JSON object with 'path', 'download_url', 'presentation_path', and
    'presentation_download_url' — share both download URLs with the user."""
    _validate_client_name(client_name)
    from monthly_reports.generate_ppt import generate_ppt
    content = json.loads(slide_content)
    output_path, presentation_path, excel_path = generate_ppt(client_name, slide_content=content)
    filename = os.path.basename(output_path)
    presentation_filename = os.path.basename(presentation_path)
    download_url = f"{ISSUER_URL}/files/{filename}"
    presentation_download_url = f"{ISSUER_URL}/files/{presentation_filename}"

    # Clean up generated files older than 7 days to avoid unbounded storage growth.
    slides_dir = os.path.join(PROJECT_ROOT, "slides")
    cutoff = time.time() - 7 * 86400
    protected = {
        os.path.abspath(output_path),
        os.path.abspath(presentation_path),
        os.path.abspath(excel_path) if excel_path else "",
    }
    for pattern in (f"{client_name}_monthly_*.pptx", f"{client_name}_monthly_*_data.xlsx"):
        for old_file in _glob.glob(os.path.join(slides_dir, pattern)):
            if os.path.getmtime(old_file) < cutoff and os.path.abspath(old_file) not in protected:
                try:
                    os.remove(old_file)
                except OSError:
                    pass

    result = {
        "path": output_path,
        "download_url": download_url,
        "presentation_path": presentation_path,
        "presentation_download_url": presentation_download_url,
    }
    if excel_path:
        excel_filename = os.path.basename(excel_path)
        result["excel_path"] = excel_path
        result["excel_download_url"] = f"{ISSUER_URL}/files/{excel_filename}"

    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    import uvicorn
    from starlette.responses import FileResponse, Response

    class FileDownloadMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http" and scope.get("path", "").startswith("/files/"):
                filename = scope["path"][len("/files/"):]
                slides_dir = os.path.join(PROJECT_ROOT, "slides")
                file_path = os.path.join(slides_dir, filename)
                _MEDIA_TYPES = {
                    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }
                _, ext = os.path.splitext(filename)
                if (os.path.abspath(file_path).startswith(os.path.abspath(slides_dir))
                        and os.path.isfile(file_path)
                        and ext in _MEDIA_TYPES):
                    response = FileResponse(
                        file_path,
                        filename=filename,
                        media_type=_MEDIA_TYPES[ext],
                    )
                else:
                    response = Response(content='{"error":"Not found"}', status_code=404, media_type="application/json")
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)

    uvicorn.run(FileDownloadMiddleware(mcp.streamable_http_app()), host="0.0.0.0", port=8000)
