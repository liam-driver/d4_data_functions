# PRD: Monthly Report Generic Template System

## Problem Statement

The monthly report PowerPoint pipeline assembles slides in a single monolithic function. Every slide type is wired directly into the main assembly flow — there are no reusable building blocks. Adding a new slide type (e.g. a data table or a planning overview) means reaching into the middle of the pipeline and writing bespoke code. The output is also limited: there is no data table slide, no 90-day plan status slide, and no standalone scorecard. The result is a deck that requires heavy manual effort in Google Slides before it can go to a client.

---

## Solution

Refactor the slide assembly layer into a library of generic, composable template functions — one function per slide type. Each function is self-contained: it takes explicit data arguments, creates the slide, populates it, and returns it. The main pipeline becomes a clean orchestration of these building blocks. New slide types (table, planning/Gantt) are added as first-class templates. A bug in the stacked bar chart renderer is fixed as part of this work.

---

## User Stories

1. As a report author, I want a reusable `slide_chart_commentary` function, so that I can add a chart + bullet-point commentary slide anywhere in the deck without duplicating layout code.
2. As a report author, I want a reusable `slide_commentary` function, so that I can add a text-only slide (title + summary + bullets) without a chart when an action has no graph.
3. As a report author, I want a reusable `slide_scorecard_commentary` function, so that I can show KPI boxes alongside written commentary on the same slide.
4. As a report author, I want a reusable `slide_scorecard` function, so that I can add a standalone KPI scorecard slide with boxes laid out in a horizontal row.
5. As a report author, I want a reusable `slide_section_separator` function, so that I can insert navy, gold, or orange section breaks at any point in the deck.
6. As a report author, I want a reusable `slide_cover` function, so that I can generate a branded cover slide from a title string.
7. As a report author, I want a `slide_table` function, so that I can render a channel × metric performance table with header row and alternating row shading.
8. As a report author, I want a `slide_table_commentary` function, so that I can show a data table on the right alongside bullet-point commentary on the left.
9. As a report author, I want a `slide_planning_gantt` function, so that I can render the client's current 90-day plan tasks as a colour-coded status table in the deck.
10. As a report author, I want status cells in the planning table to be colour-coded by status value (Complete = teal, In Progress = gold, Scheduled = light grey, Blocked = orange), so that the client can scan plan health at a glance.
11. As a report author, I want each template function to accept explicit, typed arguments (not a raw `client` dict), so that the functions are testable in isolation without needing a full data pipeline run.
12. As a report author, I want the main `generate_ppt` pipeline to call template functions sequentially, so that the deck structure is readable as a top-level list of slide-building calls rather than a mix of layout logic and content.
13. As a report author, I want KPI boxes to display the current value, previous value, and percentage change on three typographic lines, so that the client can read performance at a glance without opening a spreadsheet.
14. As a report author, I want charts embedded in slides to preserve their aspect ratio, so that the output does not look distorted when opened in Google Slides.
15. As a report author, I want table header rows to use the brand dark colour with white text, so that tables are visually consistent with the deck's design system.
16. As a report author, I want the 90-day plan section to only appear if a `plan_json` is present for the client, so that clients without a plan configured don't get an empty section.
17. As a report author, I want the `_extract_current_tasks` helper to handle multiple plan JSON shapes (nested by quarter, flat list, keyed by `tasks`), so that plan data from different quarters or formats doesn't break the pipeline.
18. As a report author, I want plan task dates formatted as `dd/mm/yyyy` in the planning table, so that the output is consistent with the British date format used across the rest of the deck.
19. As a developer, I want the `render_stacked_bar_chart` function signature fixed to match the other renderers, so that stacked bar chart specs don't raise a `KeyError` at render time.
20. As a developer, I want all low-level helpers (table shaping, KPI box drawing, title textbox, bullet population) to be extracted as private `_` functions, so that the template builders stay readable and the helpers can be reused across multiple slide types.

---

## Implementation Decisions

### Modules to build or modify

- **Slide template builders** — a set of public `slide_*` functions in `generate_ppt.py`, one per slide type. Each function accepts explicit arguments, creates a slide from the appropriate layout index, populates all placeholders and programmatic shapes, and returns the slide. No function reads from the `client` dict directly — data is passed in by the caller.

