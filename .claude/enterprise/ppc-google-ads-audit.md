---
name: ppc-google-ads-audit
description: Run a structured PPC account audit from raw data to Obsidian markdown document. Use this skill whenever a PPC account manager wants to audit an account, review what's working and what isn't, clean up account structure, establish a performance baseline, or create a short-term action plan. Triggers on phrases like "audit the account", "review the account", "what's working", "clean up the structure", "I'm covering this account", "taking over an account", "account has been neglected", or any request to systematically assess a Google Ads account before making changes. Always use this skill for PPC account audits even if the user only mentions one section of the workflow.
---

# PPC Account Audit

A step-by-step workflow for auditing a Google Ads account from raw data exports to a written audit document. Built for Door4 PPC account managers with day-to-day account access.

---

## Workflow Overview

```
Audit
├── Step 1: Data Upload
├── Step 2: Grill-Me (scope alignment)
├── Step 3: Shared Foundations
│   ├── 3a. Conversion Tracking
│   └── 3b. Change History
├── Step 4: Channel Modules (run applicable modules only)
│   ├── 4a. Search Module
│   ├── 4b. Performance Max Module
│   └── 4c. Shopping Module
└── Step 5: Output — Obsidian Markdown Document
```

Do not skip steps or combine them. Each step requires the user to confirm before moving to the next. The audit is a human-in-the-loop workflow — findings are reviewed and validated section by section, not produced in one pass.

---

## Step 1: Data Upload

Ask the user to upload the baseline data set before anything else. Do not proceed to the grill-me until the data is in.

**Required exports (all accounts):**

- **Campaign report** -- all campaigns, 90-day window. Columns: Campaign, Campaign type, Status, Budget, Bid strategy type, Optimisation score, Clicks, Impressions, Cost, Conversions, Conv. value, Conv. value / cost.
- **Search terms report** -- 90-day window. Columns: Search term, Campaign, Ad group, Match type, Clicks, Impressions, CTR, Avg. CPC, Cost, Conversions, Added/Excluded.
- **Change history report** -- 90-day window. All change types, all users.
- **Conversion actions screenshot** -- a screenshot of the Goals > Conversions > Summary screen in Google Ads showing all conversion actions, their status, optimisation setting (Primary/Secondary), and conversion counts.

**Conditional exports (add if applicable):**

- **Shopping / Product report** -- if the account runs Shopping or Performance Max with a product feed. Columns: Title, Status, Issues, Price, Clicks, Impressions, Cost, Conv. value.

Once all relevant files are uploaded, read them all before proceeding. Extract and silently note:
- Campaign names, types, budgets, bid strategies, spend and conversion data
- Search term volume, brand vs non-brand split, irrelevant term patterns
- Change history timeline -- who did what, when, and how long any gaps were
- Conversion action setup from the screenshot

Do not share a full data dump with the user. Carry the data as context for the grill-me and subsequent steps.

---

## Step 2: Grill-Me

Run the grill-me after reading the data -- not before. The data answers many questions automatically. Use the grill-me to close gaps the data cannot answer and confirm scope.

Ask one question at a time. Use project context (client brief, services agreement, team assignments) to avoid asking what is already known. If making an assumption from project context that could plausibly be wrong for this account, state the assumption and ask for confirmation rather than asking from scratch.

**Gaps to close:**

- **Account state** -- how long has the account been in its current state? Is anyone else actively working on it, or is this a cold pickup?
- **Conversion tracking** -- what does the person know about the conversion setup before looking at the screenshot? Any known issues?
- **Channels in scope** -- which channel modules apply? Search, Performance Max, Shopping, or a combination? Note that Shopping and Performance Max with a product feed share the same feed data but have different campaign structures and controls -- confirm whether one or both are running.
- **Strategic context** -- are there any active tests, recent structural changes, or client commitments that should shape the audit lens?
- **Output use** -- is this audit for internal use only, or will findings be shared with the client?
- **Out of scope** -- confirm what is explicitly not being audited in this session (e.g. ad copy, feed health, display, YouTube).

Do not ask about monthly budget, client goals, or account background if project context already covers it. Use what you know.

