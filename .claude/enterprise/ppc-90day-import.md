---
name: ppc-90day-import
description: Monthly import of PPC 90-day plan tasks into Scoro. Reads the current 90-day plan, creates missing Scoro tasks, and schedules time entries for the upcoming calendar month. Run in the final week of the preceding month.
---

# PPC 90-Day Plan — Monthly Import

You are an assistant for D4 Digital's PPC team. When the user invokes this skill, follow the workflow below exactly. Nothing is written to Scoro until the user has explicitly approved the complete draft.

**Hard rule: No Scoro writes until the user confirms the draft at Phase 4.**

---

## Pre-flight: Read the client config

Before calling any tools, read the **Scoro Client Config** table from the enterprise project docs. You need for the specified client:
- `projectId` — the Scoro project ID
- `responsibleUserId` — the Scoro user ID of the PPC account manager
- `weeklyReportDay` — day of week for Weekly and Monthly Reporting time entries
- `activeWorkDay` — day of week for BAU and Active Workstream time entries

If the client is not in the config table, stop and ask the user to add an entry before proceeding.

---

## Phase 1 — Establish context

Ask the user:
1. Which client are we importing for?
2. Which month are we importing? (Default: next calendar month)

Confirm before fetching data:

> Importing **[Client]** PPC tasks for **[Month Year]**.
> Scoro project ID: **[id]** — responsible user: **[name] ([id])**.
> Is this correct?

Wait for confirmation.

---

## Phase 2 — Fetch and analyse the plan

**2a. Fetch plan data**

Call `fetch_plan_data` with `client_name`. This returns a dict keyed by sheet tab name. Use only the entry where `plan_status == "current"`. Each task object has:
- `name`, `desc`, `category`, `status`, `start_date`, `end_date`, `platform`
- `schedule`: `{"YYYY-MM-DD": hours_float, ...}` — one entry per week column where hours > 0

**2b. Identify target weeks**

Target weeks are all `YYYY-MM-DD` keys in any task's `schedule` where the date falls within the target calendar month.

**2c. Filter active tasks**

A task is active in the target month if it has at least one non-zero hour in any target week.

**2d. Consolidate BAU**

All tasks where `category == "BAU"` are merged into a single synthetic entry:

| Field | Value |
|---|---|
| Name | `{Client}: PPC: BAU` |
| Schedule | Sum hours across all BAU tasks per week |
| Start date | Earliest target week date with combined hours > 0 |
| Due datetime | Last target week date at 17:00, with correct BST/GMT offset |
| Description | *(omit)* |

`Active Workstream` and `Reporting` tasks remain as individual entries.

**2e. Build the import list**

Print a summary table before the Scoro lookup:

| # | Scoro Task Name | Source | Active Weeks | Total Hours |
|---|---|---|---|---|
| 1 | {Client}: PPC: BAU | BAU (consolidated) | n | x.xh |
| 2 | {Client}: PPC: Paid Search Expansion | Active Workstream | n | x.xh |
| 3 | {Client}: PPC: Weekly Reporting | Reporting | n | x.xh |
| ... | | | | |

---

## Phase 3 — Scoro lookup

For each task in the import list:

1. Call `get_tasks` with `filters.projectIds: [projectId]`
2. Search returned tasks for an **exact** name match
3. If found: record the `taskId` — time entries will be added to this task, no creation needed
4. If not found: mark as **New** — task creation required

Report lookup results before building the draft:

> **Lookup complete**
> - Existing tasks found: {n} — time entries will be added
> - New tasks to create: {n}
>
> Existing IDs: {name → id, name → id, ...}
>
> Any issues before I build the draft?

---

## Phase 4 — Build draft and confirm

Compile the complete draft. Apply bank holiday and weekend rules (see rules tables below) before generating dates.

**Day-of-week placement**

The plan's week column headers are always Mondays. Adjust each time entry date to the correct day within that week using the client config:
- BAU and Active Workstream tasks → use `activeWorkDay`
- Weekly Reporting and Monthly Reporting tasks → use `weeklyReportDay`

Day offsets from Monday: Monday +0, Tuesday +1, Wednesday +2, Thursday +3, Friday +4.

Example: FALKN `activeWorkDay = Thursday`. Week of `2026-06-01` (Monday) → entry date = `2026-06-04`.

If the adjusted date lands on a bank holiday, flag it in the draft — do not silently skip or move it without asking.

**Task creation table** (new tasks only):

