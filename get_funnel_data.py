import pandas as pd
import numpy as np
import json
import locale
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from safe_div import safe_div
from pandas.tseries.offsets import MonthEnd
from generate_df import *


# Main workflow
def get_funnel_data(client, table_type):
    df = initialise_df(client)
    date_range = set_date_range(client, table_type)
    breakdown_dimension = set_breakdown_dimensions(client,table_type)
    df = apply_filters(df, client, breakdown_dimension, date_range)
    # Basic Compare
    if table_type in ["paid_lead_gen", "paid_ecommerce","overall_lead_gen", "overall_ecommerce"]:
        final_data = get_comparison_data(df, breakdown_dimension, table_type)

    # llm_data
    elif table_type in ["llm_lead_gen", "llm_ecommerce"]:
        final_data = get_llm_data(client, breakdown_dimension, df, table_type)

    # 90 Day review
    elif table_type in ["time_series_lead_gen", "time_series_ecommerce"]:
        final_data = get_llm_data(client, breakdown_dimension, df, table_type)

    return(final_data)

# Set the date range that the dataset will be filtered by
def set_date_range(client, table_type):
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        date_range = {
            "start_date": client['start_date'],
            "end_date": client['end_date'],
            "compare_start_date": client['compare_start_date'],
            "compare_end_date": client['compare_end_date']
        }
    else:
        date_range = {
            "start_date": (client['end_date'] - pd.DateOffset(days=90)).normalize(),
            "end_date": client['end_date'],
            "compare_start_date": '',
            "compare_end_date": ''
        }
    return(date_range)


# Set the dimensions that the dataset will be broken down by
def set_breakdown_dimensions(client, table_type):
    if table_type in ["paid_lead_gen", "paid_ecommerce"]:
        breakdown_dimension = [client['dimension'], 'Period']
    elif table_type in ["overall_lead_gen", "overall_ecommerce"]:
        breakdown_dimension = ['Channel', 'Period']
    elif table_type in ["llm_lead_gen", "llm_ecommerce"]:
        breakdown_dimension = ['Ad Platform', 'Period']
    else:
        breakdown_dimension = ['Week number (ISO)', client['dimension']]
    return breakdown_dimension

# Generate a json object that has all the data for the 
def get_llm_data(client, breakdown_dimension, df, table_type):
    # Create a list of all the ad channels in the client dataset
    ad_channels = df['Ad Channel'].dropna().unique().tolist()
    final_data = {}

    # Loop through all the channels and create a json entry broken down by breakdown
    for channel in ad_channels:
        # Skip over any channels that are not within logic
        if channel not in ['Combined', 'Dispaly','Shopping', 'Paid Search', 'Paid Social', 'Paid Social Static', 'Paid Social Video', 'Video']:
            continue

        # Create df and filter down to the current channel
        df_llm = df.copy()
        mask = (df['Ad Channel'] == channel)
        df_llm = df_llm.loc[mask]

        # Create a list of all the headers in the df
        headers = list(df_llm.columns.values)

        # Find the relevant function for the current ad channel
        if channel == 'Paid Search':
            if client['account_type'] == 'Lead Gen':
                df_llm = paid_search_lead_gen(df_llm, breakdown_dimension,  headers, table_type)
            else:
                df_llm = paid_search_ecommerce(df_llm, breakdown_dimension,  headers, table_type)
        if channel in ('Shopping', 'Combined', 'Performance Max'):
            if client['account_type'] == 'Lead Gen':
                df_llm = paid_shopping_lead_gen(df_llm, breakdown_dimension,  headers, table_type)
            else:
                df_llm = paid_shopping_ecommerce(df_llm, breakdown_dimension,  headers, table_type)
        if channel == 'Display':
            if client['account_type'] == 'Lead Gen':
                df_llm = paid_display_lead_gen(df_llm, breakdown_dimension,  headers, table_type)
            else:
                df_llm = paid_display_ecommerce(df_llm, breakdown_dimension,  headers, table_type)
        if channel == 'Video':
            if client['account_type'] == 'Lead Gen':
                df_llm = paid_video_lead_gen(df_llm, breakdown_dimension,  headers, table_type)
            else:
                df_llm = paid_video_ecommerce(df_llm, breakdown_dimension,  headers, table_type)
        if channel == 'Paid Social Video':
            if client['account_type'] == 'Lead Gen':
                df_llm = paid_social_video_lead_gen(df_llm, breakdown_dimension,  headers, table_type)
            else:
                df_llm = paid_social_video_ecommerce(df_llm, breakdown_dimension,  headers, table_type)
        if channel in ('Paid Social Static', 'Paid Social'):
            if client['account_type'] == 'Lead Gen':
                df_llm = paid_social_static_lead_gen(df_llm, breakdown_dimension,  headers, table_type)
            else:
                df_llm = paid_social_static_ecommerce(df_llm, breakdown_dimension,  headers, table_type)

        # Collate all the relevant metrics and create a pivot table that can be turned into json          
        metrics = [col for col in df_llm.columns if col not in breakdown_dimension]

        if table_type in ["llm_lead_gen", "llm_ecommerce"]:
            df_llm = pivot_df(df_llm, breakdown_dimension, metrics, table_type)

        # Append the json entry to the final dict
        final_data[channel] = df_to_json(df_llm, breakdown_dimension, metrics, table_type)
    
    # Return the completed list
    return(final_data)
  

