# D4 Weekly Reports

An automated reporting pipeline that generates weekly and monthly paid media performance reports for Door4 clients, using Funnel.io as the ETL layer and BigQuery as the data store.

## Language

### Data pipeline

**Funnel Import Data**:
Time-series paid media performance rows for a client — one row per date/channel combination. The canonical source is BigQuery (`d4_reporting.funnel_data`). Funnel.io writes to it; the report pipeline reads from it.
_Avoid_: "Funnel Import sheet", "the spreadsheet data", "raw data"

**Client**:
A single reporting entity in `config.json`, identified by `name` and `bq_client_name`. One real-world client may have more than one Client entry when they have distinct Lead Gen and Ecommerce conversion streams (see: Harrison's).
_Avoid_: Account, brand

**Account Type**:
The conversion model for a Client — either `'Lead Gen'` or `'Ecommerce'`. Determines which metrics and report templates are used. Stored in `config.json` and as a column in BigQuery.
_Avoid_: Account model, client type

**BQ Client Name**:
The `client_name` value used to filter BigQuery rows for a given Client. For most clients, identical to `name`. For multi-stream clients (e.g. Harrison's), multiple Client entries share the same BQ Client Name and are distinguished by Account Type.
_Avoid_: BigQuery name, table key

**Canonical Metric**:
A metric column name in BigQuery that is consistent across all clients, regardless of how the source platform names it. Funnel.io's transformation layer maps platform-specific names (e.g. `Account Registers`, `Purchases - Google`) to the canonical name (e.g. `conversions`) before export.
_Avoid_: Normalised metric, mapped metric

**Dimension**:
A non-metric grouping column used to break down report data for a client (e.g. `Ad Channel`, `Campaign`, `Website`). The primary breakdown dimension is configured per-client in `config.json`. Extra dimensions (`website`, `department`) exist as nullable columns in BigQuery for clients that need them.

**Data Cut**:
A breakdown of Funnel Import Data by a Dimension for a given date window, used to power a Trend Slide. Produces a comparison table (current vs prior period) and a timeseries. One Data Cut is fetched per Trend Slide via the `fetch_trend_data` MCP tool.
_Avoid_: Dimension cut, dimension slice, breakdown
_Avoid_: Segment, group-by, breakdown

### Slide templates

**Scorecard Slide** (`scorecard_vertical`, `scorecard_horizontal`):
A slide showing metric totals as KPI boxes, each box representing a different metric from the `Total` row of a data source. Used in both the Performance Overview and Top Level Insights (trends) sections.
- **Overview scorecards**: metrics are fixed by account type (Lead Gen: Cost / Conversions / CPA / Conversion Rate; Ecommerce: Cost / Revenue / ROAS / Conversion Rate). Data source is the overall paid totals.
- **Trend scorecards**: metrics are chosen by the user. Data source is a dimension cut's Total row, filtered to the channel or segment of interest. Comparison window (MoM or YoY) is also user-chosen via `graph.comparison`.
_Avoid_: "dimension scorecard", "channel scorecard" — scorecard boxes always represent metrics, not dimension values.

**KPI Box**:
A single coloured box within a Scorecard Slide showing one metric's `curr`, `prev`, and `pct` values for the selected comparison window.
_Avoid_: "stat box", "metric card"

### Report types

**Weekly Report**:
A per-client email report covering the current week vs a comparison period, generated via the MCP tool `fetch_client_data` and sent via `send_weekly_report`.

**Monthly Report**:
A per-client PowerPoint deck covering the previous full calendar month, with MoM, YoY, and MTD comparison passes, generated via `generate_monthly_pptx`. Every run produces two versions: the **Detailed Deck** and the **Presentation Deck**.

**Detailed Deck**:
The pre-meeting version of the Monthly Report, sent to the client before the review session. Slides contain a headline summary (up to one data point) plus 3–6 metric-backed bullets. Filename: `{client}_monthly_{YYYY_MM}.pptx`.

**Presentation Deck**:
The in-room version of the Monthly Report, used by the presenter during the client meeting. Same structure as the Detailed Deck but bullets are narrative-only — no data points — and capped at 3. The headline summary is unchanged. Filename: `{client}_monthly_{YYYY_MM}_presentation.pptx`.
_Avoid_: "clean version", "presenter copy", "lite deck"

**Traps & Tripwires**:
An automated health-check report that runs budget pacing, conversion tracking, and platform-specific checks across all clients, delivered to Slack.

### Comparison windows

**MoM (Month-on-Month)**:
Current period compared against the same date range one month prior.

**YoY (Year-on-Year)**:
Current period compared against the same date range one year prior.

**MTD (Month-to-Date)**:
Current month from the 1st to two days ago, compared against the same days in the prior year.

**Templated Date Range**:
One of the preset date windows the report pipeline can compute automatically: `previous_7_days`, `mtd`, `previous_month`, `ytd`, `last_90_days`. Used as shorthand when invoking Data Cuts or the standard monthly fetch.
_Avoid_: preset range, default range

**Custom Date Window**:
An explicit start and end date specified at runtime, used in place of a Templated Date Range. For overview slides, both a same-length prior-period comparison and a YoY comparison are always fetched. For Data Cuts, it is passed directly to `fetch_trend_data` alongside the dimension.
_Avoid_: custom range, bespoke dates, ad-hoc dates

**Run Rate**:
A projected end-of-month spend figure extrapolated from actual spend to date. Used in both weekly reports and Traps & Tripwires budget pacing checks.

## Relationships

- **Funnel.io** ingests from ad platforms → transforms → writes **Funnel Import Data** to BigQuery
- A **Client** has exactly one **Account Type** and one **BQ Client Name**
- Multiple **Clients** may share a **BQ Client Name** when a real-world client has both Lead Gen and Ecommerce streams
- A **Client** has one primary **Dimension** and zero or more extra nullable Dimensions
- **Canonical Metrics** are enforced by Funnel.io's transformation layer — the Python codebase never references source-platform metric names
- **Weekly Reports** and **Monthly Reports** both read **Funnel Import Data** via the same `initialise_df()` → BigQuery query path

## Example dialogue

> **Dev:** "Why does Harrison's appear twice in the config?"
> **Domain expert:** "Harrison's has both a Lead Gen stream (account registers) and an Ecommerce stream. They share the same BQ Client Name but have different Account Types. Each generates a separate report."

> **Dev:** "What's the `conversions` column in BigQuery for a client like Paintnuts?"
> **Domain expert:** "It's the Canonical Metric — Funnel.io maps whatever that client calls their primary conversion event into `conversions` before the data lands in BigQuery. We never see the platform-specific name in the codebase."

## Planning & Scheduling

**90-Day Plan**:
A per-client Google Sheet tracking all PPC delivery tasks across a 90-day window. Each row is a task; columns from week 1 onward contain the planned hours for that task in that week. The first sheet tab is the current plan (`plan_status: "current"`); older tabs are historical.
_Avoid_: quarterly plan, sprint plan

**Plan Schedule**:
The per-week hour allocations embedded in the 90-day plan Google Sheet. Column headers are Monday dates; cell values are planned hours (e.g. 0.5, 1, 2). This is the authoritative source for Scoro time entry durations — no hours are inferred or defaulted.
_Avoid_: weekly hours, allocation grid

**BAU Task (Scoro)**:
A single consolidated Scoro task aggregating all plan rows where `category == "BAU"` for a given client. Named `{Client}: PPC: BAU`. Time entry durations are the sum of all BAU-category hours for each week. One BAU task exists per client per 90-day plan; subsequent monthly imports add time entries to the same task.
_Avoid_: BAU bundle, ongoing task

**Workstream Task (Scoro)**:
A Scoro task corresponding to a single `Active Workstream` or `Reporting` plan row. Named `{Client}: PPC: {task name}`. Covers the full lifespan of the workstream; monthly imports add that month's time entries to the existing task rather than creating a new one.
_Avoid_: project task, delivery task

**Monthly Import**:
A Claude skill (`ppc-90day-import`) run in the final week of the preceding month. Reads the current 90-day plan, identifies tasks active in the upcoming calendar month, creates any missing Scoro tasks, and schedules time entries for that month's weeks only. Nothing is written to Scoro until the user confirms the draft.

**Weekly Check**:
A Claude skill (`ppc-90day-check`) that compares the current 90-day plan against live Scoro tasks and time entries. Surfaces gaps — missing tasks, missing time entries, status mismatches, stale entries — and resolves them conversationally with the user before writing any changes.

## Flagged ambiguities

- "client" was used to mean both the real-world business and a config entry — resolved: **Client** always means the config entry. A real-world business may map to more than one Client.
- `Cost (*)` in legacy Sheets exports — the asterisk was a Funnel.io annotation. The canonical BigQuery column name is `cost` (no asterisk).
- Column 11 (`df.iloc[:,11]`) in legacy code refers to `cost` — this positional access is eliminated as part of the BigQuery migration (see ADR 0006).
