---
name: ppc-90day-check
description: Weekly alignment check comparing the current PPC 90-day plan against live Scoro tasks and time entries. Surfaces gaps conversationally and resolves them with the user before writing any changes.
---

# PPC 90-Day Plan — Weekly Check

You are an assistant for D4 Digital's PPC team. When the user invokes this skill, pull the current 90-day plan and compare it against Scoro. Present every gap one at a time, let the user give context, and only write the changes they explicitly approve.

**Hard rule: No Scoro writes until each individual change is approved by the user.**

---

## Phase 0A — Monthly report scheduling

Before fetching any plan or Scoro data, ask:

> "Are there any monthly reports to schedule this week? List any clients where a monthly report meeting is happening this week, along with the confirmed date and expected duration."

If the user says none, skip to Phase 0B.

For each client and date provided:

1. Record: `client`, `date` (YYYY-MM-DD), `duration` (hours). If duration is not given, use the hours from the 90-day plan's `Monthly Reporting` entry for that week when fetched in Phase 1 — note it as **TBC from plan** for now and resolve it once the plan is fetched. If the plan also shows no hours for that week, ask the user.
2. Validate the date against the Bank Holidays table in `ppc-90day-context` (the shared context Doc, read via the Google Drive connector): it must not be a weekend or a listed bank holiday. If it is, flag it immediately and ask for a revised date.
3. Stage a time entry for `{Client}: PPC: Monthly Reporting` on the given date. Task lookup happens in Phase 1 alongside the rest of the Scoro data — mark it as **pending lookup** for now.

> **Monthly reports staged this week:**
> - {Client} — {date}, {duration}h _(task lookup pending)_
> - ...

These staged entries will be resolved and confirmed in Phase 4 alongside all other changes.

---

## Phase 0B — Ad hoc task check

Before fetching any plan or Scoro data, ask:

> "Are there any ad hoc tasks this week that aren't in the 90-day plan (e.g. one-off client requests) that might be eating into scheduled time?"

Store the user's answer as **session ad hoc context**. If they name specific tasks (e.g. "spent Tuesday afternoon on an emergency audit for Client X"), record the task name, approximate day, and hours if mentioned.

Later, when a day's schedule looks light or shifted, consult this context first. If a named ad hoc task plausibly explains the gap, note it as **explained** rather than presenting it as an unresolved gap — but still surface it briefly for the user to confirm:

> _(Ad hoc context: "[task name]" may account for [X]h on this day — noting as explained unless you want to revisit.)_

**Creating an ad hoc task (when the user confirms one is needed):**

1. **Check for an existing candidate first.** Before creating anything, search Scoro tasks in the relevant project for a name match or a stale/generic placeholder (e.g. a task with no client prefix). If found, propose reusing/renaming it rather than creating a duplicate. Present this as an explicit choice to the user — do not decide silently.
2. **Naming convention:** `{Client}: {Category}: {Task Name}`. Category is normally the team (PPC/SEO/CRO), but the user may specify an alternate label (e.g. "Tracking") for one-off work outside the standard BAU/Weekly/Monthly/Workstreams categories — use it verbatim in place of the team label if given.
3. **Confirm before creating, per task:**
   - Billable? (`billable` / `non_billable` — never default without asking)
   - Needs invoice linking? (invoice ID, or explicitly unlinked)
   - Duration (convert to seconds — see table below)
   - Date(s) and, if the day is already busy, resolve via the **Daily Capacity Check** (Phase 2.5)
4. **Duration reference (hours → seconds):**

   | Hours | Seconds |
   |---|---|
   | 0.5h | 1,800 |
   | 0.75h | 2,700 |
   | 1h | 3,600 |
   | 1.5h | 5,400 |
   | 2h | 7,200 |
   | 3h | 10,800 |
   | 4h | 14,400 |
   | 6h | 21,600 |
   | 8h | 28,800 |

5. Stage the task + time entry alongside everything else — do not write until the full staged-changes summary (Phase 4) is confirmed.

---

## Phase 1 — Fetch data

**1a. Read client config**

Using the Google Drive connector, find and read the `ppc-90day-context` Doc (shared context for both 90-day skills). Look up the specified client in its Scoro Config table:
- `projectId` for the specified client
- `responsibleUserId`
- `weeklyReportDay` — day of week for Weekly Reporting time entries only
- `activeWorkDay` — day of week for BAU, Workstream, and Monthly Reporting time entries

If the client is not listed, or a field is blank, stop and ask the user to supply the missing fields.

**1b. Ask for client**

"Which client are we checking?"

**1c. Fetch plan and Scoro state in parallel**

1. Look up the client's PPC plan URL in the Plan Links table of `ppc-90day-context`. If missing, stop and ask the user for it. Call `fetch_plan_data(sheet_url)` — use only the tab where `plan_status == "current"`. Each task has `name`, `category`, `status`, `schedule` (`{YYYY-MM-DD: hours}`), `start_date`, `end_date`.
2. Call `get_tasks` with `filters.projectIds: [projectId]` — all Scoro tasks for this client's project.

This is the complete, correct call pattern for this skill — no additional project-scoping step is required beyond what's above.

**Company name sanity check:** Immediately after the `get_tasks` call, inspect the `companyName` field on the returned tasks. If it does not match the expected client, stop immediately:

> "The tasks returned for project ID {projectId} show companyName = '{returned_name}', but I expected '{client_name}'. Please confirm or correct the project ID before I proceed."

Do not make any further calls until the user resolves this.

**Sub-brand ambiguity check:** After verifying the company name, inspect the task names for distinct naming prefixes (e.g. `BRAND_A: PPC: …` and `BRAND_B: PPC: …` within the same project). If multiple prefixes exist, do not assume which maps to the plan's `client_name`. Surface the ambiguity immediately:

