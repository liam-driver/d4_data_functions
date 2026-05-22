import os
import json
import pandas as pd
from core.get_funnel_data import initialise_df, apply_filters, pivot_df, df_to_json, fmt_int, fmt_pct, fmt_gbp
from core.safe_div import safe_div

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _build_data_key(dimension, filters):
    if not filters:
        return dimension
    parts = [f"{col}={val}" for col, val in sorted(filters.items())]
    return "::".join([dimension] + parts)


def _apply_scope_filters(df, filters):
    if not filters:
        return df
    for col, val in filters.items():
        if col not in df.columns:
            continue
        if isinstance(val, list):
            df = df[df[col].isin(val)]
        else:
            df = df[df[col] == val]
    return df


_ADDITIVE_METRIC_CANDIDATES = [
    ('Cost',               ['Cost (GBP)', 'Cost']),
    ('Transaction Revenue', ['Transaction Revenue (GBP)', 'Transaction Revenue']),
    ('Conversions',        ['Conversions']),
    ('Impressions',        ['Impressions']),
    ('Clicks',             ['Clicks']),
    ('Transactions',       ['Transactions']),
]


def _find_column(columns_set, candidates):
    for name in candidates:
        if name in columns_set:
            return name
    return None


def _compute_derived_metrics(df_work):
    if 'Cost' in df_work.columns and 'Transaction Revenue' in df_work.columns:
        df_work['ROAS'] = safe_div(df_work['Transaction Revenue'], df_work['Cost'], multiplier=100)
    if 'Cost' in df_work.columns and 'Conversions' in df_work.columns:
        df_work['CPA'] = safe_div(df_work['Cost'], df_work['Conversions'], multiplier=1)
    if 'Impressions' in df_work.columns and 'Clicks' in df_work.columns:
        df_work['CTR'] = safe_div(df_work['Clicks'], df_work['Impressions'], multiplier=100)
    if 'Clicks' in df_work.columns and 'Cost' in df_work.columns:
        df_work['CPC'] = safe_div(df_work['Cost'], df_work['Clicks'], multiplier=1)
    conv_col = (
        'Transactions' if 'Transactions' in df_work.columns
        else ('Conversions' if 'Conversions' in df_work.columns else None)
    )
    if 'Clicks' in df_work.columns and conv_col:
        df_work['Conversion Rate'] = safe_div(df_work[conv_col], df_work['Clicks'], multiplier=100)
    if 'Transactions' in df_work.columns and 'Transaction Revenue' in df_work.columns:
        df_work['AOV'] = safe_div(df_work['Transaction Revenue'], df_work['Transactions'], multiplier=1)
    return df_work


def get_dimension_cut(client, dimension_column, filters=None):
    """MoM comparison data sliced by dimension_column. Uses client compare_start/end_date."""
    from weekly_reports.generate_df import get_total_row

    df = initialise_df(client)

    if dimension_column not in df.columns:
        raise ValueError(
            f"Column '{dimension_column}' not found in sheet. "
            f"Available columns: {df.columns.tolist()}"
        )

    account_type = client.get('account_type', 'Ecommerce')
    table_type = 'paid_lead_gen' if account_type == 'Lead Gen' else 'paid_ecommerce'

    breakdown_dimension = [dimension_column, 'Period']
    date_range = {
        'start_date':         client['start_date'],
        'end_date':           client['end_date'],
        'compare_start_date': client['compare_start_date'],
        'compare_end_date':   client['compare_end_date'],
    }

    df = apply_filters(df, client, breakdown_dimension, date_range)
    df = _apply_scope_filters(df, filters)

    columns_set = set(df.columns.tolist())
    selected = {}
    for canonical, candidates in _ADDITIVE_METRIC_CANDIDATES:
        col = _find_column(columns_set, candidates)
        if col is not None:
            selected[canonical] = col

    if not selected:
        raise ValueError(f"No recognised metric columns found for dimension cut on '{dimension_column}'.")

    work_cols = [breakdown_dimension[1], breakdown_dimension[0]] + list(selected.values())
    df_work = df[work_cols].copy()
    df_work[list(selected.values())] = df_work[list(selected.values())].apply(pd.to_numeric, errors='coerce')
    df_work = df_work.groupby([breakdown_dimension[1], breakdown_dimension[0]], as_index=False).sum()

    rename_map = {v: k for k, v in selected.items()}
    df_work = df_work.rename(columns=rename_map)

    curr_df = get_total_row(df_work[df_work['Period'].eq('Current')].copy(), 'Current')
    prev_df = get_total_row(df_work[df_work['Period'].eq('Previous')].copy(), 'Previous')
    df_work = pd.concat([curr_df, prev_df], ignore_index=True)

    df_work = _compute_derived_metrics(df_work)

    metrics = [col for col in df_work.columns if col not in breakdown_dimension]
    df_pivot = pivot_df(df_work, breakdown_dimension, metrics, table_type)
    return df_to_json(df_pivot, breakdown_dimension, metrics, table_type)


