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
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
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
    For timeseries: columns are [dimension_col, 'Week number (ISO)', ...metrics]
    For mom/yoy: columns are [dimension_col, ...metrics] using curr values
    """
    dim_entry = client.get('dimension_data', {}).get(data_source, {})
    data = dim_entry.get(comparison_type, {})
    dimension_col = data_source.split('::')[0]
    rows = []

    if comparison_type == 'timeseries':
        for dim_val, weeks in data.items():
            for week_str, metrics in weeks.items():
                row = {dimension_col: dim_val, 'Week number (ISO)': int(week_str)}
                for metric, vals in metrics.items():
                    row[metric] = _parse_val(vals.get('curr', '0') if isinstance(vals, dict) else vals)
                rows.append(row)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df['Week number (ISO)'] = df['Week number (ISO)'].astype(int)
            df = df.sort_values('Week number (ISO)').reset_index(drop=True)
    else:
        for dim_val, metrics in data.items():
            if not isinstance(metrics, dict):
                continue
            row = {dimension_col: dim_val}
            for metric, vals in metrics.items():
                row[metric] = _parse_val(vals.get('curr', '0') if isinstance(vals, dict) else vals)
            rows.append(row)
        df = pd.DataFrame(rows) if rows else pd.DataFrame()

    return df


def _build_df_for_spec(client, spec):
    """Return the correctly sourced and filtered DataFrame for a graph spec."""
    data_source = spec.get('data_source')
    if data_source:
        ct = 'timeseries' if spec.get('dimensions', {}).get('x') == 'Week number (ISO)' else 'mom'
        df = build_dimension_df(client, data_source, ct)
    else:
        df = build_monthly_df(client)
    return _apply_monthly_filters(df, spec.get('filters', '{}'))


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
    filters = graph["filters"]
    x_col   = graph["dimensions"]["x"]
    metrics = graph["metrics"][:2]
    start   = graph["date_range"]["start"]
    end     = graph["date_range"]["end"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics = [m for m in metrics if m in df.columns]
    if x_col not in df.columns or x_col in metrics:
        x_col = 'Week number (ISO)'
    for metric in metrics:
        df[metric] = pd.to_numeric(df[metric], errors='coerce')
    df = df.groupby(x_col, as_index=False)[metrics].sum()

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    # When multiple metrics are present, use a secondary y-axis so metrics
    # with very different scales (e.g. Impressions vs CTR) are both visible
    ax2 = ax.twinx() if len(metrics) > 1 else None

    # ── 4. PLOT EACH METRIC AS A LINE ────────────────────────────────
    # Use index positions for non-Date x columns (e.g. ISO week numbers are
    # integers like 14, 15, 16 — plotting them directly misaligns the ticks)
    x_pos = df[x_col] if x_col == 'Date' else range(len(df))

    for i, metric in enumerate(metrics):
        colour = BRAND["colours"][i % len(BRAND["colours"])]
        target_ax = ax2 if (i > 0 and ax2 is not None) else ax
        target_ax.plot(
            x_pos,
            df[metric],
            linewidth=2.5,
            marker="o",
            markersize=4,
            label=metric,
            color=colour
        )
        target_ax.fill_between(
            x_pos,
            df[metric],
            alpha=0.1,
            color=colour
        )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax.set_xlabel(x_col.capitalize(), fontsize=11)

    if ax2 is not None:
        ax.set_ylabel(metrics[0], fontsize=11, color=BRAND["quaternary"])
        ax2.set_ylabel(metrics[1], fontsize=11, color=BRAND["quaternary"])
        ax2.tick_params(axis="y", colors=BRAND["quaternary"])
    else:
        ax.set_ylabel(metrics[0], fontsize=11, color=BRAND["quaternary"])

    if metrics and metrics[0] in PCT_METRICS:
        ax.yaxis.set_major_formatter(_PCT_FMT)
    if ax2 and len(metrics) > 1 and metrics[1] in PCT_METRICS:
        ax2.yaxis.set_major_formatter(_PCT_FMT)

    if x_col == 'Date':
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        fig.autofmt_xdate(rotation=45)
    else:
        ax.set_xticks(list(x_pos))
        ax.set_xticklabels(df[x_col], rotation=45, ha='right')

    ax.grid(True, alpha=0.3)

    lines1, labels1 = ax.get_legend_handles_labels()
    if ax2 is not None:
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])
    else:
        ax.legend(lines1, labels1, facecolor=BRAND["background"], edgecolor=BRAND["quaternary"])

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
    filters = graph["filters"]
    x_col   = graph["dimensions"]["x"]
    metrics = graph["metrics"]
    start   = graph["date_range"]["start"]
    end     = graph["date_range"]["end"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics = [m for m in metrics if m in df.columns]
    if x_col not in df.columns or x_col in metrics:
        x_col = 'Week number (ISO)'
    for metric in metrics:
        df[metric] = pd.to_numeric(df[metric], errors='coerce')
    df = df.groupby(x_col, as_index=False)[metrics].sum()

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))

    # ── 4. PLOT EACH METRIC AS A BAR ─────────────────────────────────
    # If multiple metrics, bars are placed side by side
    num_metrics = len(metrics)
    bar_width = 0.8 / num_metrics  # total width split across metrics
    x = range(len(df[x_col]))

    for i, metric in enumerate(metrics):
        colour = BRAND["colours"][i % len(BRAND["colours"])]
        offset = (i - num_metrics / 2 + 0.5) * bar_width  # centre the group
        ax.bar(
            [pos + offset for pos in x],
            df[metric],
            width=bar_width,
            label=metric,
            color=colour,
            alpha=0.9
        )

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax.set_xlabel(x_col.capitalize(), fontsize=11)
    ax.set_ylabel("Value", fontsize=11)
    ax.set_xticks(list(x))
    ax.set_xticklabels(
        [d.strftime("%b %d") if hasattr(d, 'strftime') else str(d) for d in df[x_col]],
        rotation=45,
        ha="right"
    )
    if metrics and all(m in PCT_METRICS for m in metrics):
        ax.yaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.2, axis="y")
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
    filters = graph["filters"]
    x_col   = graph["dimensions"]["x"]
    metrics = graph["metrics"]
    start   = graph["date_range"]["start"]
    end     = graph["date_range"]["end"]

    # ── 2. CONFIGURE THE DATAFRAME ───────────────────────────────────
    df = _build_df_for_spec(client, graph)

    metrics_present = [m for m in metrics if m in df.columns]
    if x_col not in df.columns or x_col in metrics_present:
        x_col = 'Week number (ISO)'
    for m in metrics_present:
        df[m] = pd.to_numeric(df[m], errors='coerce')
    df = df.groupby(x_col, as_index=False)[metrics_present].sum()
    metrics = metrics_present

    # ── 3. CREATE THE FIGURE ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))

    # ── 4. PLOT STACKED BARS ─────────────────────────────────────────
    # Each metric is stacked on top of the previous one
    # We track the bottom of each stack so bars sit on top of each other
    x = range(len(df[x_col]))
    bottoms = [0] * len(df)  # start all bars from 0

    for i, metric in enumerate(metrics):
        colour = BRAND["colours"][i % len(BRAND["colours"])]
        ax.bar(
            x,
            df[metric],
            bottom=bottoms,  # where this bar starts (top of previous)
            width=0.6,
            label=metric,
            color=colour,
            alpha=0.9
        )
        # Update bottoms so next metric stacks on top
        bottoms = [b + v for b, v in zip(bottoms, df[metric])]

    # ── 5. FORMATTING ────────────────────────────────────────────────
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12, color=BRAND["quaternary"])
    ax.set_xlabel(x_col.capitalize(), fontsize=11)
    ax.set_ylabel("Value", fontsize=11)
    ax.set_xticks(list(x))
    ax.set_xticklabels(
        [d.strftime("%b %d") if hasattr(d, 'strftime') else str(d) for d in df[x_col]],
        rotation=45,
        ha="right"
    )
    if metrics and all(m in PCT_METRICS for m in metrics):
        ax.yaxis.set_major_formatter(_PCT_FMT)
    ax.grid(True, alpha=0.2, axis="y")
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
    if x_col not in df.columns or x_col in metrics_present:
        x_col = 'Week number (ISO)'
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
    if x_col not in df.columns or x_col in metrics_present:
        x_col = 'Week number (ISO)'
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
    if x_col not in df.columns or x_col in metrics:
        x_col = 'Week number (ISO)'
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
    "line":       render_line_chart,
    "bar":        render_bar_chart,
    "stacked_bar": render_stacked_bar_chart,
    "pie":    render_pie_chart,
    "line_bar_combo": render_line_bar_combo_chart,
    "horizontal_bar":   render_horizontal_bar_chart,
    "scatter":          render_scatter_chart,
}

