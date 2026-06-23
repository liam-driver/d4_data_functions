# ADR 0007 — Sheets Schema Consistency and Split-Client Merge

**Status:** Accepted  
**Date:** 2026-06-22

## Context

ADR 0006 proposed migrating Funnel Import data to BigQuery. This was rejected due to cost. Google Sheets is retained as the data store; Funnel.io's export volume has been limited to stay within Sheets cell limits.

Two architectural problems identified during the BigQuery scoping remain worth fixing within the Sheets paradigm:

1. **Schema inconsistency.** Conversion metric column names vary per client (e.g. `Account Registers`, `Purchases - Google`, `Conversions`). The codebase works around this via positional column access (`df.iloc[:,11]`), which is fragile against any reordering of columns in a Funnel.io export.

2. **Split-client hack.** Clients with both Lead Gen and Ecommerce conversion streams (e.g. Harrison's) are represented as two separate Funnel Import worksheets and two separate `config.json` entries, forcing the codebase to treat one real-world client as two unrelated clients.

## Decision

**Schema consistency:** Funnel.io's transformation layer is updated to output a canonical, fixed column schema for all clients. All conversion metric variants are mapped to a single canonical name (`Conversions`) before export. Column order is frozen. All positional `df.iloc[:,N]` access in the Python codebase is replaced with named column access.

**Split-client merge:** Clients with mixed account types get a single combined `{name} Funnel Import` worksheet containing an `Account Type` column (`'Lead Gen'` or `'Ecommerce'`). Funnel.io writes both streams into this one worksheet. The Python `initialise_df()` function accepts an optional `account_type` filter and applies it when the client config specifies one. Two config entries can still share the same worksheet name (`sheet_name` field in config) and be distinguished by `account_type`.

## Canonical column schema

Fixed order for all Funnel Import worksheets:

| Column | Notes |
|---|---|
| `Date` | |
| `Week number (ISO)` | |
| `Month` | |
| `Year` | |
| `Ad Platform` | |
| `Ad Channel` | |
| `Channel` | |
| `Campaign` | |
| `Account Type` | `'Lead Gen'` or `'Ecommerce'` — new column, used for split-client filtering |
| `Sessions` | |
| `Impressions` | |
| `Clicks` | |
| `Cost` | Was `Cost (*)` — asterisk removed |
| `Conversions` | Normalised from all client-specific names by Funnel.io |
| `Transactions` | Ecomm only, empty for Lead Gen rows |
| `Transaction Revenue` | Ecomm only, empty for Lead Gen rows |
| `Search Impression Share` | |
| `Total Eligible Impression Share` | |
| `Total Absolute Top Impression Share` | |
| `Views` | |
| `Hooks` | |
| `Holds` | |
| `Website` | Nullable — Paintnuts only |
| `Department` | Nullable — Forbes only |

## config.json changes

Add `sheet_name` field to every client entry. For most clients, `sheet_name` matches `name`. For split-stream clients, both config entries share the same `sheet_name` and are distinguished by `account_type`.

## Consequences

- `initialise_df()` in `core/get_funnel_data.py` updated to optionally filter by `Account Type` column when `client['account_type']` is set and the worksheet contains mixed rows.
- All `df.iloc[:,N]` references replaced with named column access.
- `config.json` gains `sheet_name` on all 13 client entries.
- Funnel.io export must be reconfigured with the canonical column schema and metric normalisation.
- Harrison's two Funnel Import worksheets are consolidated into one by Funnel.io.
