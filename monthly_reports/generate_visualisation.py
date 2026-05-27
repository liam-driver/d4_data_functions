import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PCT_METRICS = {
    "ROAS", "CTR", "Conversion Rate", "Impression Share",
    "Abs. Top Impression Share", "View Rate", "Hook Rate", "Hold Rate",
}
_PCT_FMT = mticker.FuncFormatter(lambda x, _: f"{x:.2f}%")

TIME_DIMENSIONS = {'Week number (ISO)', 'Month', 'Year', 'Date'}


# ── BRAND CONFIG ─────────────────────────────────────────────────────
BRAND = {
    "primary":   "#FEC042",
    "secondary": "#F27D39",
    "tertiary":  "#4FA6A4",
    "quaternary": "#2B2D42",
    "background": "#FFF7E4",
    "colours": ["#FEC042", "#F27D39", "#4FA6A4", "#2B2D42"],  # cycle order for multi-metric charts
    "font": "Plus Jakarta Sans",
}

def build_monthly_df(client):
    """Flatten client['timeseries_data'] into a tidy dataframe for chart rendering."""
    ts = client.get('timeseries_data', {})
    rows = []
    for channel, weeks in ts.items():
        for week_str, metrics in weeks.items():
            row = {'Ad Channel': channel, 'Week number (ISO)': int(week_str)}
            for metric, vals in metrics.items():
                raw = vals.get('curr', '0') if isinstance(vals, dict) else vals
                clean = str(raw).replace('£', '').replace('%', '').replace(',', '').replace('x', '').strip()
                try:
                    row[metric] = float(clean)
                except (ValueError, TypeError):
                    row[metric] = 0.0
            rows.append(row)
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=['Ad Channel', 'Week number (ISO)'])
    if not df.empty:
        df['Week number (ISO)'] = df['Week number (ISO)'].astype(int)
        df = df.sort_values('Week number (ISO)').reset_index(drop=True)
    return df


def _parse_val(raw):
    clean = str(raw).replace('£', '').replace('%', '').replace(',', '').replace('x', '').strip()
    try:
        return float(clean)
    except (ValueError, TypeError):
        return 0.0


def build_dimension_df(client, data_source, comparison_type):
    """
    Build a DataFrame from client['dimension_data'][data_source] for graph rendering.
    comparison_type: 'timeseries' | 'mom' | 'yoy'
    For timeseries: columns are [dimension_col, time_dimension_col, ...metrics] using curr values.
    For mom/yoy: columns are [dimension_col, ...metrics] using curr values only.
    """
    dim_entry = client.get('dimension_data', {}).get(data_source, {})
    data = dim_entry.get(comparison_type, {})
    dimension_col = data_source.split('::')[0]
    time_col = dim_entry.get('time_dimension', 'Week number (ISO)')
    rows = []

    if comparison_type == 'timeseries':
        for dim_val, time_data in data.items():
            for time_key, metrics in time_data.items():
                parsed_key = int(time_key) if time_col in ('Week number (ISO)', 'Year') else time_key
                row = {dimension_col: dim_val, time_col: parsed_key}
                for metric, vals in metrics.items():
                    row[metric] = _parse_val(vals.get('curr', '0') if isinstance(vals, dict) else vals)
                rows.append(row)
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[dimension_col, time_col])
        if not df.empty:
            df = df.sort_values(time_col).reset_index(drop=True)
    else:
        for dim_val, metrics in data.items():
            if not isinstance(metrics, dict):
                continue
            row = {dimension_col: dim_val}
            for metric, vals in metrics.items():
                row[metric] = _parse_val(vals.get('curr', '0') if isinstance(vals, dict) else vals)
            rows.append(row)
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[dimension_col])

    return df


def build_comparison_df(client, data_source, comparison_type):
    """
    Build a long-format DataFrame for comparison charts.
    Returns rows with [dimension_col, 'Period', ...metrics] where Period is 'Current' or 'Previous'.
    comparison_type: 'mom' | 'yoy'
    """
    dim_entry = client.get('dimension_data', {}).get(data_source, {})
    data = dim_entry.get(comparison_type, {})
    dimension_col = data_source.split('::')[0]
    rows = []
    for dim_val, metrics in data.items():
        if not isinstance(metrics, dict):
            continue
        curr_row = {dimension_col: dim_val, 'Period': 'Current'}
        prev_row = {dimension_col: dim_val, 'Period': 'Previous'}
        for metric, vals in metrics.items():
            if isinstance(vals, dict):
                curr_row[metric] = _parse_val(vals.get('curr', '0'))
                prev_row[metric] = _parse_val(vals.get('prev', '0'))
            else:
                curr_row[metric] = _parse_val(vals)
                prev_row[metric] = 0.0
        rows.extend([curr_row, prev_row])
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=[dimension_col, 'Period'])