| Task Name | Project ID | Responsible User | Start Date | Due DateTime | Activity Type |
|---|---|---|---|---|---|
| {name} | {id} | {user id} | YYYY-MM-DD | YYYY-MM-DDTHH:MM:SS±HH:MM | 322 (PPC) |

**Time entries table** (all tasks, ordered by task then date):

| # | Task Name | Task ID | Date | Start | Duration | Billable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | FALKN: PPC: BAU | NEW | 2026-06-01 | 09:00 BST | 2h / 7,200s | Yes | Week 1 of 4 |
| 2 | FALKN: PPC: BAU | NEW | 2026-06-08 | 09:00 BST | 2h / 7,200s | Yes | Week 2 of 4 |
| 3 | FALKN: PPC: Paid Search Expansion | NEW | 2026-06-01 | 09:00 BST | 2h / 7,200s | Yes | Week 1 of 2 |

State clearly:
- Total tasks to create: n
- Total time entries to create: n
- Total hours scheduled: x.xh
- Bank holidays encountered and how they were handled
- Any ambiguities requiring user input

Then ask:

> "Please review this draft import. Confirm to proceed, or advise any changes before I write to Scoro."

**Do not proceed until the user explicitly confirms.**

---

## Phase 5 — Execute

Only after explicit user approval.

**5a. Create new tasks**

For each task marked New, call `create_task`:

| Field | Value |
|---|---|
| name | Task name from import list |
| projectId | From client config |
| responsibleUserId | From client config |
| startDate | Earliest target week with hours (YYYY-MM-DD) |
| dueDateTime | Last target week end — 17:00 with correct BST/GMT offset |
| activityTypeId | 322 |
| billableTimeType | billable |
| status | task_status1 |
| description | Plan task `desc` — omit for BAU |

Capture each `taskId` returned. Do not proceed to time entries until all task creations are confirmed.

**5b. Create time entries**

For each row in the approved draft, call `create_time_entry`:

| Field | Value |
|---|---|
| taskId | From 5a or existing lookup |
| userId | From client config |
| startDateTime | YYYY-MM-DDTHH:MM:SS+01:00 (BST) or +00:00 (GMT) |
| duration | hours × 3,600 (integer seconds) |
| billableDuration | Same as duration |
| billableTimeType | billable |
| activityTypeId | 322 |
| isCompleted | false |

Create entries in batches — all entries for one task before moving to the next. Confirm each batch before proceeding.

---

## Phase 6 — Completion log

| # | Task Name | Task ID | Date | Duration | Status |
|---|---|---|---|---|---|
| 1 | FALKN: PPC: BAU | 10234 | 2026-06-01 | 2h | Scheduled ✓ |
| 2 | FALKN: PPC: BAU | 10234 | 2026-06-08 | 2h | Scheduled ✓ |
| 3 | FALKN: PPC: Paid Search Expansion | 10235 | 2026-06-01 | 2h | Scheduled ✓ |

Totals:
- Tasks created: n
- Time entries created: n
- Total hours scheduled: x.xh
- Any skipped entries or flags for follow-up

---

## Duration Reference

| Hours | Seconds |
|---|---|
| 0.25h | 900 |
| 0.5h | 1,800 |
| 0.75h | 2,700 |
| 1h | 3,600 |
| 1.5h | 5,400 |
| 2h | 7,200 |
| 3h | 10,800 |
| 4h | 14,400 |
| 6h | 21,600 |
| 8h | 28,800 |

## Timezone Reference

| Period | Offset |
|---|---|
| BST (last Sun Mar → last Sat Oct) | +01:00 |
| GMT (last Sun Oct → last Sat Mar) | +00:00 |

All `startDateTime` and `dueDateTime` values must include the correct offset. A wrong offset places entries on the wrong date in Scoro.

## Bank Holidays 2026

| Date | Holiday |
|---|---|
| 2026-01-01 | New Year's Day |
| 2026-04-03 | Good Friday |
| 2026-04-06 | Easter Monday |
| 2026-05-04 | Early May Bank Holiday |
| 2026-05-25 | Spring Bank Holiday |
| 2026-08-31 | Summer Bank Holiday |
| 2026-12-25 | Christmas Day |
| 2026-12-28 | Boxing Day (substitute) |

Never schedule a time entry on a bank holiday or weekend. If a target week-start falls on a bank holiday, flag it in the draft and ask the user how to handle it — do not silently skip or move the entry.

## Quick Reference

| Setting | Value |
|---|---|
| Scope | PPC only |
| Activity type | 322 (PPC) |
| Billable | Yes |
| Default session start | 09:00 |
| isCompleted for new entries | false |
| Write before user approval | Never |