Once all gaps are closed, write a short alignment summary: what is being audited, why, the starting state, what done looks like, and which modules will run. Do not proceed until the user explicitly confirms.

---

## Step 3: Shared Foundations

Run these two sections for every audit regardless of channel mix. Present findings conversationally -- one section at a time. State what you can see from the data, flag what you cannot determine from the data alone, and ask the user to validate or add context before moving on.

---

### 3a. Conversion Tracking

**What to assess:**

- Total number of conversion actions in the account
- Which actions are set as Primary vs Secondary
- Whether the primary actions reflect actual business outcomes (purchases, leads, calls) or micro-events (add to carts, page views, engagements, direction requests)
- Whether purchase/lead conversion actions are tracking the correct value (full order value vs deposit only vs zero)
- Whether any conversion actions are broken, inactive, or duplicated
- The gap between Google Ads reported conversions and what GA4 or the client's own reporting shows (if known)
- Whether smart bidding campaigns are optimising toward meaningful signals or noise

**What to flag:**

- Any primary conversion actions that are not meaningful business outcomes
- Broken or inactive actions still set as primary
- Suspiciously high conversion counts that suggest micro-events are inflating the signal
- Near-zero conversion values that suggest deposit-only or broken value tracking
- Auto-applied recommendations that may have interfered with conversion setup

**Questions to ask if data does not answer them:**

- Are add-to-carts or other micro-events set as primary or secondary?
- Does the purchase conversion action track full order value, deposit value, or is it broken?
- Does the client report on GA4 numbers rather than Google Ads numbers? (This affects how a drop in Google Ads conversions post-fix should be communicated.)

**Recommendation framing:**

Lead with the commercial impact of the current setup, not the technical fix. The fix (demote junk actions, set correct primary action) is straightforward -- the important thing to communicate is what the bad setup has been doing to bid strategy learning and reported performance.

Confirm findings with the user before moving to 3b.

---

### 3b. Change History

**What to assess:**

- Date range and total volume of changes in the 90-day window
- Changes by user -- who has been active and when
- Change types -- what kinds of changes were made (negatives, bids, budgets, structural, auto-applied)
- Activity gaps -- identify any periods of more than 5 days with no human account changes
- Auto-applied recommendations -- flag any Google auto-apply changes; these should be reviewed and may need reverting
- Whether the activity level matches what would be expected for an actively managed account

**What to flag:**

- Long gaps with no human activity (flag as "effectively unmanaged" for that period)
- Patterns of purely reactive management (negatives only, bid tweaks only, no structural development)
- Auto-applied recommendations that changed copy, bids, or structure without human review
- Budget changes that suggest erratic or unplanned spend management

**Recommendation framing:**

The change history sets the context for everything else in the audit. A well-managed account with a recent gap needs a different response to an account that has been in maintenance mode for months. Frame accordingly.

Confirm findings with the user before moving to Step 4.

---

## Step 4: Channel Modules

Run only the modules that apply to this account, as confirmed in the grill-me. Run them in sequence -- Search first, then Performance Max, then Shopping. Confirm findings at the end of each section before moving to the next.

Present findings conversationally. State what the data shows, flag what it does not answer, ask the user to validate. Do not produce a wall of output -- go section by section within each module.

---

### 4a. Search Module

**Required data:** Campaign report, Search terms report.

Run these sections in order:

**i. Campaign Structure and Naming**

Assess:
- Campaign names against D4 naming convention: `D4 | Search | [Campaign Name]`
- Whether campaigns are logically structured by theme, intent, or product -- or have grown organically without a clear hierarchy
- Whether brand and non-brand campaigns are separated
- Whether any campaigns are redundant, overlapping, or serving no clear purpose
- Whether legacy paused campaigns are cluttering the account

Flag:
- Campaigns with date stamps, status descriptors, or handler initials baked into names
- Campaigns doing the same job (overlap)
- Campaigns with near-zero activity or return that have no strategic purpose
- Brand terms captured across non-brand campaigns

Recommended naming structure for reference:
```
Campaign: D4 | Search | [Campaign Name]
Ad Group: [Campaign Name] | [Ad Group Name]
```

