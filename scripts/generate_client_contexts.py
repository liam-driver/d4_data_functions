#!/usr/bin/env python3
"""Generate per-project MCP config docs from config.json.

Run from the project root:
    python scripts/generate_client_contexts.py

Outputs one .md file per Claude Enterprise project into storage/client_contexts/,
containing only the operational config the D4 Data Functions MCP tools need
(Config, MCP Config, Plans). Add each file to the project — either uploaded as
its own knowledge file or pasted as a section of the project's knowledge doc.

Where one Claude project covers multiple data-function clients (see
PROJECT_GROUPS), the clients are combined into a single doc with one block each.

Prose context (strategy, KPIs, seasonality, history) is NOT generated: the
team-maintained project knowledge doc is authoritative for narrative content.
"""

import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# One Claude project can cover multiple data-function clients. Map client name
# (as in config.json) → project name; unmapped clients get their own doc.
# Kept here rather than in config.json because get_config.py regenerates
# config.json from the sheet and would wipe any extra fields.
PROJECT_GROUPS = {
    "Paintnuts": "Nuts Group",
    "Paintnuts Trade": "Nuts Group",
    "Harrisons Direct (Registrations)": "Harrisons Direct",
    "Harrisons Direct (Revenue)": "Harrisons Direct",
    "Revival Beds (Transactions)": "Revival Beds",
    "Revival Beds (Showroom Visits)": "Revival Beds",
    "MacFarlane UK": "MacFarlane",
    "MacFarlane IE": "MacFarlane",
}

# Which Weekly Report commentary style (see ppc-weekly-report.md) each client
# uses. Map client name (as in config.json) → style; unmapped clients get
# DEFAULT_REPORT_STYLE. Kept here rather than in config.json for the same
# reason as PROJECT_GROUPS: get_config.py regenerates config.json from the
# sheet and would wipe any extra fields. All clients are "standard" today.
REPORT_STYLES: dict[str, str] = {}
DEFAULT_REPORT_STYLE = "standard"


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


DIVIDER = "─" * 41


def optional(value, label: str) -> str:
    if value and str(value).strip() and str(value).strip() not in ("-", "FALSE"):
        return str(value).strip(), label
    return None, None


def client_block(client: dict) -> str:
    lines = []

    # ── Config fields ─────────────────────────────────────────────────────────
    fields = [
        ("Account Type",  client.get("account_type", "")),
        ("Dimension",     client.get("dimension", "")),
        ("Comparison",    client.get("comparison_dates", "")),
        ("Report Due",    client.get("report_due_date", "")),
        ("Report Style",  REPORT_STYLES.get(client["name"], DEFAULT_REPORT_STYLE)),
    ]
    for label, value in fields:
        if value and str(value).strip():
            lines.append(f"{label + ':':<18}{str(value).strip()}")

    for raw_label, raw_key in [
        ("Slack Channel",  "slack_channel_id"),
        ("Budget",         "budget"),
        ("Dashboard",      "dashboard"),
    ]:
        val, lbl = optional(client.get(raw_key), raw_label)
        if val:
            lines.append(f"{lbl + ':':<18}{val}")

    lines.append("")

    # ── MCP Config ────────────────────────────────────────────────────────────
    mcp_config = {
        "name": client["name"],
        "account_type": client.get("account_type", ""),
        "dimension": client.get("dimension", ""),
        "comparison_dates": client.get("comparison_dates", ""),
        "report_style": REPORT_STYLES.get(client["name"], DEFAULT_REPORT_STYLE),
    }
    if client.get("plan"):
        mcp_config["plan"] = client["plan"]

    lines.append(
        "When calling fetch_client_data or fetch_monthly_client_data, pass the\n"
        "JSON block below VERBATIM as client_config — do not rebuild it from prose."
    )
    lines.append("")
    lines.append("client_config:")
    lines.append(json.dumps(mcp_config, indent=2))
    lines.append("")

    # ── Plans ─────────────────────────────────────────────────────────────────
    plan_lines = []
    if client.get("plan"):
        plan_lines.append(f"  PPC: {client['plan']}")
    if client.get("cro_plan"):
        plan_lines.append(f"  CRO: {client['cro_plan']}")
    if client.get("seo_plan"):
        plan_lines.append(f"  SEO: {client['seo_plan']}")

    if plan_lines:
        lines.append(
            "When calling fetch_plan_data (PPC), fetch_cro_plan_data (CRO), or\n"
            "fetch_seo_plan_data (SEO), pass the relevant URL as sheet_url.\n"
            "Weekly reports use the PPC plan only; CRO and SEO plans are for\n"
            "the Monthly Report Skeleton (d4-monthly-skeleton)."
        )
        lines.append("")
        lines.append("Plans:")
        lines.extend(plan_lines)
    else:
        lines.append("Plans: none configured.")

    return "\n".join(lines)


def generate_markdown(project: str, clients: list) -> str:
    parts = [
        DIVIDER,
        "13. DOOR4 REPORTING TOOLS — MCP CONFIG",
        DIVIDER,
        "Config for the D4 Data Functions MCP tools (weekly reports, monthly",
        "reports, plan fetchers).",
    ]

    if len(clients) == 1:
        parts += ["", client_block(clients[0])]
    else:
        names = " and ".join(f'"{c["name"]}"' for c in clients)
        parts += [
            f"This project covers {len(clients)} data-function clients: {names}.",
            "Use the block matching the client being reported on.",
        ]
        for i, client in enumerate(clients, start=1):
            parts += [
                "",
                f"13.{i} {client['name'].upper()}",
                DIVIDER,
                "",
                client_block(client),
            ]

    return "\n".join(parts) + "\n"


def main():
    config_path = os.path.join(PROJECT_ROOT, "storage", "config.json")
    output_dir = os.path.join(PROJECT_ROOT, "storage", "client_contexts")
    os.makedirs(output_dir, exist_ok=True)

    with open(config_path, "r", encoding="utf-8") as f:
        clients = json.load(f)

    projects: dict[str, list] = {}
    for client in clients:
        project = PROJECT_GROUPS.get(client["name"], client["name"])
        projects.setdefault(project, []).append(client)

    for project, project_clients in projects.items():
        slug = slugify(project)
        output_path = os.path.join(output_dir, f"{slug}.md")
        content = generate_markdown(project, project_clients)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        client_names = ", ".join(c["name"] for c in project_clients)
        print(f"  {project} ({client_names}) → {slug}.md")

    print(f"\n{len(projects)} files written to {output_dir}/")


if __name__ == "__main__":
    main()