def _build_df_for_spec(client, spec):
    """Return the correctly sourced and filtered DataFrame for a graph spec."""
    data_source = spec.get('data_source')
    style = spec.get('style', 'trend')
    if data_source:
        if style == 'comparison':
            comparison = spec.get('comparison', 'yoy')
            df = build_comparison_df(client, data_source, comparison)
        else:
            x_dim = spec.get('dimensions', {}).get('x', '')
            ct = 'timeseries' if x_dim in TIME_DIMENSIONS else 'mom'
            df = build_dimension_df(client, data_source, ct)
    else:
        df = build_monthly_df(client)
    return _apply_monthly_filters(df, spec.get('filters', '{}'))


def _resolve_x_col(spec, df, metrics):
    """Return the x column to use, falling back to the dimension column when the spec's declared
    x is a time dimension not present in the dataframe (comparison/distribution charts)."""
    x_col = spec.get('dimensions', {}).get('x', 'Week number (ISO)')
    if x_col not in df.columns or x_col in metrics:
        data_source = spec.get('data_source')
        if data_source:
            dim_col = data_source.split('::')[0]
            if dim_col in df.columns:
                return dim_col
        return next((td for td in TIME_DIMENSIONS if td in df.columns), x_col)
    return x_col


def _apply_monthly_filters(df, filters):
    """Filter a monthly df; uses partial (contains) matching so 'Paid Social'
    catches both 'Paid Social Static' and 'Paid Social Video'."""
    if isinstance(filters, str):
        filters = json.loads(filters)
    for dim, val in filters.items():
        if dim not in df.columns:
            continue
        if isinstance(val, list):
            df = df[df[dim].isin(val)]
        else:
            df = df[df[dim].str.contains(str(val), case=False, na=False)]
    return df


def render_graph(client, spec):
    # Get the graph spec (temp)
    fn = GRAPH_REGISTRY.get(spec["graph_type"]) 
    if not fn:
        raise ValueError(f"Unknown graph type: {spec['graph_type']}")
    return fn(spec, client)


