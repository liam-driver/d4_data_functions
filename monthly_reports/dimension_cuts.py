import os
import json
import pandas as pd
from core.get_funnel_data import initialise_df, apply_filters, pivot_df, df_to_json, fmt_int, fmt_pct, fmt_gbp
from core.safe_div import safe_div

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_VALID_DATE_RANGES = ('previous_7_days', 'mtd', 'previous_month', 'ytd', 'last_90_days')

_DATE_RANGE_LABELS = {
    'previous_7_days': 'Previous 7 Days',
    'mtd':             'Month-to-Date',
    'previous_month':  'Previous Month',
    'ytd':             'Year-to-Date',
    'last_90_days':    'Last 90 Days',
}

_DEFAULT_TIME_DIMENSION = {
    'previous_7_days': 'Date',
    'mtd':             'Date',
    'previous_month':  'Week number (ISO)',
    'ytd':             'Month',
    'last_90_days':    'Week number (ISO)',
}


def _resolve_date_windows(date_range: str) -> dict:
    """Compute current, previous-period, and previous-year windows for a date_range label.
    All windows apply the 2-day GA4 lag (effective_today = today - 2)."""
    if date_range not in _VALID_DATE_RANGES:
        raise ValueError(
            f"Unknown date_range '{date_range}'. Must be one of: {', '.join(_VALID_DATE_RANGES)}"
        )
    today = pd.Timestamp.now().normalize()
    effective_today = (today - pd.DateOffset(days=2)).normalize()

    if date_range == 'previous_7_days':
        current_start = (effective_today - pd.DateOffset(days=6)).normalize()
        current_end   = effective_today
        prev_start    = (current_start - pd.DateOffset(days=7)).normalize()
        prev_end      = (current_start - pd.DateOffset(days=1)).normalize()
        yoy_start     = (current_start - pd.DateOffset(years=1)).normalize()
        yoy_end       = (current_end   - pd.DateOffset(years=1)).normalize()

    elif date_range == 'mtd':
        current_start = effective_today.replace(day=1)
        current_end   = effective_today
        prev_start    = (current_start - pd.DateOffset(months=1)).normalize()
        prev_end      = prev_start + pd.DateOffset(days=(current_end - current_start).days)
        yoy_start     = (current_start - pd.DateOffset(years=1)).normalize()
        yoy_end       = (current_end   - pd.DateOffset(years=1)).normalize()

    elif date_range == 'previous_month':
        first_of_this_month = today.replace(day=1)
        current_start = (first_of_this_month - pd.DateOffset(months=1)).normalize()
        current_end   = (first_of_this_month - pd.DateOffset(days=1)).normalize()
        prev_start    = (current_start - pd.DateOffset(months=1)).normalize()
        prev_end      = (current_start - pd.DateOffset(days=1)).normalize()
        yoy_start     = (current_start - pd.DateOffset(years=1)).normalize()
        yoy_end       = (current_end   - pd.DateOffset(years=1)).normalize()

    elif date_range == 'ytd':
        current_start = effective_today.replace(month=1, day=1)
        current_end   = effective_today
        prev_start    = None
        prev_end      = None
        yoy_start     = (current_start - pd.DateOffset(years=1)).normalize()
        yoy_end       = (current_end   - pd.DateOffset(years=1)).normalize()

    elif date_range == 'last_90_days':
        current_start = (effective_today - pd.DateOffset(days=89)).normalize()
        current_end   = effective_today
        prev_start    = (current_start - pd.DateOffset(days=90)).normalize()
        prev_end      = (current_start - pd.DateOffset(days=1)).normalize()
        yoy_start     = (current_start - pd.DateOffset(years=1)).normalize()
        yoy_end       = (current_end   - pd.DateOffset(years=1)).normalize()

    return {
        'current_start':          current_start,
        'current_end':            current_end,
        'prev_start':             prev_start,
        'prev_end':               prev_end,
        'yoy_start':              yoy_start,
        'yoy_end':                yoy_end,
        'default_time_dimension': _DEFAULT_TIME_DIMENSION[date_range],
        'label':                  _DATE_RANGE_LABELS[date_range],
        'prev_period_available':  prev_start is not None,
    }


def _build_data_key(dimension, filters, date_range=None):
    """filters: list of {column, op, value} dicts."""
    parts = []
    if filters:
        for f in sorted(filters, key=lambda x: x.get('column', '')):
            col = f.get('column', '')
            op  = f.get('op', '=')
            val = f.get('value')
            val_str = ','.join(str(v) for v in val) if isinstance(val, list) else str(val)
            parts.append(f"{col}[{op}]={val_str}")
    if date_range:
        parts.append(f"date_range={date_range}")
    if not parts:
        return dimension
    return "::".join([dimension] + parts)


