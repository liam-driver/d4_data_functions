import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from core.get_run_rate import tat_get_run_rate

# Maps budget sheet abbreviations to raw funnel data Department column values
FORBES_DEPARTMENT_MAP = {
    'Brand': 'Brand',
    'Crime': 'Crime',
    'Clin Neg': 'Clinical Negligence',
    'ConWills': 'Contentious & Wills',
    'Equine': 'Equine',
    'Director Insolvency': 'Director Insolvency',
    'IP': 'Intellectual Property',
    'Corporate': 'Corporate',
}

_TOLATA_LABEL = 'Tolata Campaign'
_BUDGET_SHEET_KEYS = set(FORBES_DEPARTMENT_MAP.keys()) | {_TOLATA_LABEL}

STATUS_EMOJI = {"pass": "✅", "warn": "⚠️", "fail": "🔴", "skip": "➖"}


def load_forbes_department_budgets():
    """Read Traps & Tripwires Budgets tab. Returns {raw_dept_name: budget_float}."""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name('storage/creds.json', scope)
    sa = gspread.authorize(creds)
    sh = sa.open('Weekly Reports')
    ws = sh.worksheet('Traps & Tripwires Budgets')
    rows = ws.get_all_values()

    client_col = budget_col = header_row_idx = None
    for i, row in enumerate(rows):
        stripped = [c.strip() for c in row]
        budget_match = next((j for j, c in enumerate(stripped) if 'budget' in c.lower()), None)
        client_match = next((j for j, c in enumerate(stripped) if c.lower() == 'client'), None)
        if budget_match is not None and client_match is not None:
            budget_col = budget_match
            client_col = client_match
            header_row_idx = i
            break

    if budget_col is None or header_row_idx is None:
        return {}

    forbes_start = None
    for i in range(header_row_idx + 1, len(rows)):
        if 'Forbes' in rows[i][client_col].strip():
            forbes_start = i + 1
            break

    if forbes_start is None:
        return {}

    dept_budgets = {}
    for i in range(forbes_start, len(rows)):
        cell = rows[i][client_col].strip()
        if not cell:
            continue
        if cell not in _BUDGET_SHEET_KEYS:
            break
        if cell == _TOLATA_LABEL:
            continue
        budget_str = (
            rows[i][budget_col].strip()
            .replace('Â', '').replace('£', '').replace(',', '')
        )
        try:
            budget = float(budget_str) if budget_str else 0.0
        except ValueError:
            budget = 0.0
        dept_budgets[FORBES_DEPARTMENT_MAP[cell]] = budget

    return dept_budgets


def _dept_col(df):
    """Return the actual Department column name, tolerating trailing whitespace."""
    return next((c for c in df.columns if c.strip() == 'Department'), None)


def get_forbes_raw_departments(df):
    """Return sorted department names from funnel data, excluding noise."""
    col = _dept_col(df)
    if col is None:
        return []
    excluded = {'', 'Unknown', 'Tolata Campaign'}
    return sorted(d for d in df[col].unique() if d not in excluded)


def check_department_budget_pacing(client, df, dept_name, dept_budget):
    """Budget pacing for a single Forbes department. Returns (status, detail)."""
    col = _dept_col(df)
    dept_df = df[df[col] == dept_name].copy().reset_index(drop=True)
    date_mask = (
        (dept_df['Date'] >= client['start_date']) &
        (dept_df['Date'] <= client['end_date'])
    )
    dept_df = dept_df.loc[date_mask]
    spend = pd.to_numeric(dept_df.iloc[:, 11], errors='coerce').sum() if not dept_df.empty else 0.0

    if dept_budget is None:
        return 'skip', f"No budget configured — spend to date £{spend:,.0f}"
    if dept_budget == 0:
        return 'skip', f"Department paused — spend to date £{spend:,.0f}"

    run_rate = tat_get_run_rate(client, spend)
    pacing_pct = run_rate / dept_budget
    detail = (
        f"Spend to date £{spend:,.0f}. "
        f"Tracking at £{run_rate:,.0f} vs £{dept_budget:,.0f} expected ({pacing_pct:.0%} of pace)"
    )
    if pacing_pct > 1.2 or pacing_pct < 0.7:
        return 'fail', detail
    if pacing_pct > 1.1 or pacing_pct < 0.85:
        return 'warn', detail
    return 'pass', detail


def run_forbes_department_checks(client, df, dept_budgets):
    """Returns list of (dept_name, (status, detail)) for departments with an active budget (> 0)."""
    results = []
    for dept_name, budget in dept_budgets.items():
        if budget <= 0:
            continue
        result = check_department_budget_pacing(client, df, dept_name, budget)
        results.append((dept_name, result))
    return results


def build_forbes_dept_block(dept_name, pacing_result):
    """Slack section block for one Forbes department (budget pacing only)."""
    status, detail = pacing_result
    lines = [
        f"*{dept_name}* {STATUS_EMOJI[status]}",
        f"• Budget Pacing {STATUS_EMOJI[status]}",
        f"   • {detail}",
    ]
    return {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}