def render_line_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title   = graph["title"]
    metrics = graph["metrics"][:2]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics = [m for m in metrics if m in df.columns]
    if not metrics:
        return None

    x_col    = _resolve_x_col(graph, df, metrics)
    group_by = graph.get('dimensions', {}).get('group_by')
    use_group_by = bool(group_by and group_by in df.columns and group_by != x_col)

    for metric in metrics:
        df[metric] = pd.to_numeric(df[metric], errors='coerce')

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    ax2 = ax.twinx() if (len(metrics) > 1 and not use_group_by) else None

    # ── 4. PLOT ──────────────────────────────────────────────────────
    if use_group_by:
        # One line per group_by value (top 6 by total of first metric)
        top_groups = (
            df.groupby(group_by)[metrics[0]].sum()
            .nlargest(6).index.tolist()
        )
        all_x_vals = sorted(df[x_col].unique())
        colour_cycle = BRAND["colours"] * (len(top_groups) // len(BRAND["colours"]) + 1)
        for i, group_val in enumerate(top_groups):
            g_df = (df[df[group_by] == group_val]
                    .groupby(x_col, as_index=False)[metrics].sum()
                    .sort_values(x_col))
            x_pos = g_df[x_col] if x_col == 'Date' else range(len(g_df))
            ax.plot(x_pos, g_df[metrics[0]], linewidth=2, marker='o', markersize=3,
                    label=str(group_val), color=colour_cycle[i % len(colour_cycle)])
            ax.fill_between(x_pos, g_df[metrics[0]], alpha=0.07,
                            color=colour_cycle[i % len(colour_cycle)])
        if x_col != 'Date':
            ax.set_xticks(range(len(all_x_vals)))
            ax.set_xticklabels([str(v) for v in all_x_vals], rotation=45, ha='right')
    else:
        # Single-series: aggregate all rows per x_col value
        df = df.groupby(x_col, as_index=False)[metrics].sum()
        x_pos = df[x_col] if x_col == 'Date' else range(len(df))
        for i, metric in enumerate(metrics):
            colour = BRAND["colours"][i % len(BRAND["colours"])]
            target_ax = ax2 if (i > 0 and ax2 is not None) else ax
            target_ax.plot(x_pos, df[metric], linewidth=2.5, marker='o', markersize=4,
                           label=metric, color=colour)
            target_ax.fill_between(x_pos, df[metric], alpha=0.1, color=colour)
        if x_col != 'Date':
            ax.set_xticks(list(x_pos))
            ax.set_xticklabels(df[x_col], rotation=45, ha='right')

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight='bold', pad=12, color=BRAND['quaternary'])
    ax.set_xlabel(x_col, fontsize=11)

    if not use_group_by and ax2 is not None:
        ax.set_ylabel(metrics[0], fontsize=11, color=BRAND['quaternary'])
        ax2.set_ylabel(metrics[1], fontsize=11, color=BRAND['quaternary'])
        ax2.tick_params(axis='y', colors=BRAND['quaternary'])
    else:
        ax.set_ylabel(metrics[0], fontsize=11, color=BRAND['quaternary'])

    if metrics[0] in PCT_METRICS:
        ax.yaxis.set_major_formatter(_PCT_FMT)
    if ax2 and len(metrics) > 1 and metrics[1] in PCT_METRICS:
        ax2.yaxis.set_major_formatter(_PCT_FMT)

    if x_col == 'Date':
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        fig.autofmt_xdate(rotation=45)

    ax.grid(True, alpha=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    if ax2 is not None:
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2,
                  facecolor=BRAND['background'], edgecolor=BRAND['quaternary'])
    else:
        ax.legend(lines1, labels1, facecolor=BRAND['background'], edgecolor=BRAND['quaternary'])

    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path

