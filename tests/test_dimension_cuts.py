"""
Tests for monthly_reports/dimension_cuts.py.

Tests use in-memory DataFrames and mock initialise_df so no network calls are made.
"""

import pytest
import pandas as pd
from unittest.mock import patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

CLIENT_BASE = {
    "name": "TEST",
    "account_type": "Ecommerce",
    "dimension": "Ad Channel",
    "start_date": pd.Timestamp("2026-04-01"),
    "end_date":   pd.Timestamp("2026-04-30"),
    "compare_start_date": pd.Timestamp("2026-03-01"),
    "compare_end_date":   pd.Timestamp("2026-03-31"),
}


def _make_funnel_df():
    """Minimal funnel import DataFrame with the columns dimension_cuts cares about."""
    rows = [
        # Current period — Campaign A, Paid Search
        {"Date": pd.Timestamp("2026-04-05"), "Ad Channel": "Paid Search", "Campaign": "Campaign A",
         "Cost (GBP)": 100.0, "Transaction Revenue (GBP)": 500.0, "Impressions": 1000, "Clicks": 50, "Transactions": 5},
        # Current period — Campaign B, Paid Search
        {"Date": pd.Timestamp("2026-04-10"), "Ad Channel": "Paid Search", "Campaign": "Campaign B",
         "Cost (GBP)": 200.0, "Transaction Revenue (GBP)": 300.0, "Impressions": 2000, "Clicks": 80, "Transactions": 3},
        # Current period — Campaign A, Paid Social
        {"Date": pd.Timestamp("2026-04-15"), "Ad Channel": "Paid Social", "Campaign": "Campaign A",
         "Cost (GBP)": 150.0, "Transaction Revenue (GBP)": 200.0, "Impressions": 3000, "Clicks": 60, "Transactions": 2},
        # Previous period — Campaign A, Paid Search
        {"Date": pd.Timestamp("2026-03-10"), "Ad Channel": "Paid Search", "Campaign": "Campaign A",
         "Cost (GBP)": 80.0, "Transaction Revenue (GBP)": 400.0, "Impressions": 900, "Clicks": 45, "Transactions": 4},
        # Previous period — Campaign B, Paid Search
        {"Date": pd.Timestamp("2026-03-20"), "Ad Channel": "Paid Search", "Campaign": "Campaign B",
         "Cost (GBP)": 180.0, "Transaction Revenue (GBP)": 250.0, "Impressions": 1800, "Clicks": 70, "Transactions": 2},
        # Row with empty Campaign — should be excluded by apply_filters (has_dimension check)
        {"Date": pd.Timestamp("2026-04-01"), "Ad Channel": "Paid Search", "Campaign": "",
         "Cost (GBP)": 10.0, "Transaction Revenue (GBP)": 0.0, "Impressions": 100, "Clicks": 5, "Transactions": 0},
    ]
    return pd.DataFrame(rows)


# ── get_dimension_cut tests ───────────────────────────────────────────────────

