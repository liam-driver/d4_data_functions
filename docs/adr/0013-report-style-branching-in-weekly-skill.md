# Branch Weekly Report commentary rules on report_style, not rewrite in place

Client feedback showed the existing Weekly Report commentary (metric-heavy, plan tasks dumped verbatim, uncapped insights) is hard for clients to read. Rather than editing the Commentary Rules in `ppc-weekly-report.md` in place, we introduce a `report_style` field on the Client (`'standard'` for now, hard-coded in `scripts/generate_client_contexts.py`, not `config.json`, since the latter is fully overwritten from the Config sheet on every `get_config.py` run) and structure the skill so shared mechanics (data sources, channel definitions, formatting rules like British English and no em-dashes) stay common, while the rules that actually change per style (WIP synthesis, insight count/shape, tone) live in per-style sub-sections the skill selects between at runtime.

Today every client is `'standard'`, so this adds scaffolding with no immediate behavioural difference from just rewriting the rules in place. The alternative — rewrite the existing rules directly and revisit the file's shape later if a second style appears — was rejected because `report_style` is stated as a deliberate, lasting axis (client-configurable in future), not a one-off tweak; building the branch now avoids a second restructuring of a hand-maintained prose skill file later, when the shared vs per-style boundary would be harder to extract cleanly from rules that had grown further under a single path.

## Considered options

- **Rewrite Commentary Rules in place, no branching** — rejected: cheapest today, but `report_style` is explicitly meant to support future styles per-client; deferring the split risks a messier extraction later.
- **Branch on report_style now (chosen)** — shared mechanics stay in one place, `'standard'`-specific rules live in a clearly bounded sub-section, future styles are additive.