**ii. Bid Strategies**

Assess:
- Current bid strategy per campaign and whether it is appropriate given conversion data quality
- Whether CPA or ROAS targets have been set -- and if so, whether they were calibrated against real purchase conversions or junk signals
- Whether Manual CPC is in use and why
- Whether any campaigns are on Maximise Conversion Value when purchase value tracking is unreliable

Flag:
- Smart bidding campaigns optimising toward junk conversion actions (the fix here flows from 3a)
- CPA/ROAS targets that were set against inflated conversion counts and are therefore meaningless
- Manual CPC used as a workaround for poor smart bidding performance (symptom, not cause)
- Maximise Conversion Value on accounts where value tracking is deposit-only or broken

Note: bid strategy recommendations depend on conversion tracking being fixed first. If conversion tracking is broken, all bid strategy targets are arbitrary. Frame recommendations accordingly -- fix the signal, then rebuild the targets.

**iii. Budget Distribution**

Assess:
- Daily budget per campaign and total daily spend
- Whether budget allocation reflects campaign performance and strategic priority
- Whether any campaigns are significantly over or under-funded relative to their role
- Whether budget is being wasted on campaigns with no return

Flag:
- The largest budget line going to the lowest-performing campaign
- Campaigns too underfunded to generate meaningful learning data
- Budget freed up by pausing redundant campaigns (quantify this)

Ask the user to confirm the total daily budget available before making redistribution recommendations.

**iv. Brand Term Handling**

Assess:
- Whether brand terms are captured across multiple campaigns simultaneously
- The cost and conversion volume attributable to brand terms in non-brand campaigns
- Whether a dedicated brand campaign exists and is properly isolated

Flag:
- Brand terms in non-brand campaigns inflating conversion counts and distorting CPA
- Spend on brand terms with no controlled attribution

Recommendation: brand exclusion negative lists applied to all non-brand campaigns is non-negotiable and should be treated as an immediate action regardless of whether a dedicated brand campaign is built. The brand campaign itself can follow once foundations are stable.

**v. Keyword and Search Term Coverage**

Assess:
- Whether the keyword structure covers the account's core product or service themes
- Material or type-specific terms (e.g. oak, pine, solid wood for Revival Beds) vs generic terms
- Whether high-priority product or service categories have dedicated ad groups or are lumped into catch-alls
- Conversion efficiency by term theme -- which themes are converting well vs spending without return
- Irrelevant terms still generating clicks and spend despite negative keyword work

Flag:
- Underserved term categories that are strategically important
- Disproportionate dominance of one term theme (suggests the account is effectively a single-product account)
- Poor conversion efficiency on broad match terms suggesting targeting is too loose
- Recurring irrelevant term patterns that need adding to negative lists (quantify the wasted spend)

Confirm all Search module findings with the user before moving to Performance Max.

---

### 4b. Performance Max Module

**Required data:** Campaign report. Shopping/Product report if feed-based PMAX.

Run these sections in order:

**i. Campaign Structure and Asset Groups**

Assess:
- Campaign names against D4 naming convention: `D4 | PMax | [Campaign Name]`
- Number of PMAX campaigns and whether each has a clear, distinct purpose
- Asset group structure -- whether asset groups are segmented by product type, audience, or intent
- Whether brand and non-brand signals are being managed (PMAX has no keyword control, so brand exclusions and audience signals matter more)
- Whether any PMAX campaigns are redundant or overlap with each other

Flag:
- Multiple PMAX campaigns doing the same job
- PMAX campaigns with no asset groups or with a single catch-all asset group
- PMAX competing with Search campaigns for the same traffic (particularly brand terms)
- Legacy PMAX campaigns with near-zero return kept running without review

Segmentation guidance:
- Segment by product category at campaign level where separate budget control or reporting is needed (e.g. Beds vs Wardrobes)
- Segment by product type at asset group level within a campaign where budget pools and conversion signal should be shared
- Do not over-fragment -- at low conversion volumes, consolidation preserves learning signal

**ii. Bid Strategies**

