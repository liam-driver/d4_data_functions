# D4 Weekly Reports

An automated reporting pipeline that generates weekly and monthly paid media performance reports for Door4 clients, using Funnel.io as the ETL layer and Google Sheets as the data store.

## Language

### Data pipeline

**Funnel Import Data**:
Time-series performance rows for a client — one row per date/channel combination, covering both paid and organic channels. Stored in a Google Sheet called `'Weekly Reports'`, one tab per client named `"{client_name} Funnel Import"`. Funnel.io populates these tabs; the report pipeline reads them via gspread.
_Avoid_: "raw data"

**Client**:
A single reporting entity in `config.json`, identified by `name`. The `name` must exactly match the Google Sheet tab name used to find Funnel Import Data (i.e. the worksheet `"{name} Funnel Import"` must exist). One real-world client may have more than one Client entry when they have distinct Lead Gen and Ecommerce conversion streams (see: Harrison's).
_Avoid_: Account, brand

**Account Type**:
The conversion model for a Client — either `'Lead Gen'` or `'Ecommerce'`. Determines which metrics and report templates are used. Stored in `config.json`.
_Avoid_: Account model, client type

**Report Style**:
Which Commentary Rules sub-section the `ppc-weekly-report` skill applies when writing a Weekly Report for a Client — currently only `'standard'` exists. Hard-coded per client in a `REPORT_STYLES` dict in `scripts/generate_client_contexts.py`, the same pattern used for `PROJECT_GROUPS`, because `config.json` is fully overwritten from the Config sheet on every `get_config.py` run and cannot hold hand-added fields. Emitted into the `client_config` JSON block in the Client Context File; the skill reads it from there like `account_type` or `dimension`. Not present in `config.json`. See `docs/adr/0013-report-style-branching-in-weekly-skill.md`.
_Avoid_: report type, commentary style

**Canonical Metric**:
A metric column name in the Funnel Import Data that is consistent across all clients, regardless of how the source platform names it. Funnel.io's transformation layer maps platform-specific names (e.g. `Account Registers`, `Purchases - Google`) to the canonical name (e.g. `conversions`) before writing to the sheet.
_Avoid_: Normalised metric, mapped metric

**Dimension**:
A non-metric grouping column used to break down report data for a client (e.g. `Channel`, `Ad Channel`, `Campaign`, `Website`, `Campaign Group: Brand`). The primary breakdown dimension is configured per-client in `config.json`. `Channel` (GA4 session default channel group) is a non-paid Dimension covering organic, direct, and paid traffic together. `Campaign Group: Brand` (`'Branded'` / `'Non-Branded'`) is only populated for Google Ads and Microsoft Ads rows — used by the Traps & Tripwires Brand Spend Split check.

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

**Organic Overview**:
A scorecard slide covering Organic Search performance from `overall_data` (GA4), filtered to the `"Organic Search"` Channel row. Metrics: Sessions, Conversions (Lead Gen) or Transaction Revenue (Ecommerce), and Conversion Rate. Rendered inside the **SEO** team section (gold divider labelled "Organic SEO"), alongside the SEO team's Gantt.
_Avoid_: "SEO Overview", "organic traffic slide" — the slide type is always "Organic Overview" (it's GA4 organic-search data, not SEO deliverables), even though it lives inside the section labelled "Organic SEO". Do not use "Organic Overview" and "SEO" interchangeably as slide names — "SEO" is the correct name for the containing team only.

**CRO Overview**:
A scorecard slide covering site-wide conversion performance from `overall_data` (GA4), using the `"Total"` Channel row. Metrics: Sessions, Conversion Rate, and AOV (Ecommerce only). Rendered inside the **CRO** team section (gold divider labelled "CRO UX"). Included per-run when requested.
_Avoid_: conversion slide, site-wide overview

### Report types

**Weekly Report**:
A per-client email report covering the current week vs a comparison period, generated via the MCP tool `fetch_client_data` and sent via `send_weekly_report`.

**Monthly Report**:
A per-client PowerPoint deck covering the previous full calendar month, with MoM, YoY, and MTD comparison passes, built in two phases by two skills — see **Monthly Report Skeleton** and **Monthly Report Insights**. Every final run produces two versions: the **Detailed Deck** and the **Presentation Deck**.

**Detailed Deck**:
The pre-meeting version of the Monthly Report, sent to the client before the review session. Slides contain a headline summary (up to one data point) plus 3–6 metric-backed bullets. Filename: `{client}_monthly_{YYYY_MM}.pptx`.

**Presentation Deck**:
The in-room version of the Monthly Report, used by the presenter during the client meeting. Same structure as the Detailed Deck but bullets are narrative-only — no data points — and capped at 3. The headline summary is unchanged. Filename: `{client}_monthly_{YYYY_MM}_presentation.pptx`.
_Avoid_: "clean version", "presenter copy", "lite deck"

**Team**:
One of the three delivery groups covered by the Monthly Report: **PPC**, **SEO**, **CRO**. Each Team has its own 90-Day Plan (see PPC/SEO/CRO 90-Day Plan), its own Gantt, and its own Overview scorecard slide. A client may have any subset of the three Teams active, detected from which plan URLs are present in their Client Context File. Each Team's section opens with a gold section separator: "Paid Media" (PPC), "Organic SEO" (SEO), "CRO UX" (CRO).
_Avoid_: "vertical", "workstream" (Workstream already means something narrower — a category of plan task)

**Monthly Report Skeleton**:
The first phase of building a Monthly Report, run by the **Client Services** team via the `d4-monthly-skeleton` skill. Produces the deck's structural sections for every active Team — a section separator, Overview scorecard(s), and Gantt — with real LLM-written overview commentary, but no Top Level Trends. Calls `generate_skeleton_pptx`, which renders a real draft PPTX (both Detailed and Presentation variants) for review and persists the confirmed content to `storage/{client}_skeleton_content.json` as the checkpoint the Insights phase builds on.
_Avoid_: "skeleton report", "draft deck" on its own (always qualify as "the skeleton draft")

**Monthly Report Insights**:
The second phase of building a Monthly Report, run via the `ppc-monthly-report-insights` skill. Works slide-by-slide through PPC trend topics (see Data Cut) exactly as the old `ppc-monthly-report` skill's Phase 2–4 did, then calls `generate_monthly_pptx` with only the confirmed `trends`. The server loads the cached **Monthly Report Skeleton** checkpoint, slots the trends into the PPC Team's section, and renders the final Detailed and Presentation Decks. Requires the Skeleton phase to have already run for that client this month — there is no flat, single-call path anymore.

**Client Services**:
The team that owns the Monthly Report Skeleton phase — confirms which Teams are active, which comparison windows to use, and reviews the structural draft deck before Insights adds PPC trend slides. Distinct from the performance marketers who run Insights.

**Traps & Tripwires**:
An automated health-check report that runs budget pacing, conversion tracking, and platform-specific checks across all clients, delivered to Slack.

**Merge Group**:
A set of `config.json` rows (Clients) that represent one real-world account split across multiple conversion streams — e.g. Harrisons Direct (Registrations/Revenue), Revival Beds (Transactions/Showroom Visits) — collapsed into a single Traps & Tripwires Slack message instead of one per row. Defined by the hard-coded `MERGE_GROUPS` dict in `traps_and_tripwires/main.py` (same reasoning as `PROJECT_GROUPS`/`REPORT_STYLES`: `config.json` is regenerated from the Config sheet every run and can't hold hand-added grouping fields). `merge_grouped_clients()` takes the account-level checks (Budget Pacing, Campaign Spend, Brand Spend Split) from whichever member ran first — identical across a group's members since they share one ad account — and keeps Conversion Tracking per member, relabeled with that member's parenthetical suffix. Not every pair of Clients sharing a `slack_channel_id` is a Merge Group — MacFarlane UK/IE, Paintnuts/Paintnuts Trade, and Aspray/Major Loss share a channel by convenience but are genuinely separate accounts (different `plan`/`dashboard`/`budget`) and are deliberately not merged. See `docs/adr/0015-tt-merge-groups-slack-layer-only.md`.
_Avoid_: split client (that's the config.json-level concept — see **Client** — a Merge Group is the T&T Slack-reporting response to it)

**Bespoke Check**:
A Traps & Tripwires check written for exactly one Client rather than the shared checks every Client gets. Gated by `client['name']`, since neither `config.json` nor the Client Context File carry per-client feature toggles. Two wiring shapes exist, chosen by how much the check needs to render:
- A single check that fits the standard `(status, detail)` shape and belongs alongside a Client's normal checks is added inline to `run_checks()` in `main.py`, gated by name — e.g. Empress Mills' **ROAS Volatility** check, which also extends its result to `(status, detail, direction)` so `build_client_block` can pick a 📈/📉 emoji instead of the standard pass/warn/fail emoji (this check is informational only and never fails or warns).
- A check that expands into several rows per Client instead lives in its own module and posts as a separate Slack sub-thread — e.g. Forbes' per-department budget pacing (`forbes.py`).
_Avoid_: client-specific check, custom check

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

**Standard Report Style**:
The only **Report Style** in use as of this writing. Redesigns the `ppc-weekly-report` Commentary Rules in response to client feedback that commentary was too metric-heavy and the WIP section just restated the 90-Day Plan verbatim. Changes from the prior (now fully replaced, no fallback) rules:
- **WIP**: keeps the per-task list structure, but each task's summary is enriched with any matching **WOL Message** or Slack context for that task, not just a one-sentence rewrite of `desc`.
- **Insights**: hard cap of 3 points (was 4-10), no longer forced into a per-channel `<Ad Channel> <Metric Group> <Direction>` template. Each point may be a channel/metric movement, a general cross-account trend the client wouldn't normally spot, or the measurable impact of a completed plan action, competing freely for the 3 slots rather than a fixed quota per type. Qualifies via the existing single-period % thresholds OR a sustained multi-period direction in `timeseries_data` (3+ consecutive periods same direction), to catch slow-burn trends a single mom/yoy comparison misses. Still never sourced standalone from `overall_data`, that restriction is unchanged.
- **performance_overview / ninety_day_overview**: still evidence-based, but no longer required to pack mom + yoy + goal comparison + spend into one tight paragraph. One clear headline figure per paragraph, framed in plain language.
- **KPIs / Cost**: unchanged, these are compact reference blocks (not narrative commentary) and the client's own feedback draws a line between wanting human interpretation in the commentary and being fine with dashboards/reference data existing.
- **Step 6 (shorten and confirm)**: skipped entirely, the Step 4 draft is already short; goes straight to Step 7 once approved.

See `docs/adr/0013-report-style-branching-in-weekly-skill.md`.

**WOL Message (Work Out Loud)**:
A Slack message the account manager posts while actively working, giving a live progress update tied to a specific 90-Day Plan task. Not a separate system or data source, it is a subset of `slack_context` (see **Client Context File** / Weekly Report Step 2), distinguished by intent rather than any tag or field. Used to synthesise real plan movement in the Weekly Report **WIP** section, rather than restating the plan row as-is.
_Avoid_: "work order log", "WOL log" — there is no separate log; WOL messages live in the same Slack channel and are fetched the same way as any other Slack context.

## Relationships

- **Funnel.io** ingests from ad platforms → transforms → writes **Funnel Import Data** to a Google Sheet tab per client (`"{name} Funnel Import"` in the `'Weekly Reports'` spreadsheet)
- A **Client** has exactly one **Account Type** and one primary **Dimension**
- Multiple **Clients** may share a Funnel Import tab when a real-world client has both Lead Gen and Ecommerce streams (e.g. Harrison's — two config entries, one shared sheet tab)
- **Canonical Metrics** are enforced by Funnel.io's transformation layer — the Python codebase never references source-platform metric names
- **Weekly Reports** and **Monthly Reports** both read **Funnel Import Data** via the same `initialise_df()` → gspread path
- **`config.json`** is the authoritative config for **Traps & Tripwires only** — all skill-triggered workflows (weekly reports, monthly reports, plan tools) get their config from the **Client Context File** via Claude at runtime
- **Client Context Files** are generated from `config.json` via `scripts/generate_client_contexts.py` and uploaded to each client's Claude Enterprise project; regenerate and re-upload after any config change
- A **Client** has at most one **Scoro Project ID**, shared across all three **Teams** — not one per Team
- `ppc-90day-import` and `ppc-90day-check` read all shared client config from the **90-Day Plan Context Doc**, not from `config.json` or the per-client **Client Context File**

## Example dialogue

> **Dev:** "Why does Harrison's appear twice in the config?"
> **Domain expert:** "Harrison's has both a Lead Gen stream (account registers) and an Ecommerce stream. They share the same Funnel Import tab but have different Account Types. Each generates a separate report."

> **Dev:** "What's the `conversions` column in the Funnel Import sheet for a client like Paintnuts?"
> **Domain expert:** "It's the Canonical Metric — Funnel.io maps whatever that client calls their primary conversion event into `conversions` before writing to the sheet. We never see the platform-specific name in the codebase."

## Planning & Scheduling

**Client Context File**:
A per-project markdown file in `storage/client_contexts/` (e.g. `falkn.md`), added to each client's Claude Enterprise project — uploaded as its own knowledge file or pasted as a section of the project's knowledge doc. Contains only the operational config that skills need at runtime: `account_type`, `dimension`, `comparison_dates`, `report_due_date`, `slack_channel_id`, budgets, plan sheet URLs, a `## Scoro` block (see **Scoro Project ID**), and a ready-to-pass `client_config` JSON block. Where one Claude project covers multiple data-function clients (e.g. Nuts Group → Paintnuts + Paintnuts Trade; mapping lives in `PROJECT_GROUPS` in the generator, not in `config.json`, because `get_config.py` regenerates `config.json` from the sheet), the file contains one block per client. Prose context (strategy, KPIs, seasonality, history) is deliberately not included — the team-maintained project knowledge doc is authoritative for narrative content. When a skill runs, Claude reads this file from its project knowledge and passes the matching JSON block to MCP tools verbatim — the tools do not read `config.json` themselves (except Traps & Tripwires). Generated from `config.json` via `scripts/generate_client_contexts.py`; re-upload to the Claude project after regenerating.
_Avoid_: client config file, context doc

**Scoro Project ID**:
The Scoro `projectId` for a Client, shared across all three Teams (PPC/SEO/CRO) rather than one per Team — one Client has exactly one Scoro project. Stored in the Client Context File's `Scoro:` block (alongside `Responsible User ID`, `Weekly Report Day`, `Active Work Day`), generated from `SCORO_CONFIG` in `scripts/generate_client_contexts.py`. Read by `d4-monthly-skeleton` only. `ppc-90day-import` and `ppc-90day-check` are a separate operational context (live Scoro task/time-entry writes, not report generation) and deliberately keep their own independent Client→projectId table in the **90-Day Plan Context Doc** — this is a second, intentionally separate source for the same value, not drift to fix. If absent for a Client in the Client Context File, Scoro-dependent content (Delivery Recap/Forecast, Scoro-informed commentary) is skipped gracefully with a note, the same pattern used when GA4 Organic Search data is missing for an SEO Overview.
_Avoid_: Scoro config, project mapping

**90-Day Plan Context Doc**:
A Google Doc (`ppc-90day-context`, mirrored in this repo at `.claude/enterprise/ppc-90day-context.txt` as a plain-text, copy-paste-ready reference) holding the shared config `ppc-90day-import` and `ppc-90day-check` need: the Scoro Config table (`projectId`, `responsibleUserId`, `weeklyReportDay`, `activeWorkDay` per client), the Plan Links table (90-day plan sheet URLs per client), and the Bank Holidays table. Both skills run in the shared Scoro Claude Enterprise project and have no access to per-client Claude project knowledge, so this Doc — not `config.json`, not the per-client **Client Context File** — is their only source for these fields. Read live via the Google Drive connector at the start of each skill run, not uploaded as a static knowledge file. Hand-maintained directly in the Doc; unlike the Client Context File, there is no generator script — the repo `.txt` mirror is a manually-updated reference copy, not a build artifact. Supersedes the earlier `ppc-90day-plans.md`/`.txt` (plan URLs only, embedded Scoro config duplicated separately in both skill files).
_Avoid_: plan links doc, Scoro config table (ambiguous once these tables moved into one Doc — always say "90-Day Plan Context Doc")

**PPC 90-Day Plan**:
A per-client Google Sheet tracking all PPC delivery tasks across a 90-day window. Each row is a task; columns from week 1 onward contain the planned hours for that task in that week. The first sheet tab is the current plan (`plan_status: "current"`); older tabs are historical. Sheet URL stored in the Client Context File under `## Plans`. Claude passes it to `fetch_plan_data` as a `sheet_url` parameter at runtime.
_Avoid_: quarterly plan, sprint plan, 90-day plan (ambiguous — always prefix with team)

**CRO 90-Day Plan**:
A per-client Google Sheet tracking all CRO delivery tasks across a 90-day window. Same tab/status structure as the PPC plan. Columns are parsed by header name (not position) because the column count varies across clients. Per-week hour allocations follow the same Monday-date header convention. Sheet URL stored in the Client Context File under `## Plans`. Claude passes it to `fetch_cro_plan_data` as a `sheet_url` parameter at runtime.
Task schema: `name`, `idea`, `hypothesis`, `objective`, `workstream` (→ rendered as `platform` on the Gantt), `facs`, `test_or_jdi`, `category` (`"Active Workstream"` or `"BAU"`), `status`, `start_date`, `end_date`, `schedule`. RICE fields (`reach`, `impact`, `confidence`, `effort`, `score`) are included when present in the sheet.
_Avoid_: quarterly plan, sprint plan

**SEO 90-Day Plan**:
A per-client Google Sheet tracking SEO delivery tasks, typically covering a 12-month rolling window. Unlike PPC/CRO plans, there are no explicit `Start Date`, `End Date`, or `Status` columns, and cells contain no hour allocations. Active periods are indicated by cell background colour `#fff2cc`; start and end dates are inferred from the first and last coloured cell per task row. Status is inferred from today's date: future → `"Scheduled"`, overlapping today → `"In Progress"`, past → `"Complete"`. Section headers (Tech, Content, Hygiene, Dev Briefs, Indexability, Optimisations, Planning) act as the `platform` grouping on the Gantt slide. All tasks are treated as `"Active Workstream"` for Gantt filtering. Sheet URL stored in the Client Context File under `## Plans`. Claude passes it to `fetch_seo_plan_data` as a `sheet_url` parameter at runtime. The tool uses `fetch_sheet_metadata(params={"includeGridData": "true"})` to read cell background colours.
Task schema: `name`, `desc`, `category` (always `"Active Workstream"`), `status` (inferred), `start_date`, `end_date`, `platform` (section header).
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

**Delivery Recap**:
A narrative slide in the Monthly Report Skeleton ("What We've Done"), one per active Team, rendered from the `delivery.done` block in the Teams Content JSON Schema — positioned before that Team's Overview(s). LLM-written headline title; subtitle is always fixed to "Last month's actions" and every bullet gets a ✅ appended by the renderer, not the LLM. Bullets are synthesised from Scoro time entries logged in the reported month under the Client's Scoro project — all logged work is included and blended together without distinguishing plan-matched tasks from ad hoc work. Fetched read-only via direct Scoro MCP calls in `d4-monthly-skeleton` (`get_tasks` filtered by **Scoro Project ID**, then `get_time_entries` per task, filtered to the reported month client-side). Does not modify the Gantt, which remains rendered from unmodified `plan_json` with no LLM text.
_Avoid_: delivery summary, WIP (WIP already means something narrower in the Weekly Report's Standard Report Style)

**Delivery Forecast**:
A narrative slide in the Monthly Report Skeleton ("What We're Going To Do"), one per active Team, rendered from the `delivery.next` block in the Teams Content JSON Schema — positioned directly before that Team's Gantt. Title and subtitle are always fixed ("What's next?" / "Next priority actions") regardless of input, since there's no story yet to headline. LLM-written bullets are synthesised from the 90-day plan's schedule for the upcoming calendar month — reuses the `plan_json` already fetched for the Gantt, no separate fetch required.

## Flagged ambiguities

- "client" was used to mean both the real-world business and a config entry — resolved: **Client** always means the config entry. A real-world business may map to more than one Client.
- `Cost (*)` in legacy Sheets exports — the asterisk was a Funnel.io annotation. The canonical column name in Funnel Import Data is `cost` (no asterisk).
- Column 11 (`df.iloc[:,11]`) in legacy T&T code refers to `cost` — this positional access is a known tech debt item, not yet eliminated.
