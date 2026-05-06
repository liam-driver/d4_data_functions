## Problem Statement

D4 has a monthly reporting workflow that currently requires manual effort to assemble a branded PowerPoint deck for each client. The infrastructure to generate slide content (LLM), render charts, and assemble the deck from a template already exists in isolation — but there is no orchestrator wiring these pieces together. As a result, monthly PowerPoint reports cannot be generated, and there is no way to trigger generation via the MCP server used for weekly reports.

## Solution

Build `monthly_reports/main.py` as the orchestrating entry point that chains the existing pipeline stages: date setup → two-pass data fetch (month-on-month and year-on-year) → chart rendering → PPT assembly → dated local output. Extend the LLM slide content function to receive both comparison datasets. Expose the full pipeline as a single MCP tool so it can be triggered from a Claude skill. During development, the same pipeline is callable directly from the CLI with a `--client` argument.

## User Stories

1. As a developer, I want to run `python -m monthly_reports.main --client "ClientName"` and have a complete PowerPoint deck saved locally, so that I can iterate on the pipeline without needing the MCP server running.
2. As a Claude skill, I want to call a single `generate_monthly_report(client_name)` MCP tool and receive the output file path, so that I can generate a monthly deck for any client in one step.
3. As a developer, I want the output file named `{client_name}_monthly_{YYYY_MM}.pptx`, so that I can identify which client and month a deck belongs to without opening it.
4. As a developer, I want the monthly data fetch to cover the previous full calendar month, so that the report always reflects a complete, closed reporting period.
5. As a developer, I want both a month-on-month and a year-on-year comparison dataset fetched for every run, so that the LLM can choose the most meaningful comparison for each slide.
6. As a developer, I want the LLM (GPT-4o-mini) to receive both MoM and YoY datasets in a single call, so that it can reference whichever comparison window is most insightful per trend or action slide.
7. As a developer, I want the monthly data stored in a separate JSON file from the weekly data, so that monthly and weekly pipelines do not overwrite each other's intermediate files.
8. As a developer, I want the `charts/` directory created automatically if it does not exist, so that the first run does not fail with a missing directory error.
9. As a developer, I want rendered chart PNGs left on disk after the deck is built, so that I can inspect individual charts for debugging without opening the PPT.
10. As a developer, I want the PPT generation to use the existing `slides/template.pptx`, so that all brand styles and slide layouts are inherited without duplication.
11. As a developer, I want the `generate_monthly_report` MCP tool to follow the same subprocess pattern as `fetch_client_data` and `send_weekly_report`, so that the server remains stateless and the tool is easy to extend.
12. As a developer, I want the MCP tool to validate the client name against `config.json` before running the pipeline, so that bad input fails fast with a clear error message.
13. As a developer, I want the MCP tool to return the path of the generated PPT file on success, so that downstream steps (e.g. uploading to Drive) can locate it.
14. As a developer, I want `generate_ppt` to accept an explicit output path rather than hard-coding `slides/test.pptx`, so that the monthly orchestrator controls where the file is saved.
15. As a developer, I want a `generate_monthly_report` Claude skill (analogous to the weekly report skill), so that I can invoke the pipeline conversationally without knowing the MCP tool name.

## Implementation Decisions

### Modules

**New: monthly orchestrator**
- Entry point supporting both CLI (`--client` arg) and direct import by the MCP tool.
- Computes `start_date` as the first day of the previous calendar month and `end_date` as the last day of the previous calendar month.
- Computes two comparison windows from the client's existing `comparison_dates` config field:
  - MoM: same calendar window one month prior
  - YoY: same calendar window one year prior
- Calls the data fetch function twice — once per comparison window — storing results under distinct keys (`*_mom`, `*_yoy`) in the client dict.
- Saves the enriched client dict to a monthly-specific intermediate file (`storage/{client_name}_monthly_data.json`) to avoid collision with the weekly `_data.json`.
- Creates the `charts/` directory if absent.
- Calls `generate_ppt` with an explicit output path.

**Modify: PPT assembler (`generate_ppt`)**
- Add an `output_path` parameter; stop hard-coding `slides/test.pptx`.
- Read from the monthly-specific data file rather than the weekly one.
- No other behavioural changes.

**Modify: LLM slide content function (`generate_monthly_slide_content`)**
- Extend the prompt payload to include both `paid_data_mom`, `llm_data_mom`, `overall_data_mom` and their `*_yoy` counterparts.
- Label each dataset clearly in the system prompt so the model understands which window is which.
- No schema changes to the output — the model's slide content JSON format is unchanged.

**Modify: MCP server**
- Add a `generate_monthly_report(client_name: str) -> str` tool.
- Validate client name with the existing `_validate_client_name` helper.
- Run `monthly_reports/main.py` as a subprocess (same pattern as `fetch_client_data`).
- Return the output file path on success; raise on non-zero exit code.

### Data flow

```
CLI / MCP tool
  -> main.py: set monthly dates on client dict
  -> get_funnel_data() x 2 (MoM comparison window)
  -> get_funnel_data() x 2 (YoY comparison window)
  -> save storage/{client}_monthly_data.json
  -> generate_ppt(client_name, output_path)
      -> generate_monthly_slide_content(client)  [GPT-4o-mini, both datasets]
      -> render_graph() x N  ->  charts/*.png
      -> assemble slides/template.pptx
      -> save slides/{client}_monthly_{YYYY_MM}.pptx
```

### Key constraints
- Monthly and weekly pipelines must not share intermediate data files.
- `charts/` directory is created lazily; PNG files are not cleaned up after assembly (cleanup deferred).
- The MCP tool is stateless — it spawns a subprocess and returns; no in-process state is shared with the server.
- Delivery (email, Google Drive upload) is explicitly out of scope for this iteration.

## Testing Decisions

**What makes a good test here:** test external behaviour — inputs and outputs — not internal implementation. For the date logic, assert on the date values written into the client dict; do not assert on which internal helper was called.

**Modules worth testing in isolation:**

- **Date calculation logic in the orchestrator** — the function that derives `start_date`, `end_date`, `compare_start_mom`, `compare_end_mom`, `compare_start_yoy`, `compare_end_yoy` from the current date and the client's `comparison_dates` field. This is pure Python with no I/O and is the most failure-prone piece of new logic. Test edge cases: run on the first day of the month, last day of the month, leap-year February.

**Modules not worth unit-testing:**
- The MCP tool (thin subprocess wrapper — integration-tested by running it end-to-end).
- `generate_ppt` output path change (single-line parameter addition, verified by running the pipeline).
- LLM prompt changes (non-deterministic output; validate by inspection, not assertion).

## Out of Scope

- **Delivery** — emailing the deck, uploading to Google Drive, or posting to Slack. Delivery will be designed and built separately once local generation is stable.
- **Slack context injection** — pulling Slack channel messages as additional LLM input. Marked as a future enhancement; not wired in this iteration.
- **Per-client monthly opt-in flag** — all clients are eligible; the caller selects the client explicitly.
- **Chart cleanup** — removing `charts/*.png` after PPT assembly. Deferred until the pipeline is stable.
- **Scheduled / automatic triggering** — no cron job or date-based filter. Generation is always on-demand.
- **`/monthly-report` Claude skill** — the MCP tool exposes the capability; a dedicated skill can be added once the tool is proven.

## Further Notes

- The brief at `docs/briefs/monthly_report_automation.md` documents the existing infrastructure and the known gaps this PRD closes.
- `slides/template.pptx` exists and contains the 14 slide layouts the assembler depends on.
- The `charts/` directory does not currently exist and must be created at runtime.
- GPT-4o-mini is the model used for slide content generation — consistent with the weekly commentary function.
- British date format (`dd/mm/yyyy`) is used throughout the pipeline; this must be preserved in all new date string fields.
