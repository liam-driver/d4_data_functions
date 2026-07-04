# Open Data Cuts to non-paid data

Data Cuts previously hard-filtered every row where both `Ad Channel` and `Ad Platform` were null or empty, effectively restricting breakdowns to paid media rows only. This made it impossible to cut by `Channel` (GA4 session default channel group), which includes organic search, direct, and other non-paid traffic that exists in Funnel Import Data.

We removed the paid filter unconditionally from all three locations where it appeared (`get_dimension_cut()`, `get_dimension_timeseries()`, and the post-aggregation `build_dimension_df()` path). The filter is not needed to protect paid-dimension cuts: `apply_filters()` already gates rows on the primary dimension column being non-empty, so non-paid rows with an empty `Campaign` or `Ad Channel` are excluded by that earlier check. The paid filter was therefore either redundant (for paid dimensions) or actively harmful (for `Channel`).

The alternative was a per-dimension `paid_only` flag in `dimension_config.json`. We rejected it because the data itself provides the boundary — a paid-dimension cut cannot surface non-paid rows through `apply_filters()` — so the flag would add config complexity with no behavioural benefit.

`Channel` has been added to `dimension_config.json` as the first available Dimension for Data Cuts.