def render_bar_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title   = graph["title"]
    metrics = graph["metrics"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics = [m for m in metrics if m in df.columns]
    if not metrics:
        return None

    # Comparison df (has Period column): dimension is x, Period is group_by
    data_source = graph.get('data_source')
    if 'Period' in df.columns and data_source:
        x_col = data_source.split('::')[0]
        group_by = 'Period'
    else:
        x_col = _resolve_x_col(graph, df, metrics)
        group_by = graph.get('dimensions', {}).get('group_by')
    use_group_by = bool(group_by and group_by in df.columns and group_by != x_col)

    for metric in metrics:
        df[metric] = pd.to_numeric(df[metric], errors='coerce')

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))

    # ── 4. PLOT ──────────────────────────────────────────────────────
    if use_group_by:
        # Grouped bars: one cluster per x_col value, one bar per group_by value
        top_groups = (
            df.groupby(group_by)[metrics[0]].sum()
            .nlargest(6).index.tolist()
        )
        x_vals = sorted(df[x_col].unique())
        x = range(len(x_vals))
        bar_width = 0.8 / len(top_groups)
        colour_cycle = BRAND["colours"] * (len(top_groups) // len(BRAND["colours"]) + 1)
        for i, group_val in enumerate(top_groups):
            g_df = df[df[group_by] == group_val].groupby(x_col, as_index=False)[metrics].sum()
            heights = [
                float(g_df[g_df[x_col] == xv][metrics[0]].values[0])
                if xv in g_df[x_col].values else 0.0
                for xv in x_vals
            ]
            offset = (i - len(top_groups) / 2 + 0.5) * bar_width
            ax.bar([pos + offset for pos in x], heights, width=bar_width,
                   label=str(group_val), color=colour_cycle[i % len(colour_cycle)], alpha=0.9)
        ax.set_xticks(list(x))
        ax.set_xticklabels([str(v) for v in x_vals], rotation=45, ha='right')
    else:
        df = df.groupby(x_col, as_index=False)[metrics].sum()
        num_metrics = len(metrics)
        bar_width = 0.8 / num_metrics
        x = range(len(df[x_col]))
        for i, metric in enumerate(metrics):
            colour = BRAND["colours"][i % len(BRAND["colours"])]
            offset = (i - num_metrics / 2 + 0.5) * bar_width
            ax.bar([pos + offset for pos in x], df[metric], width=bar_width,
                   label=metric, color=colour, alpha=0.9)
        ax.set_xticks(list(x))
        ax.set_xticklabels(
            [d.strftime("%b %d") if hasattr(d, 'strftime') else str(d) for d in df[x_col]],
            rotation=45, ha='right'
        )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight='bold', pad=12, color=BRAND['quaternary'])
    ax.set_xlabel(x_col, fontsize=11)
    ax.set_ylabel('Value', fontsize=11)
    if metrics and all(m in PCT_METRICS for m in metrics):
        ax.yaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.2, axis='y')
    ax.legend(facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])
    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def render_stacked_bar_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title   = graph["title"]
    metrics = graph["metrics"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics_present = [m for m in metrics if m in df.columns]
    if not metrics_present:
        return None
    x_col    = _resolve_x_col(graph, df, metrics_present)
    group_by = graph.get('dimensions', {}).get('group_by')
    use_group_by = bool(group_by and group_by in df.columns and group_by != x_col)

    for m in metrics_present:
        df[m] = pd.to_numeric(df[m], errors='coerce')
    metrics = metrics_present

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))

    # ── 4. PLOT ──────────────────────────────────────────────────────
    if use_group_by:
        # Stack per group_by value over x_col (e.g. Cost by Ad Channel per week)
        top_groups = (
            df.groupby(group_by)[metrics[0]].sum()
            .nlargest(6).index.tolist()
        )
        x_vals = sorted(df[x_col].unique())
        x = range(len(x_vals))
        bottoms = [0.0] * len(x_vals)
        colour_cycle = BRAND["colours"] * (len(top_groups) // len(BRAND["colours"]) + 1)
        for i, group_val in enumerate(top_groups):
            g_df = df[df[group_by] == group_val].groupby(x_col, as_index=False)[metrics].sum()
            heights = [
                float(g_df[g_df[x_col] == xv][metrics[0]].values[0])
                if xv in g_df[x_col].values else 0.0
                for xv in x_vals
            ]
            ax.bar(x, heights, bottom=bottoms, width=0.6, label=str(group_val),
                   color=colour_cycle[i % len(colour_cycle)], alpha=0.9)
            bottoms = [b + h for b, h in zip(bottoms, heights)]
        ax.set_xticks(list(x))
        ax.set_xticklabels([str(v) for v in x_vals], rotation=45, ha='right')
    else:
        # Stack per metric over x_col (existing behaviour)
        df = df.groupby(x_col, as_index=False)[metrics].sum()
        x = range(len(df[x_col]))
        bottoms = [0] * len(df)
        for i, metric in enumerate(metrics):
            colour = BRAND["colours"][i % len(BRAND["colours"])]
            ax.bar(x, df[metric], bottom=bottoms, width=0.6, label=metric,
                   color=colour, alpha=0.9)
            bottoms = [b + v for b, v in zip(bottoms, df[metric])]
        ax.set_xticks(list(x))
        ax.set_xticklabels(
            [d.strftime("%b %d") if hasattr(d, 'strftime') else str(d) for d in df[x_col]],
            rotation=45, ha='right'
        )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight='bold', pad=12, color=BRAND['quaternary'])
    ax.set_xlabel(x_col, fontsize=11)
    ax.set_ylabel('Value', fontsize=11)
    if metrics and all(m in PCT_METRICS for m in metrics):
        ax.yaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.2, axis='y')
    ax.legend(facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])
    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def render_pie_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title   = graph["title"]
    filters = graph["filters"]
    x_col   = graph["dimensions"]["x"]
    metrics = graph["metrics"]
    start   = graph["date_range"]["start"]
    end     = graph["date_range"]["end"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics_present = [m for m in metrics if m in df.columns]
    if not metrics_present:
        return None
    x_col = _resolve_x_col(graph, df, metrics_present)
    for m in metrics_present:
        df[m] = pd.to_numeric(df[m], errors='coerce')
    df = df.groupby(x_col, as_index=False)[metrics_present].sum()
    metrics = metrics_present

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 7))  # square canvas works best for pie

    # ── 4. PLOT THE PIE ──────────────────────────────────────────────
    # Pie charts show a single metric split across the x_col categories
    # We sum the first metric across all rows grouped by x_col
    metric = metrics[0]  # pie only makes sense for one metric at a time
    pie_data = df.groupby(x_col)[metric].sum()

    wedge_colours = [
        BRAND["colours"][i % len(BRAND["colours"])]
        for i in range(len(pie_data))
    ]

    ax.pie(
        pie_data.values,
        labels=pie_data.index,
        colors=wedge_colours,
        autopct="%1.1f%%",      # show percentage on each wedge
        pctdistance=0.85,       # how far % label sits from centre
        startangle=90,          # start from 12 o'clock
        wedgeprops={"edgecolor": BRAND["background"], "linewidth": 2}
    )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight="bold", pad=16, color=BRAND["quaternary"])
    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path

