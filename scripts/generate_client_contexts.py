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


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def optional(value: str, label: str) -> str:
    if value and str(value).strip() and str(value).strip() not in ("-", "FALSE"):
        return f"- **{label}**: {str(value).strip()}"
    return ""


def client_sections(client: dict, level: int) -> str:
    """Config / MCP Config / Plans sections for one client at the given heading level."""
    h = "#" * level

    # ── Config ────────────────────────────────────────────────────────────────
    config_lines = [
        f"- **Account Type**: {client.get('account_type', '')}",
        f"- **Dimension**: {client.get('dimension', '')}",
        f"- **Comparison**: {client.get('comparison_dates', '')}",
        f"- **Report Due**: {client.get('report_due_date', '')}",
    ]
    for line in [
        optional(client.get("slack_channel_id"), "Slack Channel"),
        optional(client.get("budget"), "Budget (Weekly Reports)"),
        optional(client.get("tat_budget"), "Budget (T&T)"),
        optional(client.get("dashboard"), "Dashboard"),
    ]:
        if line:
            config_lines.append(line)

    parts = [f"{h} Config\n\n" + "\n".join(config_lines) + "\n"]

    # ── MCP Config ────────────────────────────────────────────────────────────
    mcp_config = {
        "name": client["name"],
        "account_type": client.get("account_type", ""),
        "dimension": client.get("dimension", ""),
        "comparison_dates": client.get("comparison_dates", ""),
    }
    if client.get("plan"):
        mcp_config["plan"] = client["plan"]
    parts.append(
        f"{h} MCP Config\n\n"
        "Pass this JSON verbatim as `client_config` when calling `fetch_client_data` or "
        "`fetch_monthly_client_data`. Do not rebuild it from the fields above.\n\n"
        "```json\n" + json.dumps(mcp_config, indent=2) + "\n```\n"
    )

    # ── Plans ─────────────────────────────────────────────────────────────────
    plan_lines = []
    if client.get("plan"):
        plan_lines.append(f"- **PPC Plan**: {client['plan']}")
    if client.get("cro_plan"):
        plan_lines.append(f"- **CRO Plan**: {client['cro_plan']}")
    if client.get("seo_plan"):
        plan_lines.append(f"- **SEO Plan**: {client['seo_plan']}")

    if plan_lines:
        parts.append(
            f"{h} Plans\n\n"
            "Pass the relevant URL as `sheet_url` to `fetch_plan_data` (PPC), "
            "`fetch_cro_plan_data` (CRO), or `fetch_seo_plan_data` (SEO). "
            "Weekly reports use the PPC plan only; CRO and SEO plans are for "
            "the monthly report.\n\n"
            + "\n".join(plan_lines) + "\n"
        )
    else:
        parts.append(f"{h} Plans\n\n_No plans configured._\n")

    return "\n".join(parts)


def generate_markdown(project: str, clients: list) -> str:
    parts = [
        f"# {project} — Door4 Reporting Tools (MCP Config)\n",
        "Config for the D4 Data Functions MCP tools (weekly reports, monthly "
        "reports, plan fetchers).\n",
    ]

    if len(clients) == 1:
        parts.append(client_sections(clients[0], level=2))
    else:
        names = ", ".join(f'"{c["name"]}"' for c in clients)
        parts.append(
            f"This project covers {len(clients)} data-function clients: {names}. "
            "Reports and plan fetches run separately for each — use the block "
            "matching the client being reported on.\n"
        )
        for client in clients:
            parts.append(f"## {client['name']}\n")
            parts.append(client_sections(client, level=3))

    return "\n".join(parts)


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
