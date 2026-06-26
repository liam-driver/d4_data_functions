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