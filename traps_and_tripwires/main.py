import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
import requests
from datetime import datetime, timedelta
from core.error_logger import log_error
from core.get_config import init_clients
from core.config_dates import config_dates
from core.get_funnel_data import initialise_df, apply_filters
from core.get_run_rate import tat_get_run_rate
from weekly_reports.generate_df import *

# ── CHECKS ────────────────────────────────────────────────────────────────────

def check_budget_pacing(client):
    """Returns (status, detail). Status is 'pass', 'warn', 'fail', or 'skip'."""
    budget_str = client.get('budget', '').strip()
    if not budget_str or budget_str == '-':
        return 'skip', 'No budget configured'
    date_range = {
        "start_date": client['start_date'],
        "end_date": client['end_date'],
    }

    df = initialise_df(client)
    df = apply_filters(df, client, ['Week number (ISO)', 'Ad Platform'], date_range)
    spend = pd.to_numeric(df.iloc[:,11], errors='coerce').sum()
    budget = float(budget_str.replace(',', ''))
    run_rate = tat_get_run_rate(client, spend)
    pacing_pct = run_rate / budget
    detail = f"Spend to date £{spend:,.0f}. Tracking at £{run_rate:,.0f} vs £{budget:,.0f} expected ({pacing_pct:.0%} of pace)"
    if pacing_pct > 1.2 or pacing_pct < 0.7:
        return 'fail', detail
    upper_warn = 1.0 if client['name'] == 'Defib' else 1.1
    if pacing_pct > upper_warn or pacing_pct < 0.85:
        return 'warn', detail
    return 'pass', detail


def check_conversion_tracking(client):
    date_range = {
        "start_date": client['end_date'] - timedelta(days=7),
        "end_date": client['end_date'],
    }
    df = initialise_df(client)
    df = apply_filters(df, client, ['Date', 'Channel'], date_range)

    daily = (
        df.groupby('Date')
        .apply(lambda x: pd.to_numeric(x.iloc[:, 11], errors='coerce').sum(), include_groups=False)
        .reset_index()
        .sort_values('Date')
    )

    streak = 0
    for val in reversed(daily.iloc[:, 1].values):
        if val == 0:
            streak += 1
        else:
            break

    total = int(daily.iloc[:, 1].sum())
    if streak >= 3:
        return 'fail', f"{streak} consecutive days with 0 conversions — potential tracking issue"
    if streak == 2:
        return 'warn', f"2 consecutive days with 0 conversions — possible tracking issue or data lag"
    return 'pass', f"{total:,} conversions recorded in last 7 days — no issues detected"


def check_campaign_spend(client):
    """Returns (status, detail)."""
    date_range = {
            "start_date": client['end_date'] - timedelta(days=3),
            "end_date": client['end_date'],
        }
    df = initialise_df(client)
    df = apply_filters(df, client, ['Ad Platform', 'Date'], date_range)
    if client['account_type'] == 'Ecommerce':
        df = paid_ecommerce(df, ['Date', 'Ad Platform'], '')
    else:
        df = paid_lead_gen(df, ['Date', 'Ad Platform'], '')
    
    platform_col = df.columns[0]
    date_col = df.columns[1]
    cost_col = df.columns[2]

    tracked_channels = {
        'Paid Social Video', 'Paid Social Static', 'Paid Search',
        'Display', 'Shopping', 'Combined', 'Performance Max', 'Video',
    }
    df = df[df[platform_col].isin(tracked_channels)]

    failing = []
    warning = []

    for platform in df[platform_col].unique():
        platform_df = df[df[platform_col] == platform].sort_values(date_col)
        daily_cost = pd.to_numeric(platform_df[cost_col], errors='coerce').fillna(0)

        streak = 0
        for val in reversed(daily_cost.values):
            if val == 0:
                streak += 1
            else:
                break

        if streak >= 3:
            failing.append(f"{platform} ({streak} days)")
        elif streak >= 2:
            warning.append(f"{platform} (2 days)")

    if failing:
        return 'fail', f"Zero spend detected: {', '.join(failing)}"
    if warning:
        return 'warn', f"Zero spend detected: {', '.join(warning)}"
    return 'pass', "All platforms spending normally"


def run_checks(client):
    return [
        {"name": "Budget Pacing",        "result": check_budget_pacing(client)},
        {"name": "Conversion Tracking",  "result": check_conversion_tracking(client)},
        {"name": "Campaign Spend",        "result": check_campaign_spend(client)},
    ]


# ── SLACK ─────────────────────────────────────────────────────────────────────

STATUS_EMOJI = {"pass": "✅", "warn": "⚠️", "fail": "🔴", "skip": "➖"}


def post_slack_message(token, channel, blocks, thread_ts=None):
    payload = {"channel": channel, "blocks": blocks}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    data = resp.json()
    if not data.get("ok"):
        log_error(f"Slack API error: {data.get('error')}")
    return data.get("ts")


def build_client_block(client_name, checks):
    statuses = [c["result"][0] for c in checks]
    if "fail" in statuses:
        worst = "fail"
    elif "warn" in statuses:
        worst = "warn"
    else:
        worst = "pass"

    lines = [f"*{client_name}* {STATUS_EMOJI[worst]}"]
    for check in checks:
        status, detail = check["result"]
        lines.append(f"• {check['name']} {STATUS_EMOJI[status]}")
        if detail:
            lines.append(f"   • {detail}")

    return {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}


def build_summary_blocks(client_results, date_str):
    error_clients, warning_clients, healthy_clients = [], [], []
    for client_name, checks in client_results:
        statuses = [c["result"][0] for c in checks]
        if "fail" in statuses:
            error_clients.append(client_name)
        elif "warn" in statuses:
            warning_clients.append(client_name)
        else:
            healthy_clients.append(client_name)

    sections = [f"📊 *Daily Account Health Check — {date_str}*"]
    if error_clients:
        sections.append(f"*{len(error_clients)} client{'s' if len(error_clients) != 1 else ''} with errors* 🔴\n• {', '.join(error_clients)}")
    if warning_clients:
        sections.append(f"*{len(warning_clients)} client{'s' if len(warning_clients) != 1 else ''} with warnings* ⚠️\n• {', '.join(warning_clients)}")
    if healthy_clients:
        sections.append(f"*{len(healthy_clients)} client{'s' if len(healthy_clients) != 1 else ''} healthy* ✅\n• {', '.join(healthy_clients)}")
    if not warning_clients and not error_clients:
        sections.append("_All checks passed — no action needed._")

    return [{"type": "section", "text": {"type": "mrkdwn", "text": "\n\n".join(sections)}}]


def build_thread_blocks(client_results):
    blocks = []
    for client_name, checks in sorted(client_results, key=lambda x: x[0]):
        if blocks:
            blocks.append({"type": "divider"})
        blocks.append(build_client_block(client_name, checks))
    return blocks


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    with open("storage/secrets.json") as f:
        secrets = json.load(f)

    slack_token = secrets["slack_bot_token"]
    slack_channel = "C093QSSCU1L"            #Official channel: C093QSSCU1L; Test: C05510P0Z7G

    with open("storage/config.json") as f:
        clients = json.load(f)

    date_str = datetime.today().strftime("%a %d %b")

    client_results = [] 
    client_channels = {}
    for client in clients:
        client = config_dates(client)
        client['end_date'] = client['end_date'] + timedelta(days=1)
        client_channels[client['name']] = client.get('slack_channel_id', '')
        try:
            checks = run_checks(client)
            client_results.append((client["name"], checks))
        except Exception as e:
            log_error(f"Checks failed for {client['name']}: {e}")

    summary_blocks = build_summary_blocks(client_results, date_str)
    thread_ts = post_slack_message(slack_token, slack_channel, summary_blocks)

    thread_blocks = build_thread_blocks(client_results)
    post_slack_message(slack_token, slack_channel, thread_blocks, thread_ts=thread_ts)

    for client_name, checks in client_results:
        statuses = [c["result"][0] for c in checks]
        if "fail" not in statuses:
            continue
        channel_id = client_channels.get(client_name, '')
        if not channel_id:
            continue
        post_slack_message(slack_token, channel_id, [build_client_block(client_name, checks)])

main()