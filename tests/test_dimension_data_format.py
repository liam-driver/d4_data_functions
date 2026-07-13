"""
Round-trip format tests for the dimension data pipeline.

Verifies that data produced by dimension_cuts.py (formatted strings like
"£1,234.56", "3.45%", "1,234") can be correctly parsed back to floats by
build_dimension_df / _parse_val in generate_visualisation.py, so graph
renderers always receive numeric DataFrames.

No network calls, no matplotlib, no Google Sheets access required.
"""

import sys
import os
import unittest
import types
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub out matplotlib before importing generate_visualisation so the module
# loads without matplotlib being installed in this environment.
def _stub_matplotlib():
    mpl = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    dates = types.ModuleType("matplotlib.dates")
    font_manager = types.ModuleType("matplotlib.font_manager")
    ticker = types.ModuleType("matplotlib.ticker")

    class _FuncFormatter:
        def __init__(self, fn): pass
    ticker.FuncFormatter = _FuncFormatter

    class _FontManager:
        def addfont(self, *a): pass
    font_manager.fontManager = _FontManager()

    for attr in ("subplots", "close", "tight_layout", "rcParams"):
        setattr(pyplot, attr, lambda *a, **kw: None)
    pyplot.rcParams = {}

    for attr in ("DateFormatter",):
        setattr(dates, attr, lambda *a, **kw: None)

    sys.modules["matplotlib"] = mpl
    sys.modules["matplotlib.pyplot"] = pyplot
    sys.modules["matplotlib.dates"] = dates
    sys.modules["matplotlib.font_manager"] = font_manager
    sys.modules["matplotlib.ticker"] = ticker

def _stub_google_deps():
    oauth2client = types.ModuleType("oauth2client")
    svc_acct = types.ModuleType("oauth2client.service_account")
    class _Creds:
        @classmethod
        def from_json_keyfile_name(cls, *a, **kw): return None
    svc_acct.ServiceAccountCredentials = _Creds
    oauth2client.service_account = svc_acct
    sys.modules["oauth2client"] = oauth2client
    sys.modules["oauth2client.service_account"] = svc_acct

    gspread = types.ModuleType("gspread")
    gspread.authorize = lambda *a, **kw: None
    sys.modules["gspread"] = gspread


_stub_matplotlib()
_stub_google_deps()

from monthly_reports.dimension_cuts import _apply_scope_filters
from monthly_reports.generate_visualisation import (
    _parse_val,
    build_dimension_df,
    build_monthly_df,
    _build_df_for_spec,
    _apply_monthly_filters,
)


# ── Synthetic data helpers ─────────────────────────────────────────────────────

