import pandas as pd
from pandas.tseries.offsets import MonthEnd
import locale

def get_run_rate(client):
    current_spend = float(client['paid_data']['Total']['Cost']['curr'].replace("£", "").replace(",", ""))
    # Dummy spend value — replace with real variable when ready
    start_date = client['start_date']
    end_date = client['end_date']

    # Check if the period is a full month — if so, no run rate needed
    is_full_month = (
        start_date.day == 1 and
        end_date == (start_date + MonthEnd(0)).normalize()
    )

    if is_full_month:
        return '-'

    # Days elapsed (inclusive of start date, so +1)
    days_elapsed = (end_date - start_date).days

    # Total days in the month the period starts in
    total_days_in_month = (start_date + MonthEnd(0)).day

    if days_elapsed <= 0:
        return '-'

    avg_daily_spend = current_spend / days_elapsed
    run_rate = avg_daily_spend * total_days_in_month

    return f"£{float(run_rate):,.2f}"
