# Split monthly report into skeleton + insights, joined by a cached checkpoint

`ppc-monthly-report` was a single skill covering both structural deck-building (overview scorecards, actions, plan Kanban/Gantt) and narrative trend analysis (slide-by-slide data cuts). As the deck grew to cover three teams (PPC, SEO, CRO) instead of just PPC, we split it into two skills run by different people at different times: **d4-monthly-skeleton** (client services — overview + Kanban + Gantt for all three teams) and **ppc-monthly-report-insights** (PPC trend slides only, unchanged in spirit from the old Phase 2-4).

Because these two skills may run in entirely separate chat sessions with no shared context, `generate_skeleton_pptx` persists the confirmed team content (`overviews`, `plan_json`) to `storage/{client}_skeleton_content.json` server-side, in addition to rendering a real draft PPTX for client services to review. `generate_monthly_pptx` now takes only the new PPC `trends[]`, loads the cached skeleton checkpoint, slots trends into the PPC block, and renders the final Detailed + Presentation decks — it no longer accepts a full flat payload and requires the skeleton step to have run first.

The alternative — having insights resupply the full teams payload (overviews/plan_json for all three teams) verbatim alongside trends — was rejected because it relies on a context-free session perfectly reproducing another session's confirmed choices with no source of truth to check against. The cached checkpoint follows the same pattern already used by `fetch_monthly_client_data`/`fetch_trend_data` (`storage/{client}_monthly_data.json`), so it is consistent with the rest of the pipeline rather than a new mechanism.

`ppc-monthly-report.md` and its flat-payload contract are retired as part of this change, not kept alongside for backward compatibility — this is the split, not an additive option.

## Considered options

- **Two independent standalone decks** (no merge) — rejected: the goal is one client-facing deck; a client services draft and a PPC insights deck that never combine would leave someone to manually stitch slides together.
- **Insights resupplies everything verbatim** — rejected: fragile under a fresh context window, no verification against what was actually confirmed in skeleton.
- **Cached checkpoint + trends-only insights payload (chosen)** — server is the source of truth for what skeleton confirmed; insights' job is narrowed to exactly what it's named for.