def _make_mom_data():
    """Mimics get_dimension_cut output: {dim_val: {metric: {curr, prev, delta, pct}}}."""
    return {
        "Campaign A": {
            "Cost":                 {"curr": "£1,234.56", "prev": "£1,100.00", "delta": "£134.56", "pct": "+12.23%"},
            "Transaction Revenue":  {"curr": "£5,000.00", "prev": "£4,200.00", "delta": "£800.00", "pct": "+19.05%"},
            "Clicks":               {"curr": "1,234",     "prev": "1,100",     "delta": "134",     "pct": "+12.18%"},
            "Impressions":          {"curr": "50,000",    "prev": "45,000",    "delta": "5,000",   "pct": "+11.11%"},
            "Transactions":         {"curr": "50",        "prev": "42",        "delta": "8",       "pct": "+19.05%"},
            "CTR":                  {"curr": "2.47%",     "prev": "2.44%",     "delta": "0.03%",   "pct": "+1.01%"},
            "ROAS":                 {"curr": "405.13%",   "prev": "381.82%",   "delta": "23.31%",  "pct": "+6.11%"},
            "CPA":                  {"curr": "£24.69",    "prev": "£26.19",    "delta": "-£1.50",  "pct": "-5.73%"},
            "Conversion Rate":      {"curr": "4.05%",     "prev": "3.82%",     "delta": "0.23%",   "pct": "+6.11%"},
        },
        "Campaign B": {
            "Cost":                 {"curr": "£800.00",   "prev": "£750.00",   "delta": "£50.00",  "pct": "+6.67%"},
            "Transaction Revenue":  {"curr": "£2,000.00", "prev": "£1,800.00", "delta": "£200.00", "pct": "+11.11%"},
            "Clicks":               {"curr": "800",       "prev": "720",       "delta": "80",      "pct": "+11.11%"},
            "Impressions":          {"curr": "30,000",    "prev": "27,000",    "delta": "3,000",   "pct": "+11.11%"},
            "Transactions":         {"curr": "20",        "prev": "18",        "delta": "2",       "pct": "+11.11%"},
            "CTR":                  {"curr": "2.67%",     "prev": "2.67%",     "delta": "0.00%",   "pct": "+0.00%"},
            "ROAS":                 {"curr": "250.00%",   "prev": "240.00%",   "delta": "10.00%",  "pct": "+4.17%"},
            "CPA":                  {"curr": "£40.00",    "prev": "£41.67",    "delta": "-£1.67",  "pct": "-4.01%"},
            "Conversion Rate":      {"curr": "2.50%",     "prev": "2.50%",     "delta": "0.00%",   "pct": "+0.00%"},
        },
        "Total": {
            "Cost":                 {"curr": "£2,034.56", "prev": "£1,850.00", "delta": "£184.56", "pct": "+9.98%"},
            "Transaction Revenue":  {"curr": "£7,000.00", "prev": "£6,000.00", "delta": "£1,000.00", "pct": "+16.67%"},
            "Clicks":               {"curr": "2,034",     "prev": "1,820",     "delta": "214",     "pct": "+11.76%"},
            "Impressions":          {"curr": "80,000",    "prev": "72,000",    "delta": "8,000",   "pct": "+11.11%"},
            "Transactions":         {"curr": "70",        "prev": "60",        "delta": "10",      "pct": "+16.67%"},
            "CTR":                  {"curr": "2.54%",     "prev": "2.53%",     "delta": "0.01%",   "pct": "+0.61%"},
            "ROAS":                 {"curr": "344.08%",   "prev": "324.32%",   "delta": "19.76%",  "pct": "+6.09%"},
            "CPA":                  {"curr": "£29.07",    "prev": "£30.83",    "delta": "-£1.76",  "pct": "-5.71%"},
            "Conversion Rate":      {"curr": "3.44%",     "prev": "3.30%",     "delta": "0.14%",   "pct": "+4.39%"},
        },
    }


def _make_timeseries_data():
    """Mimics get_dimension_timeseries output: {dim_val: {week_str: {metric: {curr: val}}}}."""
    return {
        "Campaign A": {
            "14": {"Cost": {"curr": "£300.00"}, "Clicks": {"curr": "300"}, "Impressions": {"curr": "12,000"}, "Transactions": {"curr": "12"}, "CTR": {"curr": "2.50%"}, "ROAS": {"curr": "400.00%"}},
            "15": {"Cost": {"curr": "£320.00"}, "Clicks": {"curr": "320"}, "Impressions": {"curr": "13,000"}, "Transactions": {"curr": "14"}, "CTR": {"curr": "2.46%"}, "ROAS": {"curr": "420.00%"}},
            "16": {"Cost": {"curr": "£614.56"}, "Clicks": {"curr": "614"}, "Impressions": {"curr": "25,000"}, "Transactions": {"curr": "24"}, "CTR": {"curr": "2.46%"}, "ROAS": {"curr": "405.00%"}},
        },
        "Campaign B": {
            "14": {"Cost": {"curr": "£200.00"}, "Clicks": {"curr": "200"}, "Impressions": {"curr": "7,500"}, "Transactions": {"curr": "5"}, "CTR": {"curr": "2.67%"}, "ROAS": {"curr": "250.00%"}},
            "15": {"Cost": {"curr": "£210.00"}, "Clicks": {"curr": "210"}, "Impressions": {"curr": "7,800"}, "Transactions": {"curr": "6"}, "CTR": {"curr": "2.69%"}, "ROAS": {"curr": "245.00%"}},
            "16": {"Cost": {"curr": "£390.00"}, "Clicks": {"curr": "390"}, "Impressions": {"curr": "14,700"}, "Transactions": {"curr": "9"}, "CTR": {"curr": "2.65%"}, "ROAS": {"curr": "252.00%"}},
        },
    }


def _make_client_with_dimension_data():
    """Minimal client dict with dimension_data and timeseries_data populated."""
    mom = _make_mom_data()
    ts = _make_timeseries_data()
    return {
        "name": "TEST",
        "dimension_data": {
            # old 2-part key kept so existing tests continue to pass
            "Campaign::Paid Search": {
                "mom": mom,
                "yoy": mom,
                "timeseries": ts,
            },
            # new 3-part keys — channel+platform, channel-only, platform-only
            "Campaign::Google::Paid Search": {
                "mom": mom,
                "yoy": mom,
                "timeseries": ts,
            },
            "Campaign::all::Paid Search": {
                "mom": mom,
                "yoy": mom,
                "timeseries": ts,
            },
            "Campaign::Google::all": {
                "mom": mom,
                "yoy": mom,
                "timeseries": ts,
            },
        },
        "timeseries_data": {
            "Paid Search": {
                "14": {"Cost": {"curr": "£500.00"}, "Clicks": {"curr": "500"}, "CTR": {"curr": "2.50%"}},
                "15": {"Cost": {"curr": "£530.00"}, "Clicks": {"curr": "530"}, "CTR": {"curr": "2.46%"}},
                "16": {"Cost": {"curr": "£1,004.56"}, "Clicks": {"curr": "1,004"}, "CTR": {"curr": "2.46%"}},
            }
        },
    }


METRIC_COLUMNS = ["Cost", "Transaction Revenue", "Clicks", "Impressions", "Transactions", "CTR", "ROAS", "CPA", "Conversion Rate"]


# ── Test: _parse_val ───────────────────────────────────────────────────────────

class TestParseVal(unittest.TestCase):

    def test_gbp_simple(self):
        self.assertAlmostEqual(_parse_val("£1,234.56"), 1234.56)

    def test_gbp_zero(self):
        self.assertAlmostEqual(_parse_val("£0.00"), 0.0)

    def test_gbp_negative_delta(self):
        # Delta values can be "-£1.50" — strip everything except digits and dot
        # Note: "-£1.50" → removes £ → "-1.50" → valid float
        self.assertAlmostEqual(_parse_val("-£1.50"), -1.50)

    def test_pct_positive(self):
        self.assertAlmostEqual(_parse_val("3.45%"), 3.45)

    def test_pct_zero(self):
        self.assertAlmostEqual(_parse_val("0.00%"), 0.0)

    def test_pct_with_plus_sign(self):
        # pct_diff produces "+12.24%" — + is not stripped by _parse_val
        # float("+12.24") is valid Python so this should work
        self.assertAlmostEqual(_parse_val("+12.24%"), 12.24)

    def test_pct_negative(self):
        self.assertAlmostEqual(_parse_val("-5.73%"), -5.73)

    def test_int_with_comma(self):
        self.assertAlmostEqual(_parse_val("1,234"), 1234.0)

    def test_int_no_comma(self):
        self.assertAlmostEqual(_parse_val("50"), 50.0)

    def test_roas_as_pct(self):
        # ROAS is stored as fmt_pct: "405.13%"
        self.assertAlmostEqual(_parse_val("405.13%"), 405.13)

    def test_plain_float_string(self):
        self.assertAlmostEqual(_parse_val("99.9"), 99.9)

    def test_zero_string(self):
        self.assertAlmostEqual(_parse_val("0"), 0.0)

    def test_none_returns_zero(self):
        self.assertAlmostEqual(_parse_val(None), 0.0)

    def test_empty_string_returns_zero(self):
        self.assertAlmostEqual(_parse_val(""), 0.0)

    def test_dash_returns_zero(self):
        # pct_diff returns "-" for None values
        self.assertAlmostEqual(_parse_val("-"), 0.0)


# ── Test: build_dimension_df (mom/yoy) ────────────────────────────────────────

class TestBuildDimensionDfMom(unittest.TestCase):

    def setUp(self):
        self.client = _make_client_with_dimension_data()
        self.df = build_dimension_df(self.client, "Campaign::Paid Search", "mom")

    def test_returns_dataframe(self):
        self.assertIsInstance(self.df, pd.DataFrame)

    def test_not_empty(self):
        self.assertFalse(self.df.empty)

    def test_dimension_column_present(self):
        self.assertIn("Campaign", self.df.columns)

    def test_dimension_values_correct(self):
        campaigns = set(self.df["Campaign"].tolist())
        self.assertIn("Campaign A", campaigns)
        self.assertIn("Campaign B", campaigns)

    def test_summary_rows_dropped(self):
        """'Total' summary rows are dropped so they can't be charted as a dimension value."""
        self.assertNotIn("Total", self.df["Campaign"].tolist())

    def test_metric_columns_present(self):
        for metric in ["Cost", "Clicks", "CTR", "ROAS"]:
            self.assertIn(metric, self.df.columns, f"Missing metric column: {metric}")

    def test_all_metric_columns_numeric(self):
        """No metric column should contain string values — all must be float."""
        for col in self.df.columns:
            if col == "Campaign":
                continue
            self.assertTrue(
                pd.api.types.is_numeric_dtype(self.df[col]),
                f"Column '{col}' is not numeric: dtype={self.df[col].dtype}, sample={self.df[col].tolist()[:3]}"
            )

    def test_cost_value_correct(self):
        row = self.df[self.df["Campaign"] == "Campaign A"].iloc[0]
        self.assertAlmostEqual(row["Cost"], 1234.56, places=1)

    def test_clicks_value_correct(self):
        row = self.df[self.df["Campaign"] == "Campaign A"].iloc[0]
        self.assertAlmostEqual(row["Clicks"], 1234.0, places=0)

    def test_ctr_value_correct(self):
        row = self.df[self.df["Campaign"] == "Campaign A"].iloc[0]
        self.assertAlmostEqual(row["CTR"], 2.47, places=2)

    def test_roas_value_correct(self):
        # ROAS stored as "405.13%" → 405.13
        row = self.df[self.df["Campaign"] == "Campaign A"].iloc[0]
        self.assertAlmostEqual(row["ROAS"], 405.13, places=1)

    def test_no_week_column(self):
        self.assertNotIn("Week number (ISO)", self.df.columns)


class TestBuildDimensionDfYoy(unittest.TestCase):
    """YoY reuses the same structure as MoM — verify routing works."""

    def test_yoy_produces_same_shape_as_mom(self):
        client = _make_client_with_dimension_data()
        df_mom = build_dimension_df(client, "Campaign::Paid Search", "mom")
        df_yoy = build_dimension_df(client, "Campaign::Paid Search", "yoy")
        self.assertEqual(set(df_mom.columns), set(df_yoy.columns))
        self.assertEqual(len(df_mom), len(df_yoy))


# ── Test: build_dimension_df (timeseries) ─────────────────────────────────────

class TestBuildDimensionDfTimeseries(unittest.TestCase):

    def setUp(self):
        self.client = _make_client_with_dimension_data()
        self.df = build_dimension_df(self.client, "Campaign::Paid Search", "timeseries")

    def test_returns_dataframe(self):
        self.assertIsInstance(self.df, pd.DataFrame)

    def test_not_empty(self):
        self.assertFalse(self.df.empty)

    def test_dimension_column_present(self):
        self.assertIn("Campaign", self.df.columns)

    def test_week_column_present(self):
        self.assertIn("Week number (ISO)", self.df.columns)

    def test_week_column_is_int(self):
        self.assertTrue(pd.api.types.is_integer_dtype(self.df["Week number (ISO)"]))

    def test_metric_columns_numeric(self):
        for col in self.df.columns:
            if col in ("Campaign", "Week number (ISO)"):
                continue
            self.assertTrue(
                pd.api.types.is_numeric_dtype(self.df[col]),
                f"Column '{col}' is not numeric: dtype={self.df[col].dtype}"
            )

    def test_sorted_by_week(self):
        weeks = self.df["Week number (ISO)"].tolist()
        # Rows should be sorted ascending by week (sort_values in build_dimension_df)
        # Multiple campaigns per week so we just check each campaign's weeks are monotone
        for campaign in self.df["Campaign"].unique():
            camp_weeks = self.df[self.df["Campaign"] == campaign]["Week number (ISO)"].tolist()
            self.assertEqual(camp_weeks, sorted(camp_weeks))

    def test_correct_number_of_rows(self):
        # 2 campaigns × 3 weeks = 6 rows
        self.assertEqual(len(self.df), 6)

    def test_cost_value_parsed(self):
        row = self.df[(self.df["Campaign"] == "Campaign A") & (self.df["Week number (ISO)"] == 14)].iloc[0]
        self.assertAlmostEqual(row["Cost"], 300.0, places=1)

    def test_impressions_value_with_comma(self):
        row = self.df[(self.df["Campaign"] == "Campaign A") & (self.df["Week number (ISO)"] == 14)].iloc[0]
        self.assertAlmostEqual(row["Impressions"], 12000.0, places=0)

    def test_roas_pct_parsed(self):
        row = self.df[(self.df["Campaign"] == "Campaign A") & (self.df["Week number (ISO)"] == 14)].iloc[0]
        self.assertAlmostEqual(row["ROAS"], 400.0, places=0)


# ── Test: _build_df_for_spec routing ──────────────────────────────────────────

class TestBuildDfForSpec(unittest.TestCase):

    def setUp(self):
        self.client = _make_client_with_dimension_data()

    def test_routes_to_dimension_df_when_data_source_set(self):
        spec = {
            "data_source": "Campaign::Paid Search",
            "dimensions": {"x": "Campaign"},
            "filters": "{}",
        }
        df = _build_df_for_spec(self.client, spec)
        self.assertIn("Campaign", df.columns)
        self.assertNotIn("Ad Channel", df.columns)

    def test_routes_to_timeseries_when_x_is_week(self):
        spec = {
            "data_source": "Campaign::Paid Search",
            "dimensions": {"x": "Week number (ISO)"},
            "filters": "{}",
        }
        df = _build_df_for_spec(self.client, spec)
        self.assertIn("Week number (ISO)", df.columns)

    def test_routes_to_mom_when_x_is_dimension(self):
        spec = {
            "data_source": "Campaign::Paid Search",
            "dimensions": {"x": "Campaign"},
            "filters": "{}",
        }
        df = _build_df_for_spec(self.client, spec)
        self.assertNotIn("Week number (ISO)", df.columns)

    def test_raises_when_no_data_source(self):
        """Specs without a data_source must fail loudly rather than chart the wrong data."""
        spec = {
            "dimensions": {"x": "Ad Channel"},
            "filters": "{}",
        }
        with self.assertRaises(ValueError):
            _build_df_for_spec(self.client, spec)

    def test_filter_applied_to_dimension_df(self):
        spec = {
            "data_source": "Campaign::Paid Search",
            "dimensions": {"x": "Campaign"},
            "filters": '{"Campaign": "Campaign A"}',
        }
        df = _build_df_for_spec(self.client, spec)
        self.assertTrue(all(df["Campaign"].str.contains("Campaign A", case=False, na=False)))
        self.assertNotIn("Campaign B", df["Campaign"].tolist())

    def test_missing_data_source_key_returns_empty_or_df(self):
        """Non-existent data_source returns empty DataFrame without raising."""
        spec = {
            "data_source": "NonExistent::Channel",
            "dimensions": {"x": "Campaign"},
            "filters": "{}",
        }
        df = _build_df_for_spec(self.client, spec)
        self.assertIsInstance(df, pd.DataFrame)


# ── Test: build_monthly_df (baseline) ─────────────────────────────────────────