# Create the json for the datasets that are just looking to compare one period against another with one breakdown
def get_comparison_data(df, breakdown_dimension, table_type):
    if table_type == 'paid_ecommerce':
        df = paid_ecommerce(df, breakdown_dimension, table_type)

    if table_type == 'paid_lead_gen':
        df = paid_lead_gen(df, breakdown_dimension, table_type)

    if table_type == 'overall_ecommerce':
        df = overall_ecommerce(df, breakdown_dimension, table_type)

    if table_type == 'overall_lead_gen':
        df = overall_lead_gen(df, breakdown_dimension, table_type)

    metrics = [col for col in df.columns if col not in breakdown_dimension]
    df = pivot_df(df, breakdown_dimension, metrics, table_type)
    final_data = df_to_json(df, breakdown_dimension, metrics, table_type)
    return(final_data)

# Initialise the dataframe
def initialise_df(client):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('storage/creds.json', scope)
    sa = gspread.authorize(creds)
    # Initial Config -- Declare Global Variables and initialise datasets (filename=serene-lotus-379510-b3f9b3b23758)
    sh = sa.open('Weekly Reports')
    locale.setlocale(locale.LC_ALL, 'en_GB.UTF-8')
    client['report_type'] = 'normal'
    ws = sh.worksheet(f"{client['name']} Funnel Import")
    df = pd.DataFrame(ws.get_all_records())
    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
    return df

# Mask the dataframes so that they are within the correct date range
def apply_filters(df, client, breakdown_dimension, date_range):
    # Apply Date Mask
    has_dimension = df[breakdown_dimension[0]] != ''

    primary_range = (
        (df['Date'] >= date_range['start_date']) &
        (df['Date'] <= date_range['end_date'])
    )

    compare_range = (
        date_range.get('compare_start_date') is not None and
        date_range.get('compare_end_date') is not None
    )

    if compare_range:
        in_compare_range = (
            (df['Date'] >= date_range['compare_start_date']) &
            (df['Date'] <= date_range['compare_end_date'])
        )
        mask = has_dimension & (primary_range | in_compare_range)
    else:
        mask = has_dimension & primary_range
    df = df.loc[mask]

    # Categorise Date Periods //TO DO: Need to make sure this isn't pulling into the time series data
    df.loc[df['Date'] >= client['start_date'], 'Period'] = 'Current'
    df.loc[df['Date'] < client['start_date'], 'Period'] = 'Previous'
    
    return (df)

