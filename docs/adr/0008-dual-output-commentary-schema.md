# Dual-output commentary schema for Detailed and Presentation decks

The monthly report now produces two PowerPoint files per run: a Detailed Deck (pre-meeting, metric-backed bullets) and a Presentation Deck (in-room, narrative-only bullets capped at 3, no data points). Rather than making two LLM calls or post-processing the detailed output, we extend the existing JSON schema for every commentary generator (`generate_monthly_slide_content`, `generate_dimension_cut_commentary`, `generate_mtd_slide_content`) to return both `bullets` (detailed) and `bullets_presentation` (narrative) in a single response. The two PPT files are then assembled from the same `client` data dict using whichever bullet array is appropriate.

## Considered options

- **Two separate LLM calls** — cleaner prompt separation but doubles API cost and latency per report.
- **Post-processing pass** — a second lightweight call strips data from detailed bullets. Adds a pipeline stage and risks losing narrative coherence between the two versions.
- **Dual-output schema (chosen)** — one call, full context available when writing both versions, no extra latency. The cost is a slightly larger schema and response payload, which is acceptable.