def _apply_scope_filters(df, filters):
    """filters: list of {column, op, value} dicts. Applies pre-aggregation row-level filtering."""
    if not filters:
        return df
    for f in filters:
        col = f.get('column', '')
        op  = f.get('op', '=')
        val = f.get('value')
        if col not in df.columns:
            continue
        if op == '=':
            if isinstance(val, list):
                df = df[df[col].isin(val)]
            else:
                df = df[df[col].astype(str) == str(val)]
        elif op == '!=':
            if isinstance(val, list):
                df = df[~df[col].isin(val)]
            else:
                df = df[df[col].astype(str) != str(val)]
        elif op == 'contains':
            df = df[df[col].astype(str).str.contains(str(val), case=False, na=False)]
        elif op == 'not_contains':
            df = df[~df[col].astype(str).str.contains(str(val), case=False, na=False)]
        else:
            numeric_col = pd.to_numeric(df[col], errors='coerce')
            try:
                fv = float(val)
                if   op == '>':  df = df[numeric_col >  fv]
                elif op == '<':  df = df[numeric_col <  fv]
                elif op == '>=': df = df[numeric_col >= fv]
                elif op == '<=': df = df[numeric_col <= fv]
            except (ValueError, TypeError):
                pass
    return df


def list_dimension_values(client_name, column, filters=None):
    """Return sorted unique values for column in the raw client data, optionally pre-filtered.

    filters: list of {column, op, value} dicts (same schema as fetch_trend_data filters).
    Lets the LLM discover real dimension values before constructing a scope filter.
    """
    data_path = os.path.join(PROJECT_ROOT, 'storage', f'{client_name}_monthly_data.json')
    with open(data_path, 'r', encoding='utf-8') as f:
        client = json.load(f)

    df = initialise_df(client)

    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found in data. "
            f"Available columns: {sorted(df.columns.tolist())}"
        )

    if filters:
        df = _apply_scope_filters(df, filters)

    _NULL = {'', 'nan', 'None', 'NaN', 'null', '(not set)'}
    values = sorted(
        v for v in df[column].dropna().astype(str).unique()
        if v not in _NULL
    )
    return values