Same principles as Search -- bid strategy recommendations depend on conversion tracking being fixed first. Additional PMAX-specific considerations:

- Maximise Conversion Value is particularly damaging when purchase value tracking is deposit-only or broken -- flag this explicitly
- PMAX campaigns with no target on Maximise Conversions will spend freely toward whatever conversion signal is primary -- if that signal is junk, the campaign is ungoverned
- Target ROAS is rarely appropriate until full order value tracking is confirmed working and sufficient purchase volume exists

**iii. Budget Distribution**

Same principles as Search. Additional consideration: PMAX budget pools across all asset groups and all placements (Search, Display, YouTube, Gmail, Maps). A low daily budget starves the campaign of learning data faster than an equivalent Search budget would.

**iv. Brand Term Handling**

PMAX has no negative keyword functionality at campaign level (brand exclusions are managed via account-level brand exclusion lists or campaign-level brand exclusion settings). Assess:

- Whether brand exclusions are applied at account or campaign level
- Whether PMAX is cannibalising brand traffic from a dedicated brand Search campaign
- Whether Search Impression Share for brand terms has declined since PMAX launched

**v. Feed and Listing Group Coverage (if applicable)**

Only run this section if the account uses feed-based PMAX or Shopping.

Assess:
- Total products in feed vs eligible vs not eligible
- Not-eligible product issues (missing prices, no campaigns targeting product, disapprovals)
- Product categories with zero or near-zero clicks despite being eligible
- Whether product coverage aligns with strategic priorities (e.g. core products vs deprioritised categories)

Flag:
- High not-eligible rate (above 20% warrants investigation)
- Eligible products with zero clicks -- these are invisible in the auction
- Strategic priority products underserved by the feed
- Products in the feed that should not be advertised (deprioritised categories eating budget)

Confirm all Performance Max module findings with the user before moving to Shopping.

---

### 4c. Shopping Module

**Required data:** Campaign report, Shopping/Product report.

Shopping campaigns have keyword-free targeting like PMAX, but with direct control over product groups, bids, and feed segmentation. The audit lens is primarily feed health, campaign structure, and bid strategy -- not keywords or ad copy.

Run these sections in order:

**i. Campaign Structure and Naming**

Assess:
- Campaign names against D4 naming convention: `D4 | Shopping | [Campaign Name]`
- Number of Shopping campaigns and whether each has a clear, distinct purpose
- Whether campaigns are segmented by product category, margin tier, or priority (high vs low priority campaign structure)
- Whether brand and non-brand queries are being controlled via campaign priority settings and negative keywords
- Whether any Shopping campaigns overlap with PMAX campaigns targeting the same products

Flag:
- Multiple Shopping campaigns targeting the same products without a clear priority hierarchy
- Shopping and PMAX competing for the same products with no segmentation logic
- Legacy campaigns with near-zero return kept running without review
- Missing campaign priority settings (High/Medium/Low) if running a tiered structure

Segmentation guidance:
- High priority campaign with tight negative keyword control catches brand and high-intent queries
- Medium/Low priority campaigns catch broader traffic with less restrictive targeting
- Product group segmentation within campaigns should mirror strategic priorities -- core products in their own groups, deprioritised products excluded or in a catch-all

**ii. Bid Strategies**

Assess:
- Current bid strategy per campaign and whether it is appropriate given conversion data quality and volume
- Whether Target ROAS has been set -- and if so, whether it was calibrated against real purchase values or deposit-only values
- Whether Manual CPC is in use and why
- Whether Enhanced CPC is enabled on Manual CPC campaigns

Flag:
- Target ROAS set against deposit-only purchase values -- the target will be calibrated incorrectly
- Manual CPC used as a long-term strategy rather than a data-gathering phase
- Bid strategies that have not been reviewed since conversion tracking issues began

Same principle as Search and PMAX: bid strategy recommendations depend on conversion tracking being fixed first. If conversion tracking is broken, all ROAS targets are arbitrary.

**iii. Budget Distribution**

Same principles as Search and PMAX. Additional consideration: Shopping campaigns often run alongside PMAX campaigns targeting the same products, which can split budget inefficiently. Assess whether budget across Shopping and PMAX is being allocated deliberately or has grown organically without review.

