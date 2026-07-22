# ADR 0015 — Traps & Tripwires Merge Groups Are a Slack-Layer Fix, Not ADR 0007

**Status:** Accepted
**Date:** 2026-07-22

## Context

Clients like Harrisons Direct and Revival Beds are split across two `config.json` rows / Funnel Import worksheets (one real-world account, two conversion streams). Traps & Tripwires ran checks per row and posted one Slack message per row to their shared `slack_channel_id`, duplicating the account-level checks (Budget Pacing, Campaign Spend, Brand Spend Split are identical across a pair — verified empirically) and splitting the one genuinely different check (Conversion Tracking) across two messages instead of one.

ADR 0007 already decided how to fix the underlying duplication: merge each pair's Funnel Import data into one worksheet with an `Account Type` column, add `sheet_name` to `config.json`, and filter in `initialise_df()`. That ADR is Accepted but was never implemented — `config.json` has no `sheet_name` field and each row still reads its own worksheet. It also only covers Lead Gen/Ecommerce splits (Harrisons); Revival Beds is a Lead Gen/Lead Gen split with no `Account Type` axis to filter on, so ADR 0007's mechanism wouldn't cover it as written.

## Decision

Fix Traps & Tripwires's Slack output without touching the data layer or waiting on ADR 0007. A hard-coded `MERGE_GROUPS` dict in `traps_and_tripwires/main.py` (same pattern as `PROJECT_GROUPS`/`REPORT_STYLES`/`SCORO_CONFIG` in `scripts/generate_client_contexts.py` — `config.json` is regenerated from the Config sheet on every run and can't hold hand-added fields) lists which config rows belong to one real account. `merge_grouped_clients()` collapses each group's `client_results` into one entry: shared account-level checks are taken from the first present member, Conversion Tracking is kept per member and relabeled with that member's distinguishing suffix (e.g. "Conversion Tracking — Registrations").

The two config rows and two Funnel Import worksheets are untouched. This only changes how results are aggregated before posting to Slack.

## Consequences

- Adding a new split-client to T&T's merge behaviour means adding an entry to `MERGE_GROUPS`, not touching `config.json`.
- If ADR 0007 is ever implemented, `MERGE_GROUPS` and `merge_grouped_clients()` become redundant (one worksheet ⇒ one config row ⇒ nothing to merge) and should be removed at that point.
- The merge assumes a group's account-level checks are identical across members without verifying it at runtime — true today because members share the same underlying ad account, but a future group added to `MERGE_GROUPS` that doesn't hold this invariant would silently show the first member's numbers for all.
