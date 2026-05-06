import pandas as pd
from pandas.tseries.offsets import MonthEnd


# Config Client object dates
def config_dates(client):
    now = pd.Timestamp.now()
    yday = (now - pd.DateOffset(days=2)).normalize()
    first_of_current_month = now.replace(day=1).normalize()

    # Create masks for date periods
    if client['comparison_dates'] == 'MTD Yearly Comparison':

        # Default = this month MTD
        start_date = first_of_current_month
        end_date = yday

        # If within first 5 days, switch to last full month
        if now.day <= 7:
            start_date = (first_of_current_month - pd.DateOffset(months=1)).normalize()
            end_date = start_date + MonthEnd(0)

        # Calculate day offset from start
        day_diff = (end_date - start_date).days

        compare_start = (start_date - pd.DateOffset(years=1)).normalize()
        compare_end = compare_start + pd.DateOffset(days=day_diff)

        client['start_date'] = start_date
        client['end_date'] = end_date
        client['compare_start_date'] = compare_start
        client['compare_end_date'] = compare_end
    
    if client['comparison_dates'] == 'MTD Monthly Comparison':

        # Default = this month MTD
        start_date = first_of_current_month
        end_date = yday

        # If within first 5 days, switch to last full month
        if now.day <= 7:
            start_date = (first_of_current_month - pd.DateOffset(months=1)).normalize()
            end_date = start_date + MonthEnd(0)

            # Compare to full month before that
            compare_start = (start_date - pd.DateOffset(months=1)).normalize()
            compare_end = compare_start + MonthEnd(0)

        else:
            day_diff = (end_date - start_date).days

            # Compare to full previous month
            compare_start = (first_of_current_month - pd.DateOffset(months=1)).normalize()
            compare_end = compare_start + pd.DateOffset(days=day_diff)

        client['start_date'] = start_date
        client['end_date'] = end_date
        client['compare_start_date'] = compare_start
        client['compare_end_date'] = compare_end
    
    client['start_date_string'] = client['start_date'].normalize().strftime("%d/%m/%Y")
    client['end_date_string'] = client['end_date'].normalize().strftime("%d/%m/%Y")
    client['compare_start_date_string'] = client['compare_start_date'].normalize().strftime("%d/%m/%Y")
    client['compare_end_date_string'] = client['compare_end_date'].normalize().strftime("%d/%m/%Y")
    return(client)