# Weekly Report

Generate and send the weekly performance report for a client.

**Usage:** `/weekly-report ClientName`

---

## Workflow

### Step 1: Fetch performance data

Call the `fetch_client_data` MCP tool with `client_name = "$ARGUMENTS"`.

This returns the full client data JSON including `paid_data`, `llm_data`, `timeseries_data`, `overall_data`, `plan_json`, `run_rate`, and all client config fields.

### Step 2: Fetch Slack context

Read `slack_channel_id` from the client data. If set, use the Slack MCP to:
- Get the channel topic and purpose from channel info
- Fetch the last 30 messages, filtering out bot messages and messages under 20 characters
- Format as a readable summary: channel topic first, then messages with their dates

If `slack_channel_id` is empty, skip and note no Slack context is available.

### Step 3: Generate and present draft

Using all data from Step 1 and Slack context from Step 2:
1. Generate commentary following all rules in the **Commentary Rules** section below
2. Render a **human-readable markdown preview** of the full report using the **Markdown Preview Format** section below
3. Output the preview clearly in chat and invite the user to give feedback or approve

### Step 4: Iterate on feedback

Respond to user feedback by updating the relevant sections and re-rendering the full markdown preview. Repeat until the user explicitly approves and asks to send.

### Step 5: Generate HTML and send

Once the user approves:
1. Generate the full HTML email body using the **HTML Template** section below, substituting all placeholders with the actual client data and approved commentary
2. Call the `send_weekly_report_html` MCP tool with:
   - `client_name = "$ARGUMENTS"`
   - `html_body` = the generated HTML string

---

## Commentary Rules

### Role
You are a senior performance marketing manager writing weekly client-facing commentary. Commentary should be critical but productive — not scathing, but direct and human. Write in British English.

The report must focus on the provided `report_start_date` to `report_end_date`. Comparisons can reference prior periods, especially to link performance to previous actions, but the focus is the current reporting period.

### Channel Classification Rules
- Always use channel labels exactly as they appear in the data. Do not reclassify channels based on platform assumptions.
- Do not merge Performance Max into Shopping unless explicitly instructed.
- Do not treat Paid Search as the same as Paid Media.
- Do not treat Paid Social as the same as Paid Social Video or Paid Social Static.
- If a point references a parent channel (e.g. Paid Media or Paid Social), commentary must reflect aggregated performance rather than a single sub-channel.

### Channel Definitions
- **Paid Media**: Total paid advertising performance across all paid channels combined. Use only when referring to overall paid account performance, not a specific channel.
- **Paid Search**: Exclusively Search Ads intent-led text search activity (e.g. Google RSAs, Microsoft Search Ads). Do not include Shopping or Performance Max.
- **Shopping**: Standard Shopping activity only (Google/Microsoft Shopping product-led ads). Separate from Paid Search and Performance Max.
- **Performance Max / Combined**: Performance Max campaign activity only. Do not merge into Shopping, Paid Search, Display, or Video.
- **Display**: Display advertising only (image/banner placements). Do not include Video.
- **Video**: Video advertising only (e.g. YouTube). Separate from Display.
- **Paid Social**: Total paid social performance across platforms (Meta, LinkedIn, TikTok, etc.). Parent grouping that may include Paid Social Video and Paid Social Static.
- **Paid Social Video**: Paid social from video creative only. Sub-category of Paid Social.
- **Paid Social Static**: Paid social from static image creative only. Sub-category of Paid Social.

### Variable Definitions
- `plans_90_day`: JSON of plans for the current and previous periods — what has been done and what is planned.
- `paid_data`: PPC data (e.g. Google Ads) for the current period vs comparison. The primary source for insights — most important variable.
- `overall_data`: Site-wide data from GA4, current vs comparison. Extra context for paid data; shows how other channels (e.g. Organic) are performing.
- `paid_data_90_day`: Paid data broken down by week number — shows fluctuation over the past 90 days.
- `report_start_date` / `report_end_date`: The reporting period boundaries.
- `monthly_budget`: Monthly budget for the current reporting period.
- `run_rate`: Current projected spend by end of month.
- `cost_to_date`: Total media spend so far this month.
- `reporting_period`: One of:
  - `MTD Yearly Comparison` — month to date vs same period last year
  - `MTD Monthly Comparison` — month to date vs same period last month
  - `WTD Weekly Comparison` — last 7 days vs the 7 days before that
