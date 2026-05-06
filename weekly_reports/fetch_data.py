import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
import pandas as pd
from core.error_logger import log_error
from core.config_dates import config_dates
from core.get_funnel_data import get_funnel_data
from core.get_run_rate import get_run_rate


class TimestampEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


def fetch_client_data(client_name):
    with open("storage/config.json", "r") as f:
        clients = json.load(f)

    client = next((c for c in clients if c['name'] == client_name), None)
    if client is None:
        raise ValueError(f"Client '{client_name}' not found in config")

    client = config_dates(client)

    try:
        if client["plan"] != "":
            with open("storage/plans.json", "r") as f:
                plans = json.load(f)
            client["plan_json"] = plans[client["name"]]
    except Exception as e:
        log_error(f"{client['name']} fetch_data: misconfigured 90 Day Plan: {e}")
        raise

    try:
        account_type = client['account_type']
        paid_type    = 'paid_lead_gen'        if account_type == 'Lead Gen' else 'paid_ecommerce'
        llm_type     = 'llm_lead_gen'         if account_type == 'Lead Gen' else 'llm_ecommerce'
        overall_type = 'overall_lead_gen'     if account_type == 'Lead Gen' else 'overall_ecommerce'
        ts_type      = 'time_series_lead_gen' if account_type == 'Lead Gen' else 'time_series_ecommerce'

        # Primary comparison dates already set by config_dates
        primary_compare_start = client['compare_start_date']
        primary_compare_end   = client['compare_end_date']

        primary_paid    = get_funnel_data(client, paid_type)
        primary_llm     = get_funnel_data(client, llm_type)
        primary_overall = get_funnel_data(client, overall_type)

        # Secondary comparison: opposite window to primary
        if client['comparison_dates'] == 'MTD Monthly Comparison':
            sec_start = (client['start_date'] - pd.DateOffset(years=1)).normalize()
            sec_end   = (client['end_date']   - pd.DateOffset(years=1)).normalize()
        else:  # MTD Yearly Comparison
            sec_start = (client['start_date'] - pd.DateOffset(months=1)).normalize()
            sec_end   = (client['end_date']   - pd.DateOffset(months=1)).normalize()

        client['compare_start_date'] = sec_start
        client['compare_end_date']   = sec_end
        sec_paid    = get_funnel_data(client, paid_type)
        sec_llm     = get_funnel_data(client, llm_type)
        sec_overall = get_funnel_data(client, overall_type)

        # Restore primary compare dates
        client['compare_start_date'] = primary_compare_start
        client['compare_end_date']   = primary_compare_end

        # Timeseries (90-day, no comparison window needed)
        timeseries = get_funnel_data(client, ts_type)

        # Assign sections
        if client['comparison_dates'] == 'MTD Monthly Comparison':
            client['mom'] = {'paid_data': primary_paid, 'llm_data': primary_llm, 'overall_data': primary_overall}
            client['yoy'] = {'paid_data': sec_paid,     'llm_data': sec_llm,     'overall_data': sec_overall}
        else:
            client['yoy'] = {'paid_data': primary_paid, 'llm_data': primary_llm, 'overall_data': primary_overall}
            client['mom'] = {'paid_data': sec_paid,     'llm_data': sec_llm,     'overall_data': sec_overall}

        client['timeseries'] = timeseries

        # Keep paid_data alias pointing to primary for the email template
        client['paid_data'] = primary_paid

        client['run_rate'] = get_run_rate(client)

    except Exception as e:
        log_error(f"{client['name']} fetch_data: misconfigured Paid Data: {e}")
        raise

    output_path = f"storage/{client_name}_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(client, f, ensure_ascii=False, indent=2, cls=TimestampEncoder)

    print(f"Data written to {output_path}")
    return client


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="Client name as it appears in config.json")
    args = parser.parse_args()
    fetch_client_data(args.client)
