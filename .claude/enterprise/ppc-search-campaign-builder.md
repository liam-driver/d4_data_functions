---
name: google-search-campaign-builder
description: Build a Google Search campaign from brief to ready-to-enter ad copy. Use this skill whenever a user wants to build, plan, or structure a new Google Search campaign — including when they mention keywords, ad groups, RSAs, headlines, descriptions, or say things like "let's build a campaign", "I need a search campaign for X", or "prep a campaign ready for launch". This skill covers the full workflow from brief to keywords to negatives to copy to extensions to WOL. Always trigger this skill for new Google Search campaign builds, even if the user only mentions one part of the workflow.
---

# Google Search Campaign Builder

A step-by-step workflow for building a new Google Search campaign from brief to launch-ready ad copy. Works across any account type — ecommerce, lead gen, B2B, local, or otherwise.

---

## Workflow Overview

```
Campaign
├── Step 1: Brief
├── Step 2: Grill-Me (shared alignment)
├── Step 3: Campaign Summary (tree structure)
├── Step 4: Keywords
├── Step 5: Negative Keywords
├── Step 6: Ad Copy (RSAs)
├── Step 7: Ad Extensions
└── Step 8: WOL
```

Do not skip steps or combine them. Each step requires confirmation before moving to the next.

---

## Step 1: Brief

Accept whatever the user provides — landing page URLs, product or service info, existing creative exports, keyword planner data, or a rough description. Do not start the grill-me until the brief is in.

If the user uploads files (keyword planner CSVs, existing ad copy exports), read them before proceeding. Extract:
- Keywords worth using (filter out irrelevant or unserviceable terms)
- Any existing copy patterns worth adapting

---

## Step 2: Grill-Me

Run the `/grill-me` skill. The gaps to close for a campaign build are:

- **Goal** — what is the campaign trying to achieve? (purchases, leads, calls, sign-ups, etc.)
- **Landing page(s)** — URL(s) for each ad group destination. Are they live or TBC?
- **Ad group structure** — how many ad groups, what intent or theme does each serve?
- **Budget** — daily budget confirmed before moving on
- **Bid strategy** — Max Conversions / Max Clicks to start, or Target ROAS/CPA if conversion history exists?
- **Key selling points / USPs** — what should the copy lead with?
- **Prices or offers** — any specific figures to call out?
- **Brand and competitor terms** — should the client's own brand terms and/or competitor terms be excluded from this campaign?

Ask one question at a time. Do not list all questions upfront. Use project context to avoid asking what you already know.

---

## Step 3: Campaign Summary (Tree Structure)

Once alignment is confirmed, output a campaign summary in tree structure format before any keywords or copy is written.

**Naming conventions:**
- Campaign: `D4 | {Campaign Type} | {Campaign Name}` — e.g. `D4 | Search | Motorbikes`
- Ad Groups: `{Campaign Name} | {Ad Group Name}` — e.g. `Motorbikes | Touch Up Pen`

**Format:**
```
Campaign: D4 | Search | [Campaign Name]
├── Config
│   ├── Goal: [e.g. Purchases / Lead gen / Calls]
│   ├── Bid strategy: [e.g. Maximise Conversions]
│   ├── Daily budget: [e.g. £50/day]
│   └── Status at launch: Paused
│
├── Ad Group: [Campaign Name] | [Ad Group Name]
│   └── URL: [Final URL or TBC]
│
├── Ad Group: [Campaign Name] | [Ad Group Name]
│   └── URL: [Final URL or TBC]
│
└── Ad Group: [Campaign Name] | [Ad Group Name]
    └── URL: [Final URL or TBC]
```

Ask the user to confirm the structure before proceeding to keywords.

---

## Step 4: Keywords

Output keywords per ad group in plain list format with match type wrappers only — no tables, no inline commentary. Use:
- `[exact match]` — square brackets
- `"phrase match"` — quote marks
- `broad match` — no wrapper

**Rules:**
- Use exact match for the highest-intent, highest-specificity terms
- Use broad match for thematic or intent-level terms where the bid strategy and search terms report can do the work
- Do not over-keyword — quality over quantity