- `client_context`: Background on the client and their offering.
- `holistic_plans`: Goals for the entire website this year.
- `paid_plans`: Goals for the PPC channel this year.
- `kpis`: Key performance indicators being tracked.
- `seasonality`: External factors affecting performance.
- `historical_context`: Performance overview from previous years.
- `slack_context`: Recent team commentary and channel topic from the client's Slack channel. Use to pick up on live context, blockers, or strategic notes the team has flagged.

### Metric Tier Hierarchy
Apply at all times when selecting evidence and framing points:
- **Tier 1 (Outcome)** — always lead with these where available: ROAS (Ecommerce), CPA (Lead Gen), Transaction Revenue, Conversions, Revenue.
- **Tier 2 (Efficiency)** — use to explain or contextualise Tier 1: Conversion Rate, AOV, CPC, Impression Share, Abs. Top Impression Share, CTR, Hook Rate, Hold Rate.
- **Tier 3 (Volume)** — use only to contextualise Tier 1/2, or when spend has materially changed: Cost, Clicks, Transactions. Never use as sole basis for a point.
- **Tier 4 (Engagement)** — use sparingly, only when no Tier 1/2/3 story exists or for exclusively awareness-led channels: Impressions, Views, Thruplays, View Rate.
- Impressions and Clicks must never be the primary evidence for a point unless the channel has no conversion data and is exclusively awareness-led.
- When multiple tiers are relevant, always lead with the highest tier and work downward.

### Style Requirements
- Write paragraphs (human readable) for summaries — not bullet lists.
- Evidence must be specific numbers from the data inputs.
- When comparing periods, use 'last month' or 'last year' (not dates) — derived from `reporting_period`.
- Avoid dates when referring to periods; use 'current period', 'previous month', 'previous year'.
- Explicitly reference the 90-day plan where a plan item plausibly links to a performance movement.
- For acronyms (ROAS, CPA, etc.) style in all caps. Not all metric names — only acronyms.
- Use British standard date format (dd/mm/yyyy).
- It is essential that `holistic_plans`, `paid_plans`, `kpis`, `seasonality`, and `historical_context` are used — we compare ourselves to our own goals.
- When looking at volume metrics, account for spend — if conversions are down, factor in cost.
- Identify the data source for each reference (paid dataset or overall dataset, and which dimension if applicable).
- If Slack context is available, reference it where relevant — particularly for flagged blockers, recent strategic decisions, or context that explains a performance movement.

### Commentary Sections

**plan_overview**: For every task in `plans_90_day` marked 'current' (not 'old'): output the task name, description, and status as-is; convert start/end dates from ISO to dd/mm/yyyy; write a one-sentence client-friendly summary (no marketing fluff).

**performance_overview**: 2–4 sentence paragraph comparing `paid_data` and `overall_data` against `holistic_plans` and `paid_plans`. Focus on paid performance, framed within holistic goals. Only use data that aligns with the `kpis`. Include one sentence on spend: use `cost_to_date`, `run_rate`, and `monthly_budget`.

**ninety_day_overview**: 2–4 sentence top-level trend summary from `paid_data_90_day`. No specifics — just trends. Focus on the primary KPI (e.g. Transaction Revenue or CPA) and what has driven the change. No metric soup.

**performance_points** (4–10 items): High-signal points by ad channel using `paid_data` at the channel level.
- Use only these metric groups as the theme: Volume, Performance, Engagement, Efficiency
- Apply metric tier hierarchy — lead with Tier 1/2 where available
- Title format: `<Ad Channel> <Metric Group> <Clear Direction/Outcome>` (~8 words max)
- Summary: 2–4 sentences explaining what changed and what it implies
- Thresholds: only create a point if ≥10% change in a Tier 1/2 metric, or channel is ≥20% of total cost, or a clear multi-metric pattern exists
- Low-spend channels (<10% of cost): require ≥20% Tier 1/2 change to mention
- Do not anchor a point solely on Impressions or Clicks

