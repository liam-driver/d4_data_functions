# ADR 0006 — BigQuery as the Funnel Data Store

**Status:** Superseded by ADR 0007  
**Date:** 2026-06-19  
**Superseded:** 2026-06-22 — BigQuery rejected due to cost. Google Sheets retained as data store. Schema consistency and split-client fixes implemented within Sheets instead (see ADR 0007).

## Context

The weekly and monthly report pipeline reads performance data from a Google Sheets spreadsheet called `Weekly Reports`. Each client has a dedicated `{client} Funnel Import` worksheet populated by Funnel.io (ETL) via its Sheets export connector. With 13 clients and growing historical data, the pipeline is hitting Google Sheets cell limits (10M cells per spreadsheet).

Two additional architectural problems were identified during this migration:

1. **Positional column access.** `traps_and_tripwires/main.py` reads the cost metric as `df.iloc[:,11]` — fragile against any reordering of columns in the Funnel.io export.
2. **Split client hack.** Harrison's has both Lead Gen (account registers) and Ecommerce conversion streams. Because the schema couldn't represent both in one worksheet, Harrison's is split into two separate Funnel Import worksheets and two separate config entries, forcing the codebase to treat one real client as two.

## Decision

Move the Funnel Import data from Google Sheets to **Google BigQuery**, with Funnel.io's native BQ connector as the export target. The rest of the stack — Funnel.io ingestion, transformation, and all other Sheets (Config, Plans, T&T Budgets) — is unchanged in this phase.

**Single consolidated table:** `d4_reporting.funnel_data`, one row per date/client/channel combination, all clients in one table. Multi-tenancy is expressed via `client_name` and `account_type` columns.

**Canonical schema:**

| Column | Type | Notes |
|---|---|---|
| `client_name` | STRING | Maps to `bq_client_name` in config.json |
| `account_type` | STRING | `'Lead Gen'` or `'Ecommerce'` |
| `date` | DATE | |
| `week_number_iso` | INTEGER | |
| `month` | INTEGER | |
| `year` | INTEGER | |
| `ad_platform` | STRING | |
| `ad_channel` | STRING | |
| `channel` | STRING | |
| `campaign` | STRING | |
| `sessions` | FLOAT | |
| `impressions` | INTEGER | |
| `clicks` | INTEGER | |
| `cost` | FLOAT | Was `Cost (*)` in Sheets — asterisk removed |
| `conversions` | FLOAT | Normalised by Funnel.io from all client-specific names (e.g. `Account Registers`, `Purchases - Google`) |
| `transactions` | INTEGER | Ecomm only, nullable |
| `transaction_revenue` | FLOAT | Ecomm only, nullable |
| `search_impression_share` | FLOAT | |
| `total_eligible_impression_share` | FLOAT | |
| `total_absolute_top_impression_share` | FLOAT | |
| `views` | INTEGER | |
| `hooks` | INTEGER | |
| `holds` | INTEGER | |
| `website` | STRING | Nullable — Paintnuts only |
| `department` | STRING | Nullable — Forbes only |

Table is **partitioned by `date`** and **clustered by `client_name`, `account_type`** for query cost and performance.

**Harrison's fix:** Both Harrison's config entries (`Harrisons Lead Gen`, `Harrisons Ecomm`) set `bq_client_name: "Harrisons"` and are distinguished by their existing `account_type` field. The BQ query filters on both. Two separate reports are still generated — one per branch. The two Funnel Import worksheets in Sheets become redundant and are not migrated.

**Metric normalisation:** All per-client conversion metric name variations are mapped to the canonical `conversions` column inside Funnel.io's transformation layer before export. The Python codebase never references client-specific metric names.

**Positional access fix:** All `df.iloc[:,N]` references are replaced with named column access (e.g. `df['cost']`) as part of the `initialise_df()` rewrite.

**Infrastructure:** New GCP project under the Door4 Google account. New service account with `BigQuery Data Editor` and `BigQuery Job User` IAM roles. Credentials stored in `storage/secrets.json` replacing the personal account credentials.

**Historical data:** Funnel.io backfills all historical data into BQ before cutover. No Sheets-to-BQ migration script required. Cutover is a hard switch — no parallel read period.

## Alternatives considered

**One table per client** — mirrors the existing Sheets structure. Rejected because it grows with client count, makes cross-client queries painful, and requires one Funnel.io export definition per client.

**PostgreSQL (self-hosted or managed)** — standard relational option. Rejected because it requires infrastructure management that the team (no dedicated data engineer) cannot sustain. BigQuery is serverless and scales without ops overhead.

**Keep Sheets, increase capacity** — not viable. Google Sheets has a hard 10M cell limit per spreadsheet with no upgrade path.

## Consequences

- `core/get_funnel_data.py` `initialise_df()` becomes a parameterised BigQuery query via `google-cloud-bigquery`. The `gspread` dependency is removed from the funnel data read path.
- `weekly_reports/get_context_data.py` updated to use the same BQ read path.
- `config.json` gains a `bq_client_name` field on every client entry.
- Funnel.io export must be reconfigured to target BQ and must include `client_name` and `account_type` as columns, with all conversion metrics normalised to `conversions`.
- The Google Sheets `{client} Funnel Import` worksheets become read-only historical archives and are no longer part of the live pipeline.
- Connected Sheets (Google Workspace) can be used to surface BQ data back into Sheets for internal use, keeping BigQuery as the single source of truth.
