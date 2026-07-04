# ADR 0011 — SEO Plan: Cell Colour as Date Inference Signal

**Status**: Accepted

## Context

SEO 90-Day Plans are Google Sheets with no explicit `Start Date`, `End Date`, or `Status` columns. The only timing signal is cell background colour: cells coloured `#fff2cc` indicate that a task is active in that week column. The alternative was to treat SEO plans as narrative context only — returning the task list without date ranges and skipping the Gantt slide.

## Decision

Parse SEO plan sheets using `fetch_sheet_metadata(params={"includeGridData": "true"})` via the existing gspread credentials (no additional packages required). For each task row, the first and last `#fff2cc`-coloured week column determine `start_date` and `end_date`. Status is inferred from those dates relative to today: future → `"Scheduled"`, overlapping today → `"In Progress"`, past → `"Complete"`.

Tasks with no coloured cells at all are skipped — they have no schedulable period.

## Consequences

- SEO tasks appear in the Gantt and Kanban slides on the same code path as PPC/CRO tasks with no changes to the slide rendering layer.
- If the SEO team changes their colour convention (e.g. uses a different shade for deprioritised tasks), the colour check (`#fff2cc`) will need updating.
- `#fff2cc` detection uses a tolerance comparison against the API's 0–1 float RGB values to handle minor rounding differences.
- The alternative (narrative-only) was rejected because it would produce an inconsistent monthly deck experience across teams.
