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

    # In the first 5 days of the month the current MTD window has almost no data.
    # Shift the reference month back by one so both the "previous month" period and
    # MTD land on the month that just completed.
    if now.day <= 5:
        first_of_current_month = (first_of_current_month - pd.DateOffset(months=1)).normalize()
        mtd_end_date = (first_of_current_month + MonthEnd(0)).normalize()
    else:
        mtd_end_date = (now - pd.DateOffset(days=2)).normalize()

    start_date = (first_of_current_month - pd.DateOffset(months=1)).normalize()
    end_date = (start_date + MonthEnd(0)).normalize()

    compare_start_mom = (start_date - pd.DateOffset(months=1)).normalize()
    compare_end_mom = (compare_start_mom + MonthEnd(0)).normalize()

    compare_start_yoy = (start_date - pd.DateOffset(years=1)).normalize()
    compare_end_yoy = (compare_start_yoy + MonthEnd(0)).normalize()

    mtd_start_date = first_of_current_month
    compare_start_mtd = (first_of_current_month - pd.DateOffset(years=1)).normalize()
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="Client name as it appears in config.json")
    parser.add_argument("--data-only", action="store_true", help="Fetch and save data only, skip PPT generation")
    args = parser.parse_args()
    run_monthly_report(args.client, data_only=args.data_only)