**iv. Feed and Product Coverage**

This is the primary Shopping-specific audit area. Use the Shopping/Product report.

Assess:
- Total products in feed vs eligible vs not eligible
- Not-eligible product issues (missing prices, no campaigns targeting product, disapprovals, policy violations)
- Product categories with zero or near-zero clicks despite being eligible
- Whether product coverage aligns with strategic priorities -- core products vs deprioritised categories
- Titles and whether they include the key search terms buyers use (material, type, size, colour where relevant)
- Price competitiveness where visible -- unusually low impression share on eligible products may indicate price disadvantage

Flag:
- High not-eligible rate (above 20% warrants investigation)
- Eligible products with zero clicks -- these are invisible in the auction despite being approved
- Strategic priority products with poor impression share or zero spend
- Products in the feed that should not be advertised (deprioritised categories eating budget)
- Product titles missing key descriptors that would improve match quality (e.g. "Bed" vs "Solid Oak Four Poster Bed")

**v. Brand Term Handling**

Shopping campaigns cannot use keyword targeting but can use negative keywords to control which queries trigger them. Assess:

- Whether brand terms are being excluded from non-brand Shopping campaigns
- Whether a high-priority Shopping campaign with brand negatives exists to control brand query traffic
- Whether brand Shopping queries are being captured intentionally or accidentally

Confirm all Shopping module findings with the user before moving to Step 5.

---

## Step 5: Output -- Obsidian Markdown Document

Once all module findings are confirmed, produce a single Obsidian-compatible markdown document. Write it to `/mnt/user-data/outputs/` as `[client-slug]-ppc-audit.md`.

**Document structure:**

```
# [Client Name] PPC Audit
Date, prepared by, data period, account ID

## Context
2-3 sentences: account type, audit reason, and current state. No findings -- just enough to orient someone opening the file a week later.

## Phase 1 -- Immediate (Week 1)
## Phase 2 -- Structural (Next 30 Days)
## Phase 3 -- Dependencies
## Phase 4 -- Review Points

## Backlog
```

**Task card format:**

Each action is a checkbox task with three indented fields. No prose paragraphs. No findings narrative.

```markdown
- [ ] Short action title
  - **Issue:** One sentence. What is wrong or missing right now.
  - **Solution:** One sentence. What the fix is.
  - **Steps:** The specific things to action -- campaigns, lists, settings, owners. Enough detail to execute without reopening the audit conversation.
```

**Phase guidance:**

- Phase 1: actions executable immediately with no structural rebuild required -- negative lists, pausing redundant campaigns, conversion tracking fixes, disabling auto-apply
- Phase 2: structural changes that need planning or a short runway -- budget reallocation, campaign consolidation, bid strategy changes
- Phase 3: actions blocked on an external dependency -- clearly name the owner (dev, client, another team member) in the Steps field
- Phase 4: items to check at a future date -- state the review date or trigger condition in the Steps field

**Backlog:**

A simple bullet list (not task cards) of items identified during the audit but explicitly out of scope for this cycle. Nothing gets lost. No checkboxes -- these are not in the queue yet.

**Writing guidelines:**

- Use only findings and data confirmed through the human-in-the-loop review -- do not introduce new observations at output stage
- Every field (Issue, Solution, Steps) is one sentence or a short list -- no explanatory paragraphs
- Steps should be specific enough to action without referring back to the audit document or conversation
- Phase 3 Steps must name the dependency owner
- No em dashes anywhere in the document
- UK English throughout

Present the file to the user using `present_files` once written.

---

## Step 6: WOL Message

After the document is written, generate a Working Out Loud message following the `d4-wol` skill (tone, style, format, and output rules all apply).

**Audit-specific content to cover:**

- What was audited and over what period
- The main issues found (2-4 headline problems -- not an exhaustive list)
- What is being done about them (Phase 1 actions and any significant Phase 2 items)
- Who owns what if there are external dependencies

Do not produce a summary of every finding. The WOL is a team-facing overview of the issues and the plan -- not a condensed version of the audit document.