- **Low-level drawing helpers** — private `_` functions in `generate_ppt.py` covering: setting text on a text frame, populating bullet lists, adding a chart image at a specified position, adding a title textbox on a blank layout, styling a table cell, building a full table shape (headers + rows + optional status colouring), adding a vertical stack of KPI boxes to an existing slide.

- **Plan data extractor** — a private `_extract_current_tasks` function that normalises the `plan_json` structure (which varies: `{quarter: {tasks: [...]}}`, `{tasks: [...]}`, flat list) into a plain list of task dicts. `plan_status: "current"` is used to filter to the active quarter.

- **Pipeline orchestrator** — the `generate_ppt` function becomes a clean sequence of `slide_*` calls. A `_build_kpis` helper extracts KPI tuples from `client` in one place so the pipeline function doesn't contain account-type branching logic inline.

- **Stacked bar fix** — `render_stacked_bar_chart` in `generate_visualisation.py` currently has a broken `spec["graph"]` dereference; its signature and body should match the other renderers (`(graph, client)` where `graph` is the spec dict directly).

### Architectural decisions

- Template functions use `try/except` around `slide.placeholders[n]` accesses for indices beyond 0 and 1, because placeholder availability varies across layout types.
- Blank-layout slides (`SLD_LAYOUT_BLANK`) are used for table, standalone scorecard, and planning slides where programmatic shape placement gives more control than the built-in layout placeholders.
- `TITLE_AND_BODY` layout is retained for chart+commentary and commentary-only slides, since the existing placeholder positions already produce a working left-text / right-image split.
- Brand colours are consolidated into a single `C` dict to avoid scattered `RGBColor(...)` calls throughout the file.
- Status colour mapping lives in a `STATUS_COLOURS` dict keyed by status string, so new statuses can be added without touching the table rendering logic.
- The plan JSON structure confirmed from `plans.json`: `{client_name: {quarter_label: {plan_status, tasks: [{name, desc, category, status, start_date, end_date, platform}]}}}`. Task field names differ from the AI output schema (`name` not `task`, `desc` not `description`, dates in `dd/mm/yy` British format not ISO).

---

## Testing Decisions

**What makes a good test here**

Tests should verify the slide output contract — that a template function returns a slide with the expected number of shapes, the expected text in the first placeholder, and the expected fill colour on a KPI box or table header. They should not assert on internal implementation details like which `add_shape` call was made or the order of internal helper calls.

**Modules to test**

- `_extract_current_tasks` — pure function with no I/O, covers the multiple-format normalisation logic. High value, trivially testable.
- `_add_table_shape` — verifiable via python-pptx's object model (table row count, cell text, cell fill colour). No file I/O required.
- `slide_planning_gantt` — verifiable that it returns `None` for empty task list, and returns a slide with a table shape for a valid list.
- `slide_scorecard_commentary` — verify placeholder text is set and that the expected number of shapes (title + body + KPI boxes) are present on the returned slide.

**Prior art**

No existing tests in the codebase. Any new tests should be placed in a `tests/` directory and use `pytest`. A `Presentation` object loaded from `slides/template.pptx` is the natural fixture for slides tests.

---

## Out of Scope

- Screenshot + commentary slide (blank scaffold — no auto-population logic needed, added to Google Slides manually)
- 3-column cards slide (blank scaffold)
- Image grid slide (blank scaffold)
- Scoro and Slack data sources (separate integration work)
- Modifying `slides/template.pptx` — template changes require a re-export from Google Slides
- Monthly report email delivery (the output is a PPTX for upload to Google Slides, not an email)
- The `monthly_reports/generate_visualisation.py` chart rendering logic beyond the stacked bar signature fix

---

## Further Notes

- The `plan_json` task field is `name` (not `task`) and `desc` (not `description`). The AI commentary schema uses `task`/`description` as output field names, but the raw plan storage uses `name`/`desc`. The planning slide reads raw plan storage, so it must use `name`/`desc`.
- Dates in `plans.json` are `dd/mm/yy` (two-digit year), not ISO. `_fmt_date` must handle this format alongside ISO `yyyy-mm-dd`.
- The `plan_status` field (`"current"` vs `"old"`) is the correct filter for which quarter's tasks to render — not a positional assumption about the dict order.