def render_line_bar_combo_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title    = graph["title"]
    filters  = graph["filters"]
    x_col    = graph["dimensions"]["x"]
    metrics  = graph["metrics"]          # expects exactly 2: [bar_metric, line_metric]
    start    = graph["date_range"]["start"]
    end      = graph["date_range"]["end"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics_present = [m for m in metrics if m in df.columns]
    if len(metrics_present) < 2:
        return None
    x_col = _resolve_x_col(graph, df, metrics_present)
    for m in metrics_present:
        df[m] = pd.to_numeric(df[m], errors='coerce')
    df = df.groupby(x_col, as_index=False)[metrics_present].sum()
    metrics = metrics_present

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()  # second y axis shares the same x axis

    # ── 4. PLOT BAR (first metric) + LINE (second metric) ────────────
    bar_metric  = metrics[0]
    line_metric = metrics[1]

    bar_colour  = BRAND["colours"][0]
    line_colour = BRAND["colours"][1]

    x = range(len(df[x_col]))

    # Bar on primary y axis
    ax1.bar(
        x,
        df[bar_metric],
        width=0.6,
        color=bar_colour,
        alpha=0.7,
        label=bar_metric
    )

    # Line on secondary y axis
    ax2.plot(
        x,
        df[line_metric],
        color=line_colour,
        linewidth=2.5,
        marker="o",
        markersize=4,
        label=line_metric
    )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax1.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax1.set_xlabel(x_col.capitalize(), fontsize=11)
    ax1.set_ylabel(bar_metric, fontsize=11, color=BRAND["quaternary"])
    ax2.set_ylabel(line_metric, fontsize=11, color=BRAND["quaternary"])

    if bar_metric in PCT_METRICS:
        ax1.yaxis.set_major_formatter(_PCT_FMT)
    if line_metric in PCT_METRICS:
        ax2.yaxis.set_major_formatter(_PCT_FMT)

    ax1.set_xticks(list(x))
    ax1.set_xticklabels(
        [d.strftime("%b %d") if hasattr(d, 'strftime') else str(d) for d in df[x_col]],
        rotation=45,
        ha="right"
    )

    ax1.grid(True, alpha=0.2, axis="y")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])

    ax2.tick_params(axis="y", colors=BRAND["quaternary"])

    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def render_horizontal_bar_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title   = graph["title"]
    filters = graph["filters"]
    x_col   = graph["dimensions"]["x"]
    metrics = graph["metrics"]
    start   = graph["date_range"]["start"]
    end     = graph["date_range"]["end"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics = [m for m in metrics if m in df.columns]
    if not metrics:
        return None
    x_col = _resolve_x_col(graph, df, metrics)
    for m in metrics:
        df[m] = pd.to_numeric(df[m], errors='coerce')
    df = df.groupby(x_col, as_index=False)[metrics].sum()

    # Sort so largest bar is at the top
    df = df.sort_values(by=metrics[0], ascending=True)

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.5)))  # height scales with number of rows

    # ── 4. PLOT HORIZONTAL BARS ──────────────────────────────────────
    num_metrics = len(metrics)
    bar_height  = 0.8 / num_metrics
    y = range(len(df[x_col]))

    for i, metric in enumerate(metrics):
        colour = BRAND["colours"][i % len(BRAND["colours"])]
        offset = (i - num_metrics / 2 + 0.5) * bar_height
        ax.barh(
            [pos + offset for pos in y],
            df[metric],
            height=bar_height,
            label=metric,
            color=colour,
            alpha=0.9
        )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax.set_xlabel("Value", fontsize=11)
    ax.set_yticks(list(y))
    ax.set_yticklabels(df[x_col])
    if metrics and metrics[0] in PCT_METRICS:
        ax.xaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.2, axis="x")
    ax.legend(facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])
    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def render_scatter_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title   = graph["title"]
    filters = graph["filters"]
    x_col   = graph["dimensions"]["x"]
    metrics = graph["metrics"]          # expects exactly 2: [x_metric, y_metric]
    start   = graph["date_range"]["start"]
    end     = graph["date_range"]["end"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 6))  # squarer canvas works better for scatter

    # ── 4. PLOT THE SCATTER ──────────────────────────────────────────
    # First metric on x axis, second metric on y axis
    x_metric = metrics[0]
    y_metric = metrics[1]

    ax.scatter(
        df[x_metric],
        df[y_metric],
        color=BRAND["primary"],
        edgecolors=BRAND["quaternary"],
        linewidths=0.5,
        s=80,           # dot size
        alpha=0.8,
        zorder=3        # render dots above grid lines
    )

    # Optionally label each point with its x_col value (e.g. date or campaign name)
    for _, row in df.iterrows():
        ax.annotate(
            str(row[x_col]),
            (row[x_metric], row[y_metric]),
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=8,
            color=BRAND["quaternary"],
            alpha=0.7
        )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax.set_xlabel(x_metric, fontsize=11)
    ax.set_ylabel(y_metric, fontsize=11)
    if x_metric in PCT_METRICS:
        ax.xaxis.set_major_formatter(_PCT_FMT)
    if y_metric in PCT_METRICS:
        ax.yaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.2)
    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def render_comparison_bar_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title      = graph["title"]
    x_col      = graph["dimensions"]["x"]
    metrics    = graph["metrics"][:1]
    comparison = graph.get("comparison", "mom")
    data_source = graph.get("data_source")

    if not data_source:
        return None

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = build_comparison_df(client, data_source, comparison)
    metrics = [m for m in metrics if m in df.columns]
    if not metrics or x_col not in df.columns:
        return None

    metric = metrics[0]
    df[metric] = pd.to_numeric(df[metric], errors='coerce')

    # Sort dimension values by current period descending
    curr_vals = df[df['Period'] == 'Current'].set_index(x_col)[metric]
    sorted_dims = curr_vals.sort_values(ascending=False).index.tolist()

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))

    # ── 4. PLOT GROUPED BARS ─────────────────────────────────────────
    bar_width = 0.35
    x = range(len(sorted_dims))

    for i, period in enumerate(['Current', 'Previous']):
        period_df = df[df['Period'] == period].set_index(x_col).reindex(sorted_dims).reset_index()
        colour = BRAND["colours"][i % len(BRAND["colours"])]
        offset = (i - 0.5) * bar_width
        ax.bar(
            [pos + offset for pos in x],
            period_df[metric],
            width=bar_width,
            label=period,
            color=colour,
            alpha=0.9
        )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax.set_xlabel(x_col, fontsize=11)
    ax.set_ylabel(metric, fontsize=11)
    ax.set_xticks(list(x))
    ax.set_xticklabels(sorted_dims, rotation=45, ha='right')
    if metric in PCT_METRICS:
        ax.yaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.2, axis='y')
    ax.legend(facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])
    plt.tight_layout()

    # ── 6. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def render_comparison_line_chart(graph, client):
    # ── 1. EXTRACT THE SPEC ──────────────────────────────────────────
    title      = graph["title"]
    metrics    = graph["metrics"][:1]
    comparison = graph.get("comparison", "mom")
    data_source = graph.get("data_source")

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    if data_source:
        df = build_dimension_df(client, data_source, 'timeseries')
        time_col = client.get('dimension_data', {}).get(data_source, {}).get('time_dimension', 'Week number (ISO)')
    else:
        df = build_monthly_df(client)
        time_col = 'Week number (ISO)'

    df = _apply_monthly_filters(df, graph.get('filters', '{}'))
    metrics = [m for m in metrics if m in df.columns]
    if not metrics or time_col not in df.columns:
        return None

    metric = metrics[0]
    df[metric] = pd.to_numeric(df[metric], errors='coerce')
    df = df.groupby(time_col, as_index=False)[metric].sum()
    df = df.sort_values(time_col).reset_index(drop=True)

    # ── 3. SPLIT INTO CURRENT AND PREVIOUS PERIOD ────────────────────
    def _ts(val):
        return val if isinstance(val, pd.Timestamp) else pd.Timestamp(val)

    start      = _ts(client['start_date'])
    end        = _ts(client['end_date'])
    comp_key   = 'yoy' if comparison == 'yoy' else 'mom'
    prev_start = _ts(client[f'compare_start_{comp_key}'])
    prev_end   = _ts(client[f'compare_end_{comp_key}'])

    def _keys_in_range(s, e):
        dates = pd.date_range(s, e, freq='D')
        if time_col == 'Week number (ISO)':
            return sorted(set(int(w) for w in dates.isocalendar().week))
        elif time_col == 'Month':
            return sorted(set(d.to_period('M').strftime('%Y-%m') for d in dates))
        elif time_col == 'Year':
            return sorted(set(d.year for d in dates))
        else:
            return sorted(set(d.strftime('%Y-%m-%d') for d in dates))

    curr_keys = _keys_in_range(start, end)
    prev_keys = _keys_in_range(prev_start, prev_end)

    curr_df = df[df[time_col].isin(curr_keys)].sort_values(time_col).reset_index(drop=True)
    prev_df = df[df[time_col].isin(prev_keys)].sort_values(time_col).reset_index(drop=True)
    curr_df['_pos'] = range(1, len(curr_df) + 1)
    prev_df['_pos'] = range(1, len(prev_df) + 1)

    # ── 4. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))

    # ── 5. PLOT BOTH PERIOD LINES ────────────────────────────────────
    if not curr_df.empty:
        ax.plot(curr_df['_pos'], curr_df[metric], linewidth=2.5, marker='o', markersize=4,
                label='Current', color=BRAND["colours"][0])
        ax.fill_between(curr_df['_pos'], curr_df[metric], alpha=0.1, color=BRAND["colours"][0])

    if not prev_df.empty:
        ax.plot(prev_df['_pos'], prev_df[metric], linewidth=2.5, marker='o', markersize=4,
                label='Previous', color=BRAND["colours"][1], linestyle='--')
        ax.fill_between(prev_df['_pos'], prev_df[metric], alpha=0.1, color=BRAND["colours"][1])

    # ── 6. FORMATTING ────────────────────────────────────────────────
    unit_label = 'Week' if time_col == 'Week number (ISO)' else ('Month' if time_col == 'Month' else 'Period')
    max_pos = max(len(curr_df), len(prev_df), 1)
    ax.set_xticks(range(1, max_pos + 1))
    ax.set_xticklabels([f'{unit_label} {i}' for i in range(1, max_pos + 1)])

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax.set_xlabel('Position in Period', fontsize=11)
    ax.set_ylabel(metric, fontsize=11, color=BRAND["quaternary"])
    if metric in PCT_METRICS:
        ax.yaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.3)
    ax.legend(facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])
    plt.tight_layout()

    # ── 7. SAVE AND RETURN ───────────────────────────────────────────
    charts_dir = os.path.join(PROJECT_ROOT, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    path = os.path.join(charts_dir, f"{title.replace(' ', '_')}.png")
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def initialise_brand():
    font_dir = os.path.join(PROJECT_ROOT, "fonts")
    for font_file in os.listdir(font_dir):
        if font_file.endswith(".ttf"):
            fm.fontManager.addfont(os.path.join(font_dir, font_file))

    # Apply global styles
    plt.rcParams.update({
        "figure.facecolor":  BRAND["background"],
        "axes.facecolor":    BRAND["background"],
        "axes.edgecolor":    BRAND["quaternary"],
        "axes.labelcolor":   BRAND["quaternary"],
        "xtick.color":       BRAND["quaternary"],
        "ytick.color":       BRAND["quaternary"],
        "text.color":        BRAND["quaternary"],
        "grid.color":        BRAND["quaternary"],
        "grid.alpha":        0.2,
        "font.family":       BRAND["font"],
    })


# Dictionary containing all the graph types and the functions that correspond to them
GRAPH_REGISTRY = {
    "line":             render_line_chart,
    "bar":              render_bar_chart,
    "stacked_bar":      render_stacked_bar_chart,
    "pie":              render_pie_chart,
    "line_bar_combo":   render_line_bar_combo_chart,
    "horizontal_bar":   render_horizontal_bar_chart,
    "scatter":          render_scatter_chart,
    "comparison_bar":   render_comparison_bar_chart,
    "comparison_line":  render_comparison_line_chart,
}