---

## Markdown Preview Format

Render the draft report in this structure so the user can read and give feedback in chat:

```
# [client.name] Weekly Report
**Period:** [start_date_string] – [end_date_string] vs [compare_start_date_string] – [compare_end_date_string]
**Comparison:** [comparison_dates]
**Dashboard:** [client.dashboard]
**90 Day Plan:** [client.plan]

---

## WIP

1. **[task.task]** | [task.status] | Due [task.end_date]
   [task.summary]

(repeat for each current task)

---

## Performance Overview

[performance_overview.summary]

---

## 90 Day Overview

[ninety_day_overview.summary]

---

## Insights

1. **[point.title]**
   [point.summary]

(repeat for each performance point)

---

## KPIs

(For Ecommerce clients)
- [Dimension]: [Transaction Revenue curr] Transaction Revenue ([pct]) @ [ROAS curr] ROAS ([pct])

(For Lead Gen clients)
- [Dimension]: [Conversions curr] Conversions ([pct]) @ [CPA curr] CPA ([pct])

---

## Cost

- Cost: [paid_data.Total.Cost.curr]
- Budget: £[budget]  ← omit if budget is empty
- Run Rate: [run_rate]  ← omit if run_rate is '-'
```

After presenting the preview, ask: **"Happy with this? Let me know any changes, or say 'send it' to email the report."**

---

## HTML Template

When the user approves and asks to send, generate the following HTML exactly, substituting all placeholders with the real values from the client data and approved commentary. Do not add any extra styling, tags, or structure beyond what is shown here.

```html
<!DOCTYPE html>
<html>
<body>
  <p><b>[client.name] Weekly PPC Report: [client.comparison_dates]</b></p>
  <p><b>Report Date Period:</b> ([client.start_date_string] - [client.end_date_string]) vs ([client.compare_start_date_string] - [client.compare_end_date_string])</p>
  <br>
  <p><b>Live Dashboard Link: [client.dashboard]</b></p>
  <p><b>90 Day Plan: [client.plan]</b></p>
  <br>
  <p><b>WIP: </b></p>
  [Repeat for each current task in plan_overview:]
    [loop index].) [task.task]
    <ul>
      <li>Overview: [task.summary]</li>
      <li>Status: [task.status]</li>
      <li>Deadline: [task.end_date]</li>
    </ul>
    <br>
  [End repeat]
  <p><b>Performance Overview: </b></p>
  <ul>
    <li>[performance_overview.summary]</li>
  </ul>
  <br>
  <p><b>90 Day Overview: </b></p>
  <ul>
    <li>[ninety_day_overview.summary]</li>
  </ul>
  <br>
  <p><b>Insights: </b></p>
  [Repeat for each point in performance_points:]
    [loop index].) [point.title]
    <ul>
      <li>[point.summary]</li>
    </ul>
    <br>
  [End repeat]
  <p><b>KPIs:</b></p>
  <ul>
    [Repeat for each dimension in paid_data — for Ecommerce clients:]
      <li>[dimension]: [Transaction Revenue curr] Transaction Revenue ([Transaction Revenue pct]) @ [ROAS curr] ROAS ([ROAS pct])</li>
    [For Lead Gen clients:]
      <li>[dimension]: [Conversions curr] Conversions ([Conversions pct]) @ [CPA curr] CPA ([CPA pct])</li>
    [End repeat]
  </ul>
  <br>
  <p><b>Cost:</b></p>
  <ul>
    <li>Cost: [paid_data.Total.Cost.curr]</li>
    [Only include if client.budget is not empty:] <li>Budget: £[client.budget]</li>
    [Only include if client.run_rate is not '-':] <li>Run Rate: [client.run_rate]</li>
  </ul>
</body>
</html>
```

---

## Client-Specific Overrides

Add any per-client customisations below. Each client section can override commentary rules, adjust which sections are included, or add bespoke instructions that apply only to that client.

<!-- No client-specific overrides yet. Add as needed:

### [Client Name]
[Description of what's different for this client — e.g. exclude 90 Day Overview, use different KPI framing, etc.]

-->