def get_dimension_timeseries(client, dimension_column, filters=None, time_dimension='Week number (ISO)', start_date_override=None):
    """Timeseries data sliced by dimension_column, grouped by time_dimension.

    time_dimension: 'Week number (ISO)' | 'Month' | 'Year' | 'Date'
    start_date_override: ISO date string to extend the lookback beyond the default 90 days.
    Returns {dim_val: {time_key: {metric: {curr}}}}."""
    df = initialise_df(client)

    if dimension_column not in df.columns:
        raise ValueError(f"Column '{dimension_column}' not found in sheet.")

    end_date = client['end_date']
    if start_date_override:
        start_date = pd.Timestamp(start_date_override).normalize()
    else:
        start_date = (end_date - pd.DateOffset(days=90)).normalize()

    mask = (
        (df['Date'] >= start_date) &
        (df['Date'] <= end_date) &
        (df[dimension_column].notna()) &
        (df[dimension_column] != '')
    )
    df = df.loc[mask].copy()
    df = _apply_scope_filters(df, filters)

    if df.empty:
        return {}

    if time_dimension == 'Week number (ISO)':
        if 'Week number (ISO)' not in df.columns:
            df['Week number (ISO)'] = df['Date'].dt.isocalendar().week.astype(int)
    elif time_dimension == 'Month':
        df['Month'] = df['Date'].dt.to_period('M').astype(str)
    elif time_dimension == 'Year':
        df['Year'] = df['Date'].dt.year.astype(int)
    # 'Date' column is already present

    if time_dimension not in df.columns:
        raise ValueError(f"Time dimension '{time_dimension}' is not available in the data.")

    columns_set = set(df.columns.tolist())
    selected = {}
    for canonical, candidates in _ADDITIVE_METRIC_CANDIDATES:
        col = _find_column(columns_set, candidates)
        if col is not None:
            selected[canonical] = col

    if not selected:
        return {}

    work_cols = [dimension_column, time_dimension] + list(selected.values())
    df_work = df[work_cols].copy()
    df_work[list(selected.values())] = df_work[list(selected.values())].apply(pd.to_numeric, errors='coerce')
    df_work = df_work.groupby([dimension_column, time_dimension], as_index=False).sum()

    rename_map = {v: k for k, v in selected.items()}
    df_work = df_work.rename(columns=rename_map)
    df_work = _compute_derived_metrics(df_work)

    int_metrics = ['Impressions', 'Clicks', 'Transactions', 'Conversions', 'Sessions']
    pct_metrics = ['CTR', 'Conversion Rate', 'ROAS', 'Impression Share', 'Abs. Top Impression Share']
    gbp_metrics = ['Cost', 'Transaction Revenue', 'CPA', 'CPC', 'AOV']
    metrics = [col for col in df_work.columns if col not in [dimension_column, time_dimension]]

    result = {}
    for _, row in df_work.iterrows():
        dim_val = str(row[dimension_column])
        time_key = str(int(row[time_dimension])) if time_dimension in ('Week number (ISO)', 'Year') else str(row[time_dimension])
        if dim_val not in result:
            result[dim_val] = {}
        time_data = {}
        for metric in metrics:
            val = row[metric]
            if metric in int_metrics:
                time_data[metric] = {'curr': fmt_int(val)}
            elif metric in pct_metrics:
                time_data[metric] = {'curr': fmt_pct(val)}
            elif metric in gbp_metrics:
                time_data[metric] = {'curr': fmt_gbp(val)}
        result[dim_val][time_key] = time_data

    return result


def fetch_trend_data(client_name, channel, dimension, channel_filter=None, platform=None, platform_filter=None, time_dimension='Week number (ISO)', start_date_override=None):
    """
    Fetches MoM, YoY, and timeseries data for a Trend Topic scoped by channel/platform,
    broken down by dimension. Persists to dimension_data[data_key] in the cached monthly JSON.

    time_dimension: column to group the timeseries by ('Week number (ISO)', 'Month', 'Year', 'Date').
    start_date_override: ISO date string to extend the timeseries lookback (e.g. start of year for YTD).
    Returns the full envelope dict.
    """
    data_path = os.path.join(PROJECT_ROOT, 'storage', f'{client_name}_monthly_data.json')
    with open(data_path, 'r', encoding='utf-8') as f:
        client = json.load(f)

    for key in ('start_date', 'end_date', 'compare_start_mom', 'compare_end_mom',
                'compare_start_yoy', 'compare_end_yoy'):
        if key in client and isinstance(client[key], str):
            client[key] = pd.Timestamp(client[key])

    # Build scope filters from channel / platform params
    filters = {}
    if channel_filter and channel_filter.get('type') == 'include':
        filters['Ad Channel'] = channel_filter['channels']
    elif channel:
        filters['Ad Channel'] = channel

    if platform_filter and platform_filter.get('type') == 'include':
        filters['Ad Platform'] = platform_filter['platforms']
    elif platform:
        filters['Ad Platform'] = platform

    filters = filters or None

    client['compare_start_date'] = client['compare_start_mom']
    client['compare_end_date'] = client['compare_end_mom']
    data_mom = get_dimension_cut(client, dimension, filters)

    client['compare_start_date'] = client['compare_start_yoy']
    client['compare_end_date'] = client['compare_end_yoy']
    data_yoy = get_dimension_cut(client, dimension, filters)

    data_timeseries = get_dimension_timeseries(client, dimension, filters, time_dimension, start_date_override)

    data_key = _build_data_key(dimension, filters)

    if not isinstance(client.get('dimension_data'), dict):
        client['dimension_data'] = {}
    client['dimension_data'][data_key] = {
        'time_dimension': time_dimension,
        'mom':            data_mom,
        'yoy':            data_yoy,
        'timeseries':     data_timeseries,
    }

    from monthly_reports.main import TimestampEncoder
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(client, f, ensure_ascii=False, indent=2, cls=TimestampEncoder)

    return {
        'channel':        channel,
        'platform':       platform,
        'dimension':      dimension,
        'data_key':       data_key,
        'time_dimension': time_dimension,
        'mom':            data_mom,
        'yoy':            data_yoy,
        'timeseries':     data_timeseries,
    }