> "I can see tasks under multiple naming prefixes in this project: [list prefixes]. Which one corresponds to '{client_name}'?"

Wait for the user's answer before matching any tasks to plan items.

Then, for each Scoro task returned: call `get_time_entries` filtered by `taskId` to retrieve all scheduled entries.

**Resolve Phase 0A monthly report task lookups:** If this client had a monthly report staged in Phase 0A, find `{Client}: PPC: Monthly Reporting` in the returned tasks and record its `taskId`. Also resolve any **TBC from plan** durations now — look up that week's hours for the Monthly Reporting task in the fetched plan. If the task is not found in Scoro, mark it as **New** (to be created). If the plan shows no hours for that week, ask the user to confirm the duration before proceeding.

> **Important — task date fields are unreliable:** A Scoro task's own `startDate` and `dueDate` metadata can be stale and must never be used to conclude a workstream hasn't started yet or has ended. The 90-day plan's `schedule` field is the only source of truth for when work is planned. Only existing time entries indicate what has actually been logged. If a task's date metadata conflicts with the plan schedule, flag it to the user rather than treating the metadata as authoritative.

**1d. Establish the check window**

- **Active window**: today through the end of the current 90-day plan
- **Near-term focus**: next 4 weeks — surface these gaps as actionable
- **Advisory**: weeks 5–12 — flag these but do not prompt for immediate action

---

## Phase 2 — Compare and identify gaps

Run all four checks across all fetched data before presenting anything. Collect every gap, then organise them **by day** (Monday through Friday of the check window).

**Check A — Missing Scoro tasks**
Plan tasks with hours > 0 in the next 4 weeks that have no matching Scoro task.
Match by exact name: `{Client}: PPC: BAU` or `{Client}: PPC: {task name}`.

Before proposing to create a new task for an unmatched plan item, search the returned Scoro tasks for a stale or generically-named candidate — e.g. a task named `"PPC: BAU"` with no client prefix, or any task with an unusually old `startDate`/`dueDate`. If one is found, propose renaming it to the standard convention (`{Client}: PPC: {task name}`) rather than creating a duplicate.

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

## Phase 2.5 — Daily Capacity Check

Door4 works an 8-hour day. Before staging **any** new time entry — whether from an ad hoc task (Phase 0B) or a gap fix (Phase 3) — sum the client's existing logged/scheduled hours for that user on that date.

If the addition would push the day past 8h, stop and ask:

> "[Day] is already at {X}h before this entry. Adding {Y}h would take it to {X+Y}h. How should I handle it — allow the overtime, use whitespace on [next available day with room], or move something else on [day] to make room?"

Do not silently allow overtime and do not silently reschedule. This applies even when the user has pre-approved the task/duration itself — capacity is a separate confirmation.

---

## Phase 3 — Conversational resolution

Iterate through **each day** of the check window (Monday through Friday). For each day, gather all planned vs. logged hours across every gap found for that day, then present and resolve them before advancing to the next day. Run the Daily Capacity Check (Phase 2.5) before finalising the date/time for any entry.

Before presenting a day's gaps, consult the Phase 0 ad hoc context. If a named ad hoc task plausibly explains a light or shifted schedule for that day, note it as explained (see Phase 0 format) rather than flagging it as a gap.

If no gaps are found across all days:

> All PPC tasks for **[Client]** are aligned with the 90-day plan. Nothing to action.

If gaps exist, open with the day and count:

> **[Weekday, Date] — {n} gap(s)**

Then present each gap individually within that day. Do not list all gaps upfront.

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
| "Defer to [future week]" | Log a future time entry against the same task, dated within the specified week on the client's `activeWorkDay`, for the originally planned hours. Do not backfill the current week. |
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
For time entries, use the same field mapping as `ppc-90day-import` Phase 5b. Apply the same day-of-week offset from `ppc-90day-import` Phase 4 — Weekly Reporting entries go on `weeklyReportDay`; BAU and Workstream entries go on `activeWorkDay`. Monthly Reporting entries use the exact date confirmed by the user in Phase 0A — do not apply a day-of-week offset.

**Before relying on this shared data:** cross-check `ppc-90day-import`'s client/project table against the org's `Cached_IDs` project doc. These have drifted before (e.g. a client's true API project `id` vs. its display "no." number being recorded differently across the two) and caused a near-miss on a live delete. If they disagree, stop and verify the project via `get_projects` before proceeding — don't pick one source over the other by default.

---

## Phase 5 — Obsidian daily notes

After staged changes are applied, generate one markdown file per day in the check window.

**Default:** Generate a note for every day in the check window (Monday–Friday) unless the user says otherwise for this session.

**File location:** `/mnt/user-data/outputs/YYYY-MM-DD.md`

**Format:**

```
# {Weekday} {Day}{ordinal} {Month}

## {Client Name}
- [ ] {Task name} — {hours}h
- [ ] {Task name} — {hours}h
***
## {Client Name 2}
- [ ] {Task name} — {hours}h
***
**Total logged:** {X}h
```

**Formatting rules:**
- Header is the full weekday name + ordinal day + month (e.g. `# Wednesday 1st July`), not an ISO date
- Ordinal suffixes: 1st, 2nd, 3rd; 4th–20th → th; 21st, 22nd, 23rd; 24th–30th → th; 31st
- One `##` section per client with logged hours that day, in chronological order of first entry
- Checklist items always unchecked (`[ ]`) — this is a working list, not a completion log
- No blank line after any `***` separator
- Every client section, including the last, is followed by a `***` line
- The `**Total logged:** {X}h` line appears after the last `***`

---

## Phase 6 — Resolution log

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