class TestBuildMonthlyDf(unittest.TestCase):

    def setUp(self):
        self.client = _make_client_with_dimension_data()
        self.df = build_monthly_df(self.client)

    def test_returns_dataframe(self):
        self.assertIsInstance(self.df, pd.DataFrame)

    def test_not_empty(self):
        self.assertFalse(self.df.empty)

    def test_ad_channel_column_present(self):
        self.assertIn("Ad Channel", self.df.columns)

    def test_week_column_present_and_numeric(self):
        self.assertIn("Week number (ISO)", self.df.columns)
        self.assertTrue(pd.api.types.is_integer_dtype(self.df["Week number (ISO)"]))

    def test_cost_numeric(self):
        self.assertTrue(pd.api.types.is_numeric_dtype(self.df["Cost"]))

    def test_all_metrics_numeric(self):
        for col in self.df.columns:
            if col in ("Ad Channel",):
                continue
            self.assertTrue(
                pd.api.types.is_numeric_dtype(self.df[col]),
                f"Column '{col}' is not numeric in baseline df"
            )


# ── Test: _apply_monthly_filters with dimension data ──────────────────────────

class TestApplyMonthlyFilters(unittest.TestCase):

    def setUp(self):
        self.client = _make_client_with_dimension_data()
        self.df = build_dimension_df(self.client, "Campaign::Paid Search", "mom")

    def test_exact_filter(self):
        filtered = _apply_monthly_filters(self.df.copy(), {"Campaign": "Campaign A"})
        self.assertTrue(all(filtered["Campaign"].str.contains("Campaign A", case=False, na=False)))

    def test_partial_match_filter(self):
        filtered = _apply_monthly_filters(self.df.copy(), {"Campaign": "Campaign"})
        # All rows contain "Campaign" so none should be dropped (except Total)
        self.assertFalse(filtered.empty)

    def test_list_filter(self):
        filtered = _apply_monthly_filters(self.df.copy(), {"Campaign": ["Campaign A", "Campaign B"]})
        self.assertIn("Campaign A", filtered["Campaign"].tolist())
        self.assertIn("Campaign B", filtered["Campaign"].tolist())
        self.assertNotIn("Total", filtered["Campaign"].tolist())

    def test_empty_filter_returns_all(self):
        filtered = _apply_monthly_filters(self.df.copy(), {})
        self.assertEqual(len(filtered), len(self.df))

    def test_string_filter_dict(self):
        filtered = _apply_monthly_filters(self.df.copy(), '{"Campaign": "Campaign B"}')
        self.assertFalse(filtered.empty)
        self.assertTrue(all(filtered["Campaign"].str.contains("Campaign B", case=False, na=False)))


# ── Test: 3-part data_source key compatibility with graph renderer ─────────────

class TestThreePartKeyGraphRenderer(unittest.TestCase):
    """Verify the graph renderer handles 3-part dimension data keys correctly."""

    def setUp(self):
        self.client = _make_client_with_dimension_data()

    def test_dimension_col_extracted_from_three_part_key(self):
        # split('::')[0] must still return the dimension column name
        df = build_dimension_df(self.client, "Campaign::Google::Paid Search", "mom")
        self.assertIn("Campaign", df.columns)

    def test_three_part_key_channel_and_platform_returns_data(self):
        df = build_dimension_df(self.client, "Campaign::Google::Paid Search", "mom")
        self.assertFalse(df.empty)

    def test_three_part_key_channel_only_sentinel(self):
        df = build_dimension_df(self.client, "Campaign::all::Paid Search", "mom")
        self.assertIn("Campaign", df.columns)
        self.assertFalse(df.empty)

    def test_three_part_key_platform_only_sentinel(self):
        df = build_dimension_df(self.client, "Campaign::Google::all", "mom")
        self.assertIn("Campaign", df.columns)
        self.assertFalse(df.empty)

    def test_three_part_key_timeseries_dimension_col(self):
        df = build_dimension_df(self.client, "Campaign::Google::Paid Search", "timeseries")
        self.assertIn("Campaign", df.columns)
        self.assertIn("Week number (ISO)", df.columns)

    def test_three_part_key_metrics_numeric(self):
        df = build_dimension_df(self.client, "Campaign::Google::Paid Search", "mom")
        for col in df.columns:
            if col == "Campaign":
                continue
            self.assertTrue(pd.api.types.is_numeric_dtype(df[col]), f"Column '{col}' not numeric")

    def test_spec_routing_with_three_part_data_source(self):
        spec = {
            "data_source": "Campaign::Google::Paid Search",
            "dimensions": {"x": "Week number (ISO)"},
            "filters": "{}",
        }
        df = _build_df_for_spec(self.client, spec)
        self.assertIn("Campaign", df.columns)
        self.assertIn("Week number (ISO)", df.columns)

    def test_spec_routes_to_mom_with_three_part_key(self):
        spec = {
            "data_source": "Campaign::Google::Paid Search",
            "dimensions": {"x": "Campaign"},
            "filters": "{}",
        }
        df = _build_df_for_spec(self.client, spec)
        self.assertIn("Campaign", df.columns)
        self.assertNotIn("Week number (ISO)", df.columns)


