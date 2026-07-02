import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from core.error_logger import log_error
from core.get_funnel_data import get_funnel_data
from core.get_run_rate import get_run_rate


class TimestampEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


def config_monthly_dates(client):
    """Derive date windows for the previous full calendar month plus MoM, YoY, and MTD comparisons."""
    now = pd.Timestamp.now()
    first_of_current_month = now.replace(day=1).normalize()

    # MoM/YoY window: always the previous full calendar month relative to today.
    start_date = (first_of_current_month - pd.DateOffset(months=1)).normalize()
    end_date = (start_date + MonthEnd(0)).normalize()

    compare_start_mom = (start_date - pd.DateOffset(months=1)).normalize()
    compare_end_mom = (compare_start_mom + MonthEnd(0)).normalize()

    compare_start_yoy = (start_date - pd.DateOffset(years=1)).normalize()
    compare_end_yoy = (compare_start_yoy + MonthEnd(0)).normalize()

    # MTD window: in the first 5 days of the month there are almost no current-month rows,
    # so show the just-completed previous month as a full MTD instead of a 2-day stub.
    if now.day <= 5:
        mtd_start_date = start_date
        mtd_end_date = end_date
    else:
        mtd_start_date = first_of_current_month
        mtd_end_date = (now - pd.DateOffset(days=2)).normalize()

    compare_start_mtd = (mtd_start_date - pd.DateOffset(years=1)).normalize()
    compare_end_mtd = (mtd_end_date - pd.DateOffset(years=1)).normalize()

    return (start_date, end_date, compare_start_mom, compare_end_mom,
            compare_start_yoy, compare_end_yoy,
            mtd_start_date, mtd_end_date, compare_start_mtd, compare_end_mtd)


def run_monthly_report(client_name, data_only=False):
    os.makedirs("charts", exist_ok=True)

    with open("storage/config.json", "r") as f:
        clients = json.load(f)

    client = next((c for c in clients if c['name'] == client_name), None)
    if client is None:
        raise ValueError(f"Client '{client_name}' not found in config")

    (start_date, end_date, compare_start_mom, compare_end_mom,
     compare_start_yoy, compare_end_yoy,
     mtd_start_date, mtd_end_date, compare_start_mtd, compare_end_mtd) = config_monthly_dates(client)

    client['start_date'] = start_date
    client['end_date'] = end_date
    client['start_date_string'] = start_date.strftime("%d/%m/%Y")
    client['end_date_string'] = end_date.strftime("%d/%m/%Y")

    if client.get("plan"):
        try:
            from core.get_plans import get_client_plan
            client["plan_json"] = get_client_plan(client["name"])
        except Exception as e:
            log_error(f"{client['name']} monthly_reports/main: 90 Day Plan fetch failed: {e}")
            raise

    account_type = client['account_type']
    paid_type = 'paid_lead_gen' if account_type == 'Lead Gen' else 'paid_ecommerce'
    llm_type = 'llm_lead_gen' if account_type == 'Lead Gen' else 'llm_ecommerce'
    overall_type = 'overall_lead_gen' if account_type == 'Lead Gen' else 'overall_ecommerce'
    ts_type = 'time_series_lead_gen' if account_type == 'Lead Gen' else 'time_series_ecommerce'

    try:
        # MoM comparison pass
        client['compare_start_date'] = compare_start_mom
        client['compare_end_date'] = compare_end_mom
        client['paid_data_mom'] = get_funnel_data(client, paid_type)
        client['llm_data_mom'] = get_funnel_data(client, llm_type)
        client['overall_data_mom'] = get_funnel_data(client, overall_type)

        # Store comparison dates explicitly so dimension cut fetches can reuse them
        client['compare_start_mom'] = compare_start_mom
        client['compare_end_mom']   = compare_end_mom
        client['compare_start_yoy'] = compare_start_yoy
        client['compare_end_yoy']   = compare_end_yoy

        # YoY comparison pass
        client['compare_start_date'] = compare_start_yoy
        client['compare_end_date'] = compare_end_yoy
        client['paid_data_yoy'] = get_funnel_data(client, paid_type)
        client['llm_data_yoy'] = get_funnel_data(client, llm_type)
        client['overall_data_yoy'] = get_funnel_data(client, overall_type)

        # Timeseries (90-day window, no comparison)
        client['timeseries_data'] = get_funnel_data(client, ts_type)

        # MTD pass: current month 1st → today-2, compared to same days last year
        if mtd_end_date >= mtd_start_date:
            client['start_date'] = mtd_start_date
            client['end_date'] = mtd_end_date
            client['compare_start_date'] = compare_start_mtd
            client['compare_end_date'] = compare_end_mtd
            client['paid_data_mtd'] = get_funnel_data(client, paid_type)
            client['llm_data_mtd'] = get_funnel_data(client, llm_type)
            client['overall_data_mtd'] = get_funnel_data(client, overall_type)
            client['mtd_start_date_string'] = mtd_start_date.strftime("%d/%m/%Y")
            client['mtd_end_date_string'] = mtd_end_date.strftime("%d/%m/%Y")
            client['compare_start_mtd'] = compare_start_mtd
            client['compare_end_mtd'] = compare_end_mtd
            # Restore main period dates
            client['start_date'] = start_date
            client['end_date'] = end_date

        # Alias MoM as the primary paid_data so existing helpers (add_kpi_boxes, get_run_rate) work
        client['paid_data'] = client['paid_data_mom']
        client['run_rate'] = get_run_rate(client)

        # Initialise empty dimension data — populated per-slide via fetch_trend_data MCP tool
        client['dimension_data'] = {}

    except Exception as e:
        log_error(f"{client['name']} monthly_reports/main: data fetch failed: {e}")
        raise

    data_path = f"storage/{client_name}_monthly_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(client, f, ensure_ascii=False, indent=2, cls=TimestampEncoder)
    print(f"Monthly data written to {data_path}")

    if data_only:
        return data_path

    from monthly_reports.generate_ppt import generate_ppt
    month_str = start_date.strftime("%Y_%m")
    output_path = f"slides/{client_name}_monthly_{month_str}.pptx"
    output_path, presentation_path, _ = generate_ppt(client_name, output_path)
    print(f"Monthly report saved to {output_path}")
    print(f"Presentation copy saved to {presentation_path}")
    return output_path


def run_custom_overview_fetch(client_name, start_date_str, end_date_str):
    """Fetch overview data for a Custom Date Window and append it to the cached monthly JSON.

    Runs both comparison passes for the window — same-length prior period (MoM-equivalent)
    and YoY — and stores results nested under paid_data_custom_{start}_{end} with mom/yoy
    sub-keys (matching the existing paid_data_mom/paid_data_yoy pattern but nested).
    Also persists resolved date strings so the PPTX generator can build date labels.
    """
    data_path = f"storage/{client_name}_monthly_data.json"
    with open(data_path, "r", encoding="utf-8") as f:
        client = json.load(f)

    with open("storage/config.json", "r") as f:
        clients = json.load(f)
    config = next((c for c in clients if c["name"] == client_name), None)
    if config is None:
        raise ValueError(f"Client '{client_name}' not found in config")
    for k, v in config.items():
        if k not in client:
            client[k] = v

    current_start = pd.Timestamp(start_date_str).normalize()
    current_end   = pd.Timestamp(end_date_str).normalize()
    num_days      = (current_end - current_start).days + 1
    prev_end      = (current_start - pd.DateOffset(days=1)).normalize()
    prev_start    = (prev_end - pd.DateOffset(days=num_days - 1)).normalize()
    yoy_start     = (current_start - pd.DateOffset(years=1)).normalize()
    yoy_end       = (current_end   - pd.DateOffset(years=1)).normalize()

    account_type = client.get("account_type", "Ecommerce")
    paid_type    = "paid_lead_gen"  if account_type == "Lead Gen" else "paid_ecommerce"
    llm_type     = "llm_lead_gen"  if account_type == "Lead Gen" else "llm_ecommerce"
    overall_type = "overall_lead_gen" if account_type == "Lead Gen" else "overall_ecommerce"

    client["start_date"] = current_start
    client["end_date"]   = current_end

    # MoM-equivalent pass (same-length prior period)
    client["compare_start_date"] = prev_start
    client["compare_end_date"]   = prev_end
    mom_paid    = get_funnel_data(client, paid_type)
    mom_llm     = get_funnel_data(client, llm_type)
    mom_overall = get_funnel_data(client, overall_type)

    # YoY pass
    client["compare_start_date"] = yoy_start
    client["compare_end_date"]   = yoy_end
    yoy_paid    = get_funnel_data(client, paid_type)
    yoy_llm     = get_funnel_data(client, llm_type)
    yoy_overall = get_funnel_data(client, overall_type)

    window_prefix = f"custom_{start_date_str}_{end_date_str}"
    client[f"paid_data_{window_prefix}"]    = {"mom": mom_paid,    "yoy": yoy_paid}
    client[f"llm_data_{window_prefix}"]     = {"mom": mom_llm,     "yoy": yoy_llm}
    client[f"overall_data_{window_prefix}"] = {"mom": mom_overall, "yoy": yoy_overall}

    fmt = "%d/%m/%Y"
    client[f"{window_prefix}_start_date_string"]         = current_start.strftime(fmt)
    client[f"{window_prefix}_end_date_string"]           = current_end.strftime(fmt)
    client[f"{window_prefix}_compare_start_mom_string"]  = prev_start.strftime(fmt)
    client[f"{window_prefix}_compare_end_mom_string"]    = prev_end.strftime(fmt)
    client[f"{window_prefix}_compare_start_yoy_string"]  = yoy_start.strftime(fmt)
    client[f"{window_prefix}_compare_end_yoy_string"]    = yoy_end.strftime(fmt)

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(client, f, ensure_ascii=False, indent=2, cls=TimestampEncoder)
    print(f"Custom overview data written to {data_path}")
    return data_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="Client name as it appears in config.json")
    parser.add_argument("--data-only", action="store_true", help="Fetch and save data only, skip PPT generation")
    parser.add_argument("--start-date", default=None, help="Custom Date Window start (YYYY-MM-DD). Requires --end-date.")
    parser.add_argument("--end-date",   default=None, help="Custom Date Window end (YYYY-MM-DD). Requires --start-date.")
    args = parser.parse_args()
    if args.start_date or args.end_date:
        if not (args.start_date and args.end_date):
            parser.error("--start-date and --end-date must be provided together")
        run_custom_overview_fetch(args.client, args.start_date, args.end_date)
    else:
        run_monthly_report(args.client, data_only=args.data_only)