class TestGetDimensionCut:

    def _call(self, filters=None, client_override=None):
        df = _make_funnel_df()
        client = {**CLIENT_BASE, **(client_override or {})}
        with patch("monthly_reports.dimension_cuts.initialise_df", return_value=df):
            from monthly_reports.dimension_cuts import get_dimension_cut
            return get_dimension_cut(client, "Campaign", filters)

    # (a) MoM date window filtering
    def test_mom_date_window(self):
        """Only rows within start/end and compare_start/compare_end dates are included."""
        result = self._call()
        # Campaign A has data in both periods → should appear with curr and prev values
        assert "Campaign A" in result
        assert result["Campaign A"]["Cost"]["curr"] != "£0.00"
        assert result["Campaign A"]["Cost"]["prev"] != "£0.00"

    def test_total_row_present(self):
        """A 'Total' row is always included in the output."""
        result = self._call()
        assert "Total" in result

    def test_output_shape_matches_paid_data_mom(self):
        """Each entry has curr/prev/delta/pct sub-keys for each metric."""
        result = self._call()
        for _dim_val, metrics in result.items():
            for _metric, values in metrics.items():
                assert "curr" in values
                assert "prev" in values
                assert "delta" in values
                assert "pct" in values

    def test_derived_metrics_present(self):
        """ROAS is computed when both Cost and Transaction Revenue are available."""
        result = self._call()
        assert "ROAS" in result.get("Campaign A", {})

    # (b) Include filter
    def test_include_filter_restricts_channels(self):
        """An '=' scope filter keeps only the specified Ad Channel rows."""
        filters = [{"column": "Ad Channel", "op": "=", "value": ["Paid Search"]}]
        result_include = self._call(filters=filters)
        result_all = self._call()

        # With include filter: Campaign A should show lower cost than unfiltered
        # (Paid Social rows for Campaign A are excluded)
        cost_filtered = float(result_include["Campaign A"]["Cost"]["curr"].replace("£", "").replace(",", ""))
        cost_all = float(result_all["Campaign A"]["Cost"]["curr"].replace("£", "").replace(",", ""))
        assert cost_filtered < cost_all

    # (c) Exclude filter
    def test_exclude_filter_removes_channels(self):
        """A '!=' scope filter drops the specified Ad Channel rows."""
        filters = [{"column": "Ad Channel", "op": "!=", "value": ["Paid Social"]}]
        result_exclude = self._call(filters=filters)
        result_all = self._call()

        cost_excluded = float(result_exclude["Campaign A"]["Cost"]["curr"].replace("£", "").replace(",", ""))
        cost_all = float(result_all["Campaign A"]["Cost"]["curr"].replace("£", "").replace(",", ""))
        assert cost_excluded < cost_all

    def test_include_and_exclude_produce_same_result_when_one_channel(self):
        """Including one channel and excluding all others yields equivalent data."""
        include_filter = [{"column": "Ad Channel", "op": "=", "value": ["Paid Search"]}]
        exclude_filter = [{"column": "Ad Channel", "op": "!=", "value": ["Paid Social"]}]
        result_inc = self._call(filters=include_filter)
        result_exc = self._call(filters=exclude_filter)

        cost_inc = result_inc["Campaign A"]["Cost"]["curr"]
        cost_exc = result_exc["Campaign A"]["Cost"]["curr"]
        assert cost_inc == cost_exc

    # (d) Lead Gen account type
    def test_lead_gen_produces_cpa_not_roas(self):
        """Lead Gen clients get CPA derived metric, not ROAS."""
        df = _make_funnel_df()
        # Add a Conversions column for lead gen
        df["Conversions"] = df["Transactions"]
        client = {**CLIENT_BASE, "account_type": "Lead Gen"}
        with patch("monthly_reports.dimension_cuts.initialise_df", return_value=df):
            from importlib import reload
            import monthly_reports.dimension_cuts as dc
            result = dc.get_dimension_cut(client, "Campaign")

        assert "CPA" in result.get("Campaign A", {})

    def test_raises_when_column_missing(self):
        """A ValueError is raised if the requested dimension column does not exist."""
        df = _make_funnel_df()
        with patch("monthly_reports.dimension_cuts.initialise_df", return_value=df):
            from monthly_reports.dimension_cuts import get_dimension_cut
            with pytest.raises(ValueError, match="not found in sheet"):
                get_dimension_cut(CLIENT_BASE, "NonExistentDimension")

    def test_channel_cut_includes_non_paid_rows(self):
        """Cutting by Channel includes rows with null Ad Channel/Ad Platform (non-paid traffic)."""
        rows = [
            # Non-paid rows — no Ad Channel or Ad Platform
            {"Date": pd.Timestamp("2026-04-05"), "Channel": "Organic Search", "Ad Channel": None, "Ad Platform": None,
             "Cost (GBP)": 0.0, "Transaction Revenue (GBP)": 800.0, "Impressions": 5000, "Clicks": 200, "Transactions": 10},
            {"Date": pd.Timestamp("2026-03-05"), "Channel": "Organic Search", "Ad Channel": None, "Ad Platform": None,
             "Cost (GBP)": 0.0, "Transaction Revenue (GBP)": 700.0, "Impressions": 4500, "Clicks": 180, "Transactions": 9},
            # Paid row alongside
            {"Date": pd.Timestamp("2026-04-10"), "Channel": "Paid Search", "Ad Channel": "Paid Search", "Ad Platform": "Google",
             "Cost (GBP)": 100.0, "Transaction Revenue (GBP)": 500.0, "Impressions": 1000, "Clicks": 50, "Transactions": 5},
        ]
        df = pd.DataFrame(rows)
        with patch("monthly_reports.dimension_cuts.initialise_df", return_value=df):
            from monthly_reports.dimension_cuts import get_dimension_cut
            result = get_dimension_cut(CLIENT_BASE, "Channel")

        assert "Organic Search" in result, "Non-paid Channel rows must not be filtered out"
        assert "Paid Search" in result
