---
name: ppc-search-query-report
description: "Run a structured Google Ads search query report (SQR) analysis and build a themed negative keyword list with match type recommendations. Use this skill whenever a user uploads a search terms CSV, asks to review search queries, wants to build or update a negative keyword list, or says anything like 'can we do a search query report', 'let's review the search terms', 'build me a negatives list', or 'clean up the account'. Covers the full workflow: ingest CSVs, infer campaign types, identify negative keyword themes, clarify scope with the user, then output confirmed negatives as an inline code block in chat. Always use this skill for SQR and negative keyword work even if the user only mentions one part of the workflow."
---

# PPC SQR and Negative Keywords Skill

## Overview

This skill covers the full workflow from raw Google Ads search terms export to a reviewed, paste-ready negative keyword list. It is designed for use across any Google Ads client account.

**Workflow:**
1. Ingest CSVs and infer campaign types
1b. Optionally ingest existing negative keyword lists
2. Run lightweight Python categorisation to identify themes
3. Present identified themes in Markdown with brief justification
4. Ask clarifying questions before building negatives
5. Build themed negative lists in Markdown — confirm with user before proceeding
6. Output confirmed negatives as an inline code block in chat

---

## Step 1 — Client context and CSV ingestion

Before touching the data, read any available client project context (Client_Context file or CLAUDE.md). Extract and hold in memory:
- Product range (what the client sells and does NOT sell)
- Brand positioning (premium, budget, niche, etc.)
- Known vehicle fitments or category constraints
- Any named competitors
- Whether the client is D2C or sells via third-party retailers

If no project context exists, note this and proceed — the analysis will be more generic.

**CSV handling:**
Google Ads search terms exports typically have 2 header rows before the data. Load with `skiprows=2`. Strip Total/summary rows (rows where Search term starts with "Total:"). Confirm the inferred campaign type with the user before proceeding — e.g.:

> "I've read two files. Based on the search terms, I'm reading file 1 as a vehicle-specific campaign and file 2 as a generic category campaign. Does that look right?"

---

## Step 1b — Existing negative keyword lists (optional)

After confirming the campaign types, prompt the user to upload any existing negative keyword lists from the account:

> "Do you have any existing negative keyword lists you'd like to share? If so, upload them now and I'll use them to build on what's already in the account rather than starting from scratch."

This step is optional — if the user has no lists, proceed to Step 2.

**If lists are provided:**
- Parse the existing negatives and hold them in memory, noting which themes and match types are already covered
- During Step 5, cross-reference all candidate negatives against the existing lists to avoid duplication
- In the themed negatives list, distinguish between:
  - **New additions** — terms not already in any list
  - **Already covered** — terms that exist in the current lists (surfaced for visibility but not added again)
- Favour extending existing themed lists over creating new ones where the theme already has coverage
- Note which existing list each addition should be appended to

**Accepted formats:** .txt, .csv, or pasted text. If the user pastes raw negatives, infer match type from formatting (quoted = phrase, bracketed = exact).

---

## Step 2 — Lightweight Python categorisation

Run categorisation filters across all uploaded CSVs to identify which of the 7 standard themes have candidates. The goal is theme identification only — no metric tables, no per-campaign breakdowns.

**Categorisation filters:**

| Theme | Filter logic |
|-------|-------------|
| Wrong product category | Terms referencing product types outside the client's range (use client context) |
| Local / retail intent | Terms containing "near me", fitter names, named retailers, collection/fitting language |
| Price-shopping / bargain intent | Terms containing "cheap", "for sale", "second hand", marketplace names (eBay, Amazon, etc.) |
| Competitor brands | Terms containing named competitors from client context |
| Non-UK / foreign language | Non-English terms; US/international spellings where UK variant is clearly preferred |
| No purchase intent / junk queries | Informational, DIY, or research-only queries with no commercial signal |
| Wrong vehicle / product type | Terms referencing vehicle makes, models, or product variants the client does not cover |

For each theme, count the number of candidate terms found. Hold the candidate lists in memory — they feed directly into Step 5.

---

## Step 3 — Present themes in Markdown

Present the populated themes as a short Markdown summary. Only include themes that have candidates — skip empty ones. For each theme, give a one-liner reason and the candidate count.

**Format:**

```
## Identified themes

**Local / retail intent** — 14 candidates
Terms like "near me", "fitter", and named retailers suggest users looking for in-person purchase or fitting, not online.

**Price-shopping / bargain intent** — 9 candidates
Queries including "cheap", "second hand", and marketplace names indicate low purchase intent for a premium product.

**Wrong product category** — 6 candidates
Several queries reference product types outside the client's range based on their product list.

...
```

Keep it brief. No tables, no per-term lists at this stage — just enough to show which themes have material and why.

---

## Step 4 — Negative keyword clarification questions

Before building the negatives list, ask at minimum:

1. Which campaigns should negatives apply to? (per-campaign, both, or account-level)
2. Should match type recommendations be included?

Use the `ask_user_input_v0` tool for these — one question at a time, presented as selectable options. Do not ask about things already clear from the data or client context.

---

## Step 5 — Build the themed negatives list

Present the negatives organised by theme in Markdown before generating the output. Standard themes — always walk through all populated ones:

| # | Theme | Scope |
|---|-------|-------|
| 1 | Wrong product category | Both campaigns |
| 2 | Local / retail intent | Both campaigns |
| 3 | Price-shopping / bargain intent | Both campaigns |
| 4 | Competitor brands | Both campaigns |
| 5 | Non-UK / foreign language | Both campaigns |
| 6 | No purchase intent / junk queries | Both campaigns |
| 7 | Wrong vehicle / product type | Campaign-specific |

Use `##` headers per theme, with terms listed as bullets. If match types were requested, include them inline (e.g. `"near me" [Phrase]`).

**Theme 7 handling:**
If client context provides a product range or vehicle fitment list, use it to populate theme 7 and flag any terms that need client confirmation before adding. Mark these clearly as "PENDING [CONTACT NAME] CONFIRMATION" inline. Do not hold back terms that are unambiguously wrong — only flag those where fitment is genuinely uncertain.

**Match types:**
**Broad match negatives are never used — Exact and Phrase match only.**

If the user requested match type recommendations, apply this logic:
- Intent-based negatives (local, price-shopping, junk queries): Phrase match — these need to block pattern variants
- Product category terms: Default to Exact match — phrase match risks blocking legitimate queries with overlapping language. If the user overrides this, honour the override
- Competitor brands: Phrase match
- Foreign language terms: Phrase match for observed terms, Exact match for single-word terms
- Campaign-specific vehicle/product terms: Exact match

**Conditional terms:**
Always separate confirmed terms from terms needing client verification. Flag conditionals clearly with the reason (e.g. "Confirm vehicle fitment before adding").

**Confirmation gate:**
After presenting the themed negatives list, always ask explicitly:

> "Are you happy with this list, or are there any terms you want to add, remove, or move between themes before I generate the final output?"

Do not proceed to Step 6 until the user has confirmed the list is good to go. If they request changes, update the list and ask again. Only move to Step 6 once explicit approval is given.

---

## Step 6 — Inline negatives output

Once the user confirms the negatives list, render the negatives directly in chat as a fenced code block. No file is created.

**Format:**

One term per line, grouped by theme with a comment header. If match types are included, use Google Ads formatting conventions: `"quoted"` for phrase match, `[bracketed]` for exact match.

```
# Wrong product category
[term one]
[term two]
"term three"

# Local / retail intent
"near me"
"fitter"
...
```

If conditional terms are present, append them at the end under a `# PENDING CONFIRMATION` comment so they are easy to locate and remove before uploading.