_ADDITIVE_METRIC_CANDIDATES = [
    ('Cost',               ['Cost (GBP)', 'Cost']),
    ('Transaction Revenue', ['Transaction Revenue (GBP)', 'Transaction Revenue']),
    ('Conversions',        ['Conversions']),
    ('Impressions',        ['Impressions']),
    ('Clicks',             ['Clicks']),
    ('Transactions',       ['Transactions']),
    ('Views',              ['Views']),
    ('Hooks',              ['Hooks']),
    ('Holds',              ['Holds']),
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
    if 'Views' in df_work.columns and 'Impressions' in df_work.columns:
        df_work['View Rate'] = safe_div(df_work['Views'], df_work['Impressions'], multiplier=100)
    if 'Hooks' in df_work.columns and 'Impressions' in df_work.columns:
        df_work['Hook Rate'] = safe_div(df_work['Hooks'], df_work['Impressions'], multiplier=100)
    if 'Holds' in df_work.columns and 'Impressions' in df_work.columns:
        df_work['Hold Rate'] = safe_div(df_work['Holds'], df_work['Impressions'], multiplier=100)
    if 'Cost' in df_work.columns and 'Views' in df_work.columns:
        df_work['CPV'] = safe_div(df_work['Cost'], df_work['Views'], multiplier=1)
    if 'Cost' in df_work.columns and 'Hooks' in df_work.columns:
        df_work['Cost Per Hook'] = safe_div(df_work['Cost'], df_work['Hooks'], multiplier=1)
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
    for col in ('Ad Channel', 'Ad Platform'):
        if col in df.columns:
            df = df[df[col].notna() & (df[col] != '')]
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


def get_dimension_timeseries(client, dimension_column, filters=None, time_dimension='Week number (ISO)', start_date_override=None, end_date_override=None):
    """Timeseries data sliced by dimension_column, grouped by time_dimension.

    time_dimension: 'Week number (ISO)' | 'Month' | 'Year' | 'Date'
    start_date_override: ISO date string to extend the lookback beyond the default 90 days.
    end_date_override: ISO date string to cap the window (e.g. for fetching a historical period).
    Returns {dim_val: {time_key: {metric: {curr}}}}."""
    df = initialise_df(client)

    if dimension_column not in df.columns:
        raise ValueError(f"Column '{dimension_column}' not found in sheet.")

    end_date = pd.Timestamp(end_date_override).normalize() if end_date_override else client['end_date']
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
    for col in ('Ad Channel', 'Ad Platform'):
        if col in df.columns:
            df = df[df[col].notna() & (df[col] != '')]
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

    int_metrics = ['Impressions', 'Clicks', 'Transactions', 'Conversions', 'Sessions', 'Views', 'Hooks', 'Holds']
    pct_metrics = ['CTR', 'Conversion Rate', 'ROAS', 'Impression Share', 'Abs. Top Impression Share', 'View Rate', 'Hook Rate', 'Hold Rate']
    gbp_metrics = ['Cost', 'Transaction Revenue', 'CPA', 'CPC', 'AOV', 'CPV', 'Cost Per Hook']
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


def fetch_trend_data(client_name, dimension, filters=None, time_dimension=None, date_range='mtd'):
    """
    Fetches Previous Period, Previous Year, and timeseries data for a Trend Topic broken down
    by dimension, with optional pre-aggregation scope filters. Persists to dimension_data[data_key]
    in the cached monthly JSON.

    filters: list of {column, op, value} dicts applied to raw rows before grouping. Any column
             from the raw data is supported. Operators: =, !=, contains, not_contains, >, <, >=, <=.
             Value can be a string, number, or list (for = and !=).
    date_range: one of 'previous_7_days', 'mtd', 'ytd', 'last_90_days' (default 'mtd').
    time_dimension: column to group the timeseries by ('Week number (ISO)', 'Month', 'Year', 'Date').
                    Defaults to the recommended dimension for the selected date_range if omitted.
    Returns the full envelope dict.
    """
    data_path = os.path.join(PROJECT_ROOT, 'storage', f'{client_name}_monthly_data.json')
    with open(data_path, 'r', encoding='utf-8') as f:
        client = json.load(f)

    windows = _resolve_date_windows(date_range)
    effective_time_dimension = time_dimension or windows['default_time_dimension']

    # Override client date window with the resolved range
    client['start_date'] = windows['current_start']
    client['end_date']   = windows['current_end']

    # Previous Period (omitted for YTD)
    if windows['prev_period_available']:
        client['compare_start_date'] = windows['prev_start']
        client['compare_end_date']   = windows['prev_end']
        data_previous_period = get_dimension_cut(client, dimension, filters)
    else:
        data_previous_period = {}

    # Previous Year
    client['compare_start_date'] = windows['yoy_start']
    client['compare_end_date']   = windows['yoy_end']
    data_previous_year = get_dimension_cut(client, dimension, filters)

    # Timeseries: current period window
    data_timeseries = get_dimension_timeseries(
        client, dimension, filters, effective_time_dimension,
        start_date_override=windows['current_start'].strftime('%Y-%m-%d'),
        end_date_override=windows['current_end'].strftime('%Y-%m-%d'),
    )

    # Timeseries: previous year window (always available)
    data_yoy_timeseries = get_dimension_timeseries(
        client, dimension, filters, effective_time_dimension,
        start_date_override=windows['yoy_start'].strftime('%Y-%m-%d'),
        end_date_override=windows['yoy_end'].strftime('%Y-%m-%d'),
    )

    # Timeseries: previous period window (not available for ytd)
    if windows['prev_period_available']:
        data_mom_timeseries = get_dimension_timeseries(
            client, dimension, filters, effective_time_dimension,
            start_date_override=windows['prev_start'].strftime('%Y-%m-%d'),
            end_date_override=windows['prev_end'].strftime('%Y-%m-%d'),
        )
    else:
        data_mom_timeseries = {}

    data_key = _build_data_key(dimension, filters, date_range)

    fmt = '%d/%m/%Y'
    resolved_dates = {
        'current_start': windows['current_start'].strftime(fmt),
        'current_end':   windows['current_end'].strftime(fmt),
        'yoy_start':     windows['yoy_start'].strftime(fmt),
        'yoy_end':       windows['yoy_end'].strftime(fmt),
    }
    if windows['prev_period_available']:
        resolved_dates['prev_start'] = windows['prev_start'].strftime(fmt)
        resolved_dates['prev_end']   = windows['prev_end'].strftime(fmt)

    if not isinstance(client.get('dimension_data'), dict):
        client['dimension_data'] = {}
    client['dimension_data'][data_key] = {
        'date_range':      date_range,
        'time_dimension':  effective_time_dimension,
        'mom':             data_previous_period,
        'yoy':             data_previous_year,
        'timeseries':      data_timeseries,
        'yoy_timeseries':  data_yoy_timeseries,
        'mom_timeseries':  data_mom_timeseries,
        'resolved_dates':  resolved_dates,
    }

    from monthly_reports.main import TimestampEncoder
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(client, f, ensure_ascii=False, indent=2, cls=TimestampEncoder)

    return {
        'dimension':             dimension,
        'filters':               filters or [],
        'date_range':            date_range,
        'date_range_label':      windows['label'],
        'data_key':              data_key,
        'time_dimension':        effective_time_dimension,
        'default_time_dimension': windows['default_time_dimension'],
        'prev_period_available': windows['prev_period_available'],
        'resolved_dates':        resolved_dates,
        'previous_period':       data_previous_period,
        'previous_year':         data_previous_year,
        'timeseries':            data_timeseries,
    }