# ── Test: _apply_scope_filters ────────────────────────────────────────────────

class TestApplyScopeFilters(unittest.TestCase):
    """Unit tests for dimension_cuts._apply_scope_filters.

    filters is a list of {column, op, value} dicts: same-column filters are
    OR'd together, different columns are AND'd.
    """

    def setUp(self):
        self.df = pd.DataFrame({
            "Ad Channel":  ["Paid Search", "Paid Social", "Shopping", "Paid Search"],
            "Ad Platform": ["Google",      "Meta",        "Google",   "Microsoft"],
            "Cost":        [100.0,          200.0,         50.0,       75.0],
        })

    def _filter(self, filters):
        return _apply_scope_filters(self.df.copy(), filters)

    def test_include_channel(self):
        result = self._filter([{"column": "Ad Channel", "op": "=", "value": ["Paid Search"]}])
        self.assertEqual(len(result), 2)
        self.assertTrue((result["Ad Channel"] == "Paid Search").all())

    def test_exclude_channel(self):
        result = self._filter([{"column": "Ad Channel", "op": "!=", "value": ["Shopping"]}])
        self.assertEqual(len(result), 3)
        self.assertNotIn("Shopping", result["Ad Channel"].tolist())

    def test_include_platform(self):
        result = self._filter([{"column": "Ad Platform", "op": "=", "value": ["Google"]}])
        self.assertEqual(len(result), 2)
        self.assertTrue((result["Ad Platform"] == "Google").all())

    def test_exclude_platform(self):
        result = self._filter([{"column": "Ad Platform", "op": "!=", "value": ["Meta"]}])
        self.assertEqual(len(result), 3)
        self.assertNotIn("Meta", result["Ad Platform"].tolist())

    def test_scalar_value_equals(self):
        result = self._filter([{"column": "Ad Channel", "op": "=", "value": "Shopping"}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Ad Channel"], "Shopping")

    def test_contains(self):
        result = self._filter([{"column": "Ad Channel", "op": "contains", "value": "paid"}])
        self.assertEqual(len(result), 3)
        self.assertNotIn("Shopping", result["Ad Channel"].tolist())

    def test_numeric_comparison(self):
        result = self._filter([{"column": "Cost", "op": ">", "value": 90}])
        self.assertEqual(sorted(result["Cost"].tolist()), [100.0, 200.0])

    def test_none_filter_returns_all_rows(self):
        result = self._filter(None)
        self.assertEqual(len(result), 4)

    def test_empty_filter_list_returns_all_rows(self):
        result = self._filter([])
        self.assertEqual(len(result), 4)

    def test_missing_column_returns_df_unchanged(self):
        result = self._filter([{"column": "Not A Column", "op": "=", "value": ["Google"]}])
        self.assertEqual(len(result), 4)

    def test_same_column_filters_are_ored(self):
        result = self._filter([
            {"column": "Ad Channel", "op": "=", "value": "Paid Social"},
            {"column": "Ad Channel", "op": "=", "value": "Shopping"},
        ])
        self.assertEqual(sorted(result["Ad Channel"].tolist()), ["Paid Social", "Shopping"])

    def test_different_column_filters_are_anded(self):
        result = self._filter([
            {"column": "Ad Channel", "op": "=", "value": ["Paid Search"]},
            {"column": "Ad Platform", "op": "=", "value": ["Google"]},
        ])
        # Paid Search rows: Google + Microsoft → after platform filter → Google only
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Ad Platform"], "Google")
        self.assertEqual(result.iloc[0]["Cost"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
