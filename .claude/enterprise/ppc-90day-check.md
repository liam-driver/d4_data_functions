---
name: ppc-90day-check
description: Weekly alignment check comparing the current PPC 90-day plan against live Scoro tasks and time entries. Surfaces gaps conversationally and resolves them with the user before writing any changes.
---

# PPC 90-Day Plan — Weekly Check

You are an assistant for D4 Digital's PPC team. When the user invokes this skill, pull the current 90-day plan and compare it against Scoro. Present every gap one at a time, let the user give context, and only write the changes they explicitly approve.

**Hard rule: No Scoro writes until each individual change is approved by the user.**

---

## Phase 1 — Fetch data

**1a. Read client config**

Read the **Scoro Client Config** from the enterprise project docs:
- `projectId` for the specified client
- `responsibleUserId`

**1b. Ask for client**

"Which client are we checking?"

**1c. Fetch plan and Scoro state in parallel**

1. Call `fetch_plan_data(client_name)` — use only the tab where `plan_status == "current"`. Each task has `name`, `category`, `status`, `schedule` (`{YYYY-MM-DD: hours}`), `start_date`, `end_date`.
2. Call `get_tasks` with `filters.projectIds: [projectId]` — all Scoro tasks for this client's project.

Then, for each Scoro task returned: call `get_time_entries` filtered by `taskId` to retrieve all scheduled entries.

**1d. Establish the check window**

- **Active window**: today through the end of the current 90-day plan
- **Near-term focus**: next 4 weeks — surface these gaps as actionable
- **Advisory**: weeks 5–12 — flag these but do not prompt for immediate action

---

## Phase 2 — Compare and identify gaps

Run all four checks before presenting anything. Collect every gap, then present them in priority order.

**Check A — Missing Scoro tasks**
Plan tasks with hours > 0 in the next 4 weeks that have no matching Scoro task.
Match by exact name: `{Client}: PPC: BAU` or `{Client}: PPC: {task name}`.

**Check B — Missing time entries**
Scoro tasks that exist but have no time entry for a week where the plan shows hours > 0.
Only flag weeks within the active window.

**Check C — Status mismatches**
Cases where the plan `status` and the Scoro task `statusName` are materially inconsistent.
Notable mismatches to flag:
- Plan: `Blocked` / Scoro: `In Progress` or `To Do`
- Plan: `Complete` / Scoro task not marked Done
- Plan: `In Progress` / Scoro task marked Done

**Check D — Stale entries**
Time entries scheduled for future weeks on tasks where the plan now shows 0 hours for those weeks. May indicate a dropped or rescheduled workstream.

---

## Phase 3 — Conversational resolution

If no gaps are found:

> All PPC tasks for **[Client]** are aligned with the 90-day plan. Nothing to action.

If gaps exist, state the total count first:

> Found **{n} gaps** across [Client]'s PPC plan. I'll walk through them one at a time.

Then present each gap individually. Do not list all gaps upfront.

**Gap format:**

> **Gap {n} of {total} — {Check type}**
> Task: `{Scoro task name}` {(ID: {id}) if exists}
> Plan says: {what the plan shows}
> Scoro shows: {what Scoro currently shows}
> **Proposed fix:** {specific action — create task / add time entry / update status / remove entry}
>
> Confirm this fix, skip it, or let me know if there's context I should know (e.g. it's blocked, the workstream was dropped, hours changed).

Wait for the user's response before presenting the next gap.

**Handling user responses:**

| Response | Action |
|---|---|
| Confirm / yes / proceed | Stage the proposed fix |
| Skip / not needed | Log as acknowledged, move on |
| "It's blocked" or similar context | Update Scoro task status to Blocked if appropriate; log the reason; move on |
| "We dropped that workstream" | Stage task status update to cancelled/done; log |
| Custom instruction | Incorporate, stage the adjusted fix, confirm before staging |

Never skip a gap silently. Every gap gets a logged outcome.

---

## Phase 4 — Confirm and apply staged changes

Once all gaps have been reviewed, summarise everything staged:

> **Staged changes — {n} actions**
> 1. Add time entry: `{task name}` — {date}, {duration}
> 2. Update status: `{task name}` → Blocked
> 3. Create task: `{task name}` — project {id}, user {id}
>
> Skipped / acknowledged: {n} items
>
> Confirm to apply these changes, or adjust anything first?

**Do not write to Scoro until the user confirms this summary.**

Execute in this order:
1. Task creations (`create_task`)
2. Task status updates (`update_task`)
3. New time entries (`create_time_entry`)

For task creation, use the same field mapping as `ppc-90day-import` Phase 5a.
For time entries, use the same field mapping as `ppc-90day-import` Phase 5b.

---

## Phase 5 — Resolution log

| # | Type | Task | Detail | Outcome |
|---|---|---|---|---|
| 1 | Time entry added | FALKN: PPC: Paid Search Expansion | 2026-06-29, 2h | Done ✓ |
| 2 | Status updated | FALKN: PPC: Shopping / PMax | → Blocked | Done ✓ |
| 3 | Skipped | FALKN: PPC: BAU | 2026-07-06 entry | Not needed — confirmed |

Totals:
- Changes applied: n
- Skipped / acknowledged: n
- Any items that could not be completed (surface for follow-up)

---

## Quick Reference

| Setting | Value |
|---|---|
| Scope | PPC only |
| Activity type | 322 (PPC) |
| Near-term focus window | Next 4 weeks |
| Advisory window | Weeks 5–12 |
| isCompleted for new entries | false |
| Write before user approval | Never |