# Create a pivoted version of the data
def pivot_df(df_grouped, breakdown_dimension, metrics, table_type):
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        df_pivot = (
            df_grouped.pivot(index=breakdown_dimension[0], columns=breakdown_dimension[1], values=metrics)
            .reindex(columns=pd.MultiIndex.from_product([metrics, ["Current", "Previous"]]))  # ensures both exist
        )
        
        df_pivot.columns = [f"{metric}__{period.lower()}" for metric, period in df_pivot.columns]
        df_pivot = df_pivot.reset_index()
        
        for metric in metrics:
            df_pivot[f"{metric}__delta"] = df_pivot[f"{metric}__current"] - df_pivot[f"{metric}__previous"] 
            df_pivot[f"{metric}__pct"] = np.where(
                df_pivot[f"{metric}__previous"].fillna(0).eq(0),
                np.nan,
                df_pivot[f"{metric}__delta"] / df_pivot[f"{metric}__previous"]
            )

    else:
        df_pivot = (
            df_grouped.pivot(index=breakdown_dimension[0], columns=breakdown_dimension[0], values=metrics)
        )

    return(df_pivot)

# Convert datafram to json format
def df_to_json(df_pivot, breakdown_dimension, metrics, table_type):    
    int_metrics = ["Impressions", "Clicks", "Transactions", "Conversions", "Sessions", "Holds", "Hooks","Views"]
    pct_metrics = ["CTR", "Conversion Rate", "ROAS", "Impression Share", "Abs. Top Impression Share", "View Rate", "Hook Rate", "Hold Rate"]
    gbp_metrics = ["Cost", "Transaction Revenue", "CPA", "CPC", "AOV"]

    output = {}
    # Create a json for when there is comparison
    if table_type in ["paid_lead_gen", "paid_ecommerce", "overall_lead_gen", "overall_ecommerce", "llm_lead_gen", "llm_ecommerce"]:
        for _, row in df_pivot.iterrows():
            breakdown = row[breakdown_dimension[0]]
            output[breakdown] = {}

            for metric in metrics: 
                if metric in int_metrics:
                    output[breakdown][metric] = {
                        "curr":  fmt_int(row[f"{metric}__current"]),
                        "prev":  fmt_int(row[f"{metric}__previous"]),
                        "delta": fmt_int(row[f"{metric}__delta"]),
                        "pct":   pct_diff(row[f"{metric}__pct"]),
                }
                elif metric in pct_metrics:
                    output[breakdown][metric] = {
                        "curr":  fmt_pct(row[f"{metric}__current"]),
                        "prev":  fmt_pct(row[f"{metric}__previous"]),
                        "delta": fmt_pct(row[f"{metric}__delta"]),
                        "pct":   pct_diff(row[f"{metric}__pct"]),
                }
                elif metric in gbp_metrics:
                    output[breakdown][metric] = {
                        "curr":  fmt_gbp(row[f"{metric}__current"]),
                        "prev":  fmt_gbp(row[f"{metric}__previous"]),
                        "delta": fmt_gbp(row[f"{metric}__delta"]),
                        "pct":   pct_diff(row[f"{metric}__pct"]),
                }
                    
    # Create a json for when there is comparison
    else: 
        for _, row in df_pivot.iterrows():
            breakdown = row[breakdown_dimension[0]]
            output[breakdown] = {}

            for metric in metrics: 
                if metric in int_metrics:
                    output[breakdown][metric] = {
                        "curr":  fmt_int(row[metric]),
                }
                elif metric in pct_metrics:
                    output[breakdown][metric] = {
                        "curr":  fmt_pct(row[metric]),
                }
                elif metric in gbp_metrics:
                    output[breakdown][metric] = {
                        "curr":  fmt_gbp(row[metric]),
                }

    return output

# Ensure no numpy types are returned
def to_py(v):
    if pd.isna(v):
        return None
    if isinstance(v, np.generic):
        return v.item()
    return v

# Convert df values to ints that are human readable
def fmt_int(v):
    v = to_py(v)
    if v is None:
        return "0"
    return f"{int(round(v)):,}"

# Convert df values to percentages that are human readable
def fmt_pct(v):
    v = to_py(v)
    if v is None:
        return "0.00%"
    return f"{float(v):.2f}%"

# Convert df values to percentages that include +/-
def pct_diff(v):
    v = to_py(v)
    if v is None:
        return "-"
    v = v*100
    if v > 0:
        return f"+{float(v):.2f}%"
    elif v <= 0:
        return f"{float(v):.2f}%"

# Convert df values to monetary values that are human readable
def fmt_gbp(v):
    v = to_py(v)
    if v is None:
        return "£0.00"  # e.g. "" or "—"
    return f"£{float(v):,.2f}"