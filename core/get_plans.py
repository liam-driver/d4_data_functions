from __future__ import annotations

import calendar
import datetime as dt
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import json

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _auth_sheets():
    secrets_path = os.path.join(_PROJECT_ROOT, "storage", "secrets.json")
    with open(secrets_path, "r") as f:
        secrets = json.load(f)
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets["google_service_account"], scope)
    return gspread.authorize(creds)


def _build_client_plan_from_worksheets(client_name, worksheets):
    client_plans = {}
    for i, sheet in enumerate(worksheets):
        values = sheet.get_all_values()
        df = pd.DataFrame(values)
        df.replace("", np.nan, inplace=True)
        weeks = get_weeks(df)
        plan_type = "current" if i == 0 else "old"
        plan = {
            "client_name": client_name,
            "plan_start": weeks[0].strftime("%d/%m/%y"),
            "plan_end": (weeks[-1] + pd.Timedelta(days=5)).strftime("%d/%m/%y"),
            "plan_status": plan_type,
            "tasks": get_tasks(df),
        }
        client_plans[sheet.title] = plan
    return client_plans


def get_client_plan(client_name: str) -> dict | None:
    """Fetch the 90-day plan for a single client directly from Google Sheets."""
    config_path = os.path.join(_PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r") as f:
        clients = json.load(f)
    client = next((c for c in clients if c["name"] == client_name), None)
    if client is None or not client.get("plan"):
        return None
    sa = _auth_sheets()
    sh = sa.open_by_url(client["plan"])
    return _build_client_plan_from_worksheets(client_name, sh.worksheets())


def build_plan_json_from_sheet():
    sa = _auth_sheets()
    config_path = os.path.join(_PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r") as config_json:
        clients = json.load(config_json)
    plans = {}
    for client in clients:
        sh = sa.open_by_url(client["plan"])
        plans[client["name"]] = _build_client_plan_from_worksheets(client["name"], sh.worksheets())
    output_path = os.path.join(_PROJECT_ROOT, "storage", "plans.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(plans, f, ensure_ascii=False, indent=2)
    return 0

# Create a list of all the dates that are used in the sheet to get a start and end date for the overall plan
def get_weeks(df):
    date_row_candidates = df.iloc[3].tolist()
    dates_cleaned = (
        pd.to_datetime(date_row_candidates, dayfirst=True, errors="coerce")
            .dropna()
            .tolist() 
        )
    return(dates_cleaned)        

# Convert the google sheet tasks into a json object that can be added to the plans json
def get_tasks(df):
    # Check for misconfigured headers
    header_row_candidates = df.index[df[1] == "Task"]
    if len(header_row_candidates) == 0:
        raise ValueError("Could not find a 'Task' header in column 1.")
    
    # Get the right range of DF
    df = df.iloc[2:, 1:7]
    df.columns = df.iloc[0].astype(str).str.strip()
    df = df.iloc[1:].reset_index(drop=True) 
    cat = df["Category"].fillna("").astype(str).str.strip()
    mask = (cat == "Active Workstream") | (cat == "")
    df = df.loc[mask]

    df["Start Date"] = pd.to_datetime(df["Start Date"], dayfirst=True, errors="coerce", utc=True)
    df["End Date"]   = pd.to_datetime(df["End Date"],   dayfirst=True, errors="coerce", utc=True)

    # Create a list of tasks, each task is a json objected appended to the 'task' list
    tasks=[]
    for idx, row in df.iterrows():
        if pd.isna(row["Description"]):
            ad_platform = row["Task"]
            continue
        tasks.append(
            {
                "name": row["Task"],
                "desc": row["Description"],
                "category": row["Category"],
                "status": row["Status"],
                "start_date": row["Start Date"].strftime("%d/%m/%y"),
                "end_date": row["End Date"].strftime("%d/%m/%y"),
                "platform": ad_platform,
            }
        )
    return tasks

def get_tasks_with_schedule(df):
    """Read all task categories (BAU, Active Workstream, Reporting) and include per-week
    hour allocations from the sheet's week columns. Used by the Scoro import/check skills."""
    raw_week_headers = df.iloc[3, 7:].tolist()
    week_dates = []
    for h in raw_week_headers:
        parsed = pd.to_datetime(h, dayfirst=True, errors="coerce")
        week_dates.append(parsed.strftime("%Y-%m-%d") if pd.notna(parsed) else None)

    header_row_candidates = df.index[df[1] == "Task"]
    if len(header_row_candidates) == 0:
        raise ValueError("Could not find a 'Task' header in column 1.")

    df_meta = df.iloc[2:, 1:7].copy()
    df_sched = df.iloc[2:, 7:].copy()

    df_meta.columns = df_meta.iloc[0].astype(str).str.strip()
    df_meta = df_meta.iloc[1:].reset_index(drop=True)
    df_sched = df_sched.iloc[1:].reset_index(drop=True)

    INCLUDED = {"Active Workstream", "BAU", "Reporting"}
    cat = df_meta["Category"].fillna("").astype(str).str.strip()
    mask = cat.isin(INCLUDED) | (cat == "")
    df_meta = df_meta.loc[mask].reset_index(drop=True)
    df_sched = df_sched.loc[mask].reset_index(drop=True)

    df_meta["Start Date"] = pd.to_datetime(df_meta["Start Date"], dayfirst=True, errors="coerce", utc=True)
    df_meta["End Date"] = pd.to_datetime(df_meta["End Date"], dayfirst=True, errors="coerce", utc=True)

    tasks = []
    ad_platform = None
    for i in range(len(df_meta)):
        row = df_meta.iloc[i]
        desc = row["Description"]
        if pd.isna(desc) or str(desc).strip() in ("", "nan"):
            ad_platform = row["Task"]
            continue

        schedule = {}
        sched_row = df_sched.iloc[i]
        for j, week_date in enumerate(week_dates):
            if week_date is None or j >= len(sched_row):
                continue
            try:
                hours = float(sched_row.iloc[j])
                if hours > 0:
                    schedule[week_date] = hours
            except (TypeError, ValueError):
                pass

        tasks.append({
            "name": row["Task"],
            "desc": str(desc).strip(),
            "category": str(row["Category"]).strip() if not pd.isna(row["Category"]) else "",
            "status": str(row["Status"]).strip() if not pd.isna(row["Status"]) else "",
            "start_date": row["Start Date"].strftime("%d/%m/%y") if pd.notna(row["Start Date"]) else None,
            "end_date": row["End Date"].strftime("%d/%m/%y") if pd.notna(row["End Date"]) else None,
            "platform": ad_platform,
            "schedule": schedule,
        })
    return tasks


def _build_client_plan_with_schedule(client_name, worksheets):
    client_plans = {}
    for i, sheet in enumerate(worksheets):
        values = sheet.get_all_values()
        df = pd.DataFrame(values)
        df.replace("", np.nan, inplace=True)
        weeks = get_weeks(df)
        plan = {
            "client_name": client_name,
            "plan_start": weeks[0].strftime("%d/%m/%y"),
            "plan_end": (weeks[-1] + pd.Timedelta(days=5)).strftime("%d/%m/%y"),
            "plan_status": "current" if i == 0 else "old",
            "tasks": get_tasks_with_schedule(df),
        }
        client_plans[sheet.title] = plan
    return client_plans


def get_client_plan_with_schedule(client_name: str) -> dict | None:
    """Fetch the 90-day plan with per-week hour allocations for all task categories."""
    config_path = os.path.join(_PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r") as f:
        clients = json.load(f)
    client = next((c for c in clients if c["name"] == client_name), None)
    if client is None or not client.get("plan"):
        return None
    sa = _auth_sheets()
    sh = sa.open_by_url(client["plan"])
    return _build_client_plan_with_schedule(client_name, sh.worksheets())


if __name__ == "__main__":
    build_plan_json_from_sheet()


# ---------------------------------------------------------------------------
# CRO plan parsing
# ---------------------------------------------------------------------------

def _find_cro_header_and_dates(df):
    """Return (header_row_idx, week_col_dates) for a CRO plan DataFrame.
    header_row_idx: row index of the column-name row (contains 'Category').
    week_col_dates: list of (col_idx, pd.Timestamp) for date-header columns.
    """
    header_row_idx = None
    for i in range(len(df)):
        row_vals = df.iloc[i].astype(str).str.strip().tolist()
        if "Category" in row_vals:
            header_row_idx = i
            break
    if header_row_idx is None:
        raise ValueError("Could not find a 'Category' header row in CRO plan.")

    # Date row is the first row after the header that has ≥ 2 parseable dates
    week_col_dates = []
    for i in range(header_row_idx + 1, min(header_row_idx + 6, len(df))):
        row = df.iloc[i]
        parsed = pd.to_datetime(row, dayfirst=True, errors="coerce")
        candidates = [(j, d) for j, d in enumerate(parsed) if pd.notna(d)]
        if len(candidates) >= 2:
            week_col_dates = candidates
            break

    return header_row_idx, week_col_dates


def get_cro_tasks(df):
    """Parse CRO plan tasks from a DataFrame. Reads by column-header name to handle
    varying schemas across clients (e.g. RICE columns only on some sheets)."""
    header_row_idx, week_col_dates = _find_cro_header_and_dates(df)

    # Map column-name → index from header row, stripping whitespace
    header_row = df.iloc[header_row_idx]
    col_map = {}
    for j, val in enumerate(header_row):
        key = str(val).strip() if pd.notna(val) else ""
        if key and key != "nan":
            col_map[key] = j

    # Workstream field varies by client: "Workstream", "Workstream " (space), or "KPI"
    workstream_idx = col_map.get("Workstream") or col_map.get("Workstream ") or col_map.get("KPI")

    _NA = {"", "nan", "n/a", "N/A"}

    def _val(row, name):
        idx = col_map.get(name)
        if idx is None or idx >= len(row):
            return None
        v = row.iloc[idx]
        if pd.isna(v):
            return None
        s = str(v).strip()
        return None if s in _NA else s

    start_row = header_row_idx + 1
    # Skip to the row after the date-header row if we found one
    if week_col_dates:
        # The date row is somewhere between header+1 and header+5; find it
        for i in range(header_row_idx + 1, header_row_idx + 6):
            if i >= len(df):
                break
            row = df.iloc[i]
            parsed = pd.to_datetime(row, dayfirst=True, errors="coerce")
            if parsed.notna().sum() >= 2:
                start_row = i + 1
                break

    INCLUDED = {"Active Workstream", "BAU"}
    tasks = []

    for i in range(start_row, len(df)):
        row = df.iloc[i]
        category = _val(row, "Category")
        if category not in INCLUDED:
            continue
        name = _val(row, "Name")
        if not name:
            continue

        raw_start = _val(row, "Start Date") or ""
        raw_end = _val(row, "End Date") or ""
        start_date = pd.to_datetime(raw_start, dayfirst=True, errors="coerce", utc=True)
        end_date = pd.to_datetime(raw_end, dayfirst=True, errors="coerce", utc=True)

        schedule = {}
        for j, week_ts in week_col_dates:
            if j >= len(row):
                continue
            try:
                hours = float(row.iloc[j])
                if hours > 0:
                    schedule[week_ts.strftime("%Y-%m-%d")] = hours
            except (TypeError, ValueError):
                pass

        platform = None
        if workstream_idx is not None and workstream_idx < len(row):
            v = row.iloc[workstream_idx]
            if pd.notna(v):
                s = str(v).strip()
                if s not in _NA:
                    platform = s

        task = {
            "name": name,
            "idea": _val(row, "Idea"),
            "hypothesis": _val(row, "Hypothesis"),
            "objective": _val(row, "Objective"),
            "platform": platform,
            "facs": _val(row, "F-A-C-S"),
            "test_or_jdi": _val(row, "Test/JDI"),
            "category": category,
            "status": _val(row, "Status"),
            "start_date": start_date.strftime("%d/%m/%y") if pd.notna(start_date) else None,
            "end_date": end_date.strftime("%d/%m/%y") if pd.notna(end_date) else None,
            "schedule": schedule,
        }

        for field in ("Reach", "Impact", "Confidence", "Effort", "Score"):
            raw = _val(row, field)
            if raw is not None:
                try:
                    task[field.lower()] = float(raw)
                except ValueError:
                    pass

        tasks.append(task)

    return tasks


def _build_client_cro_plan(client_name, worksheets):
    client_plans = {}
    for i, sheet in enumerate(worksheets):
        values = sheet.get_all_values()
        df = pd.DataFrame(values)
        df.replace("", np.nan, inplace=True)
        _, week_col_dates = _find_cro_header_and_dates(df)
        plan_start = week_col_dates[0][1] if week_col_dates else None
        plan_end = (week_col_dates[-1][1] + pd.Timedelta(days=5)) if week_col_dates else None
        plan = {
            "client_name": client_name,
            "plan_start": plan_start.strftime("%d/%m/%y") if plan_start is not None else None,
            "plan_end": plan_end.strftime("%d/%m/%y") if plan_end is not None else None,
            "plan_status": "current" if i == 0 else "old",
            "tasks": get_cro_tasks(df),
        }
        client_plans[sheet.title] = plan
    return client_plans


def get_client_cro_plan(client_name: str) -> dict | None:
    """Fetch the current CRO 90-day plan for a client from Google Sheets."""
    config_path = os.path.join(_PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r") as f:
        clients = json.load(f)
    client = next((c for c in clients if c["name"] == client_name), None)
    if client is None or not client.get("cro_plan"):
        return None
    sa = _auth_sheets()
    sh = sa.open_by_url(client["cro_plan"])
    return _build_client_cro_plan(client_name, sh.worksheets())


# ---------------------------------------------------------------------------
# SEO plan parsing
# ---------------------------------------------------------------------------

def _is_yellow(cell: dict) -> bool:
    """Return True if the cell has the #fff2cc background used in SEO plans."""
    bg = cell.get("effectiveFormat", {}).get("backgroundColor", {})
    if not bg:
        return False
    r = bg.get("red", 1.0)
    g = bg.get("green", 1.0)
    b = bg.get("blue", 1.0)
    # #fff2cc ≈ (1.0, 0.949, 0.800) in 0–1 float
    return abs(r - 1.0) < 0.02 and abs(g - 0.949) < 0.02 and abs(b - 0.800) < 0.02


def _cell_text(cell: dict) -> str:
    fv = cell.get("formattedValue", "")
    if fv:
        return str(fv).strip()
    ev = cell.get("effectiveValue", {})
    if "stringValue" in ev:
        return str(ev["stringValue"]).strip()
    if "numberValue" in ev:
        return str(ev["numberValue"])
    return ""


def get_seo_tasks_from_sheet_grid(sheet_meta: dict) -> tuple:
    """Parse SEO tasks from one sheet's grid data dict (one element of sheets[]).
    Returns (tasks, plan_start_str, plan_end_str).
    Active periods are determined by #fff2cc cell background colour.
    """
    today = dt.date.today()

    try:
        row_data = sheet_meta["data"][0]["rowData"]
    except (KeyError, IndexError):
        return [], None, None

    rows = []
    for rd in row_data:
        cells = rd.get("values", [])
        rows.append(
            ([_cell_text(c) for c in cells],
             [_is_yellow(c) for c in cells])
        )

    # Find the date header row: first row with ≥ 2 parseable dates
    date_row_idx = None
    week_col_dates = []  # list of (col_idx, dt.date)
    for i, (texts, _) in enumerate(rows):
        parsed = []
        for j, v in enumerate(texts):
            try:
                ts = pd.to_datetime(v, dayfirst=True)
                if pd.notna(ts):
                    parsed.append((j, ts.date()))
            except Exception:
                pass
        if len(parsed) >= 2:
            date_row_idx = i
            week_col_dates = parsed
            break

    # Fallback: month-name headers (no week dates in sheet)
    is_monthly = False
    if date_row_idx is None:
        for i, (texts, _) in enumerate(rows):
            parsed = []
            ref_year = today.year
            prev_month = 0
            for j, v in enumerate(texts):
                try:
                    month_num = pd.to_datetime(v, format="%B").month
                    if month_num < prev_month:
                        ref_year += 1
                    parsed.append((j, dt.date(ref_year, month_num, 1)))
                    prev_month = month_num
                except Exception:
                    pass
            if len(parsed) >= 2:
                date_row_idx = i
                week_col_dates = parsed
                is_monthly = True
                break

    if not week_col_dates:
        return [], None, None

    # Determine column spacing to confirm week vs month resolution
    if len(week_col_dates) >= 2:
        spacing = (week_col_dates[1][1] - week_col_dates[0][1]).days
        is_monthly = spacing > 14

    plan_start_str = week_col_dates[0][1].strftime("%d/%m/%y")
    last_date = week_col_dates[-1][1]
    if is_monthly:
        last_day = calendar.monthrange(last_date.year, last_date.month)[1]
        plan_end_str = dt.date(last_date.year, last_date.month, last_day).strftime("%d/%m/%y")
    else:
        plan_end_str = (last_date + dt.timedelta(days=6)).strftime("%d/%m/%y")

    tasks = []
    current_section = None

    for i, (texts, yellows) in enumerate(rows):
        if i <= date_row_idx:
            continue

        first_val = texts[0] if texts else ""
        if not first_val:
            continue

        yellow_week_cols = [
            (j, d) for j, d in week_col_dates
            if j < len(yellows) and yellows[j]
        ]

        if not yellow_week_cols:
            # Section header if short single-line text; otherwise unscheduled task → skip
            if "\n" not in first_val and len(first_val) <= 60:
                current_section = first_val.strip()
            continue

        parts = first_val.split("\n", 1)
        name = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else ""
        if not name:
            continue

        start_date = yellow_week_cols[0][1]
        raw_end = yellow_week_cols[-1][1]
        if is_monthly:
            last_day = calendar.monthrange(raw_end.year, raw_end.month)[1]
            end_date = dt.date(raw_end.year, raw_end.month, last_day)
        else:
            end_date = raw_end + dt.timedelta(days=6)

        if end_date < today:
            status = "Complete"
        elif start_date <= today:
            status = "In Progress"
        else:
            status = "Scheduled"

        tasks.append({
            "name": name,
            "desc": desc,
            "category": "Active Workstream",
            "status": status,
            "start_date": start_date.strftime("%d/%m/%y"),
            "end_date": end_date.strftime("%d/%m/%y"),
            "platform": current_section,
        })

    return tasks, plan_start_str, plan_end_str


def _build_client_seo_plan(client_name: str, spreadsheet) -> dict:
    grid_data = spreadsheet.fetch_sheet_metadata(params={"includeGridData": "true"})
    client_plans = {}
    for i, sheet_meta in enumerate(grid_data.get("sheets", [])):
        title = sheet_meta.get("properties", {}).get("title", f"Sheet{i + 1}")
        tasks, plan_start, plan_end = get_seo_tasks_from_sheet_grid(sheet_meta)
        client_plans[title] = {
            "client_name": client_name,
            "plan_start": plan_start,
            "plan_end": plan_end,
            "plan_status": "current" if i == 0 else "old",
            "tasks": tasks,
        }
    return client_plans


def get_client_seo_plan(client_name: str) -> dict | None:
    """Fetch the SEO plan for a client using cell-colour parsing via the Sheets API."""
    config_path = os.path.join(_PROJECT_ROOT, "storage", "config.json")
    with open(config_path, "r") as f:
        clients = json.load(f)
    client = next((c for c in clients if c["name"] == client_name), None)
    if client is None or not client.get("seo_plan"):
        return None
    sa = _auth_sheets()
    sh = sa.open_by_url(client["seo_plan"])
    return _build_client_seo_plan(client_name, sh)