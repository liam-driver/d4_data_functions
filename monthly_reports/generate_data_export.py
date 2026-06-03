import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from monthly_reports.generate_visualisation import (
    _build_df_for_spec,
    build_comparison_df,
    _apply_monthly_filters,
)

_COMPARISON_GRAPH_TYPES = ('comparison_bar', 'comparison_line')

_MAX_TAB_LEN = 31
_INVALID_SHEET_CHARS = str.maketrans('', '', '\\/?*[]:')


def _build_export_df(client, graph):
    """Return the filtered DataFrame for a trend slide's graph spec.

    Comparison charts get long-format curr+prev rows so both periods are visible.
    All other charts use the same builder as the chart renderer.
    """
    graph_type = graph.get('graph_type', '')
    filters = graph.get('filters', '{}')

    if graph_type in _COMPARISON_GRAPH_TYPES:
        data_source = graph['data_source']
        comparison = graph.get('comparison', 'mom')
        df = build_comparison_df(client, data_source, comparison)
        df = _apply_monthly_filters(df, filters)
    else:
        df = _build_df_for_spec(client, graph)

    # Keep only the columns the chart actually used, plus structural columns.
    metrics = graph.get('metrics', [])
    if metrics:
        structural = [c for c in df.columns if c not in metrics]
        keep = structural + [m for m in metrics if m in df.columns]
        df = df[keep]

    return df


def export_slide_data(client, slide_content, pptx_path):
    """Write an Excel file alongside the PPTX with one tab per trend slide.

    Returns the excel path, or None if no trend slides had exportable data.
    """
    excel_path = pptx_path.replace('.pptx', '_data.xlsx')
    trends = slide_content.get('trends', [])

    sheets = {}
    for i, trend in enumerate(trends):
        graph = trend.get('graph')
        if not graph or not graph.get('data_source'):
            continue

        try:
            df = _build_export_df(client, graph)
        except Exception:
            continue

        if df.empty:
            continue

        title = trend.get('title', f'Slide {i + 1}')
        tab_name = f"{i + 1}. {title}".translate(_INVALID_SHEET_CHARS)[:_MAX_TAB_LEN]
        sheets[tab_name] = df

    if not sheets:
        return None

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for tab_name, df in sheets.items():
            df.to_excel(writer, sheet_name=tab_name, index=False)

    return excel_path