**Format:**
```
**Ad Group: [Name]**
[keyword one]
[keyword two]
keyword three

**Ad Group: [Name]**
[keyword one]
keyword two
```

Validate that no keyword exceeds 80 characters (Google Ads limit). Flag any that are borderline.

Confirm keywords with the user before moving to negatives.

---

## Step 5: Negative Keywords

This is a standalone step — not an appendage to the keyword list. Build a two-layer negative list:

**Layer 1 — Universal seed list**
Apply these to every campaign as a starting point:

```
[free]
[jobs]
[careers]
[how to]
[tutorial]
[course]
[training]
[DIY]
[wiki]
[wikipedia]
[pdf]
[download]
what is
near me
```

Review the universal list against the account context — remove any that are legitimately relevant (e.g. "near me" may be valid for a local business).

**Layer 2 — Campaign-specific negatives**
Derived from:
- The grill-me (brand/competitor exclusions confirmed there)
- The keyword planner data or brief (unserviceable terms, wrong product types, wrong audience)
- Common sense filtering for the category

Output both layers together, formatted the same way as the keyword lists — plain list with match type wrappers, split by campaign-level and ad group-level where relevant.

Confirm negatives with the user before moving to ad copy.

---

## Step 6: Ad Copy (RSAs)

Output one RSA per ad group. Use separate tables for headlines and descriptions.

**Character limits — hard limits, never exceed:**
- Headlines: 30 characters maximum
- Descriptions: 90 characters maximum

**Before outputting any copy, validate every headline and description programmatically using bash_tool:**

```python
for h in headlines:
    assert len(h) <= 30, f"FAIL: {len(h)} chars — {h}"

for d in descriptions:
    assert len(d) <= 90, f"FAIL: {len(d)} chars — {d}"
```

Do not output copy that fails validation. Rewrite until it passes.

**Format per ad group:**

Final URL: [URL]
Path 1: [slug] / Path 2: [slug]

**Headlines**

| # | Headline | Chars |
|---|----------|-------|
| 1 | Headline text | 00 |
| ... | ... | ... |
| 15 | {keyword:Fallback Text} | 00 |

**Descriptions**

| # | Description | Chars |
|---|-------------|-------|
| 1 | Description text | 00 |
| 2 | Description text | 00 |
| 3 | Description text | 00 |
| 4 | Description text | 00 |

**Copy guidance:**
- 15 headlines per RSA, 4 descriptions per RSA
- Use at least one keyword insertion headline — format: `{keyword:Fallback Text}` where fallback is under 30 chars
- Lead with the strongest USPs identified in the grill-me — do not default to generic filler
- Differentiate ad groups from each other — each ad group's copy should reflect its specific theme or intent
- No em dashes anywhere in copy
- Match the language register of the account (B2B copy reads differently to consumer ecommerce)
- UK English unless the account targets another market

Confirm copy with the user before moving to extensions.

---

## Step 7: Ad Extensions

Output recommended extensions for the campaign. Validate character limits programmatically before outputting — same approach as RSAs.

**Character limits:**
- Sitelink text: 25 characters maximum
- Sitelink descriptions: 35 characters each
- Callout text: 25 characters maximum
- Structured snippet values: 25 characters each

**Sitelinks** (minimum 4)

| # | Sitelink Text | Description 1 | Description 2 | URL |
|---|---------------|---------------|---------------|-----|
| 1 | | | | |

**Callouts** (minimum 4)

| # | Callout Text |
|---|--------------|
| 1 | |

**Structured Snippets**

| Header | Values |
|--------|--------|
| [e.g. Services] | Value 1, Value 2, Value 3 |

Base extension recommendations on USPs and context from the grill-me — do not use generic placeholder copy. Choose the structured snippet header that best fits the account (Services, Products, Brands, etc.).

Confirm extensions with the user before moving to WOL.

---

## Step 8: WOL

Run the `/wol` skill once the campaign is confirmed as done.

Key details to include in the WOL:
- Campaign added paused
- Ad groups built and what each targets
- Any ad groups blocked on dependencies (e.g. landing pages TBC) — reference the Scoro task URL if provided
- Bid strategy and daily budget
- What needs to happen before it goes live
