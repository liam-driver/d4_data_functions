---
name: ppc-shopping-feed-audit
description: "Run a structured Google Shopping feed audit from a raw CSV export. Use this skill whenever a user uploads a product feed CSV, asks to audit or review a shopping feed, wants to check feed quality before going live in Merchant Centre, or says anything like 'can you look at this feed', 'audit the shopping feed', 'what's wrong with the feed', or 'let's fix the product feed'. Covers the full workflow: ingest CSV, grill-me session to establish context, run Python analysis against a priority hierarchy, produce an interactive audit report, discuss findings with the user, generate a concise actions list, then WOL. Always use this skill for Shopping feed work even if the user only mentions one part of the workflow."
---

# PPC Shopping Feed Audit

A step-by-step workflow for auditing a Google Shopping or Performance Max product feed from raw CSV export to a prioritised, agreed actions list. Works across any account type and any feed source.

---

## Workflow Overview

```
Feed Audit
├── Step 1: Feed Ingestion
├── Step 2: Grill-Me
├── Step 3: Python Analysis (against priority hierarchy)
├── Step 4: Audit Report Widget
├── Step 5: Discussion
├── Step 6: Actions List
└── Step 7: WOL
```

Do not skip steps or combine them. Each step requires confirmation before moving to the next.

---

## Step 1: Feed Ingestion

Before touching the data, read any available client project context (Client_Context file or CLAUDE.md). Extract and hold in memory:
- Product range (what the client sells, primary categories, any products NOT in scope)
- Brand positioning (quality/premium vs budget vs niche)
- Known material or variant dimensions (e.g. Oak vs Pine, colour options)
- Named competitors
- Whether the account uses Shoptimised, and whether a Google Sheets supplemental feed is already in place
- Any active tests or campaigns that depend on feed segmentation

If no project context exists, note this and proceed — the grill-me session will gather what is needed.

**Reading the feed:**
Use pandas with `nrows=5` first to inspect structure. Then load the full file. Do not blindly `cat` the CSV.

```python
import pandas as pd
df = pd.read_csv('/mnt/user-data/uploads/feed.csv', nrows=5)
# Inspect columns and shape, then load full file
df = pd.read_csv('/mnt/user-data/uploads/feed.csv')
```

Confirm the feed shape to the user with a short message only — do not begin analysis yet:

> "Feed read — [N] products across [N] product groups. Looks like a [WooCommerce/Shopify/custom] export. Before I run the audit, I have a few questions."

Then move immediately to Step 2.

---

## Step 2: Grill-Me

Run the `/grill-me` skill. The gaps to close for a feed audit are:

- **Campaign types** — is this feed feeding Shopping, Performance Max, or both?
- **Active tests** — are there any live or planned ad tests that depend on feed-level segmentation (e.g. material-specific campaigns, product category splits, price tier bidding)?
- **Known issues** — are there any known problems with the feed or account already on the radar?
- **Out of scope products** — are there any products in the feed that should NOT be advertised (discontinued lines, categories being held back, products in development)?
- **Toolchain** — is Shoptimised already in use for this feed? Is a Google Sheets supplemental feed already active?

Ask one question at a time. Do not list all questions upfront. Use project context to avoid asking what you already know.

Once the grill-me session is complete, confirm before proceeding:

> "Thanks — running the full audit now."

---

## Step 3: Python Analysis

Run ALL of the following checks. Do not skip checks because a field is absent — absence is itself an issue. Apply the **Priority Hierarchy** below when scoring and ordering findings.

**3.1 Feed Shape**
- Total rows
- Unique item_group_ids (product groups)
- Parent rows vs variant rows (rows without "attribute" in the link URL are typically parent/base rows)
- Distribution of products by custom_label_0 or product category

**3.2 Critical Field Completeness (% populated)**
Check all of these and report the % non-null:
- `id`, `title`, `description`, `price`, `availability`, `condition`
- `brand`
- `image_link`, `link`
- `product_type`, `google_product_category`
- `gtin`, `mpn`, `identifier_exists`
- `color`, `material`, `size`
- `item_group_id`
- `custom_label_0` through `custom_label_4`
- `sale_price`, `shipping`

**3.3 Brand Field**
- Is brand populated for all rows?
- Is brand set to a numeric value (e.g. "0.0") indicating a plugin default rather than actual brand name?
- Does brand match the client's actual brand name?

**3.4 Google Product Category**
- Is `google_product_category` populated?
- If not, can it be derived from `product_type` or `custom_label` values?
- Map suggested Google taxonomy IDs based on detected product types

**3.5 Title Analysis**
```python
dup_mask = df['title'].str.contains(' - ', na=False)
for kw in ['Oak', 'Pine', 'Solid', 'Wood', 'Handmade', 'UK', 'King', 'Double', 'Single']:
    count = df['title'].str.contains(kw, case=False, na=False).sum()
```
- Average title length (ideal: 70-150 chars)
- Titles over 150 chars
- Duplicate titles across the feed
- Titles following a "Name - Name" duplication pattern (common WooCommerce plugin issue)
- Key differentiators present in titles: material, size, brand qualifiers
- Titles under 30 chars

**3.6 Description Analysis**
- Average description length
- Descriptions under 100 chars (Google allows up to 5,000 — short descriptions reduce query matching surface)
- Whether descriptions vary across variants of the same product group, or are identical

**3.7 Price Analysis**
```python
df['price_clean'] = df['price'].str.replace(' GBP','').str.replace(' USD','').astype(float, errors='ignore')
```
- Price range overall and by category
- Products with price = 0 or missing
- Whether price varies across variants within the same item_group_id (if all identical, flag as worth confirming)

**3.8 Availability**
- Values present (in stock, out of stock, preorder)
- Out-of-stock products included in the feed with no exclusion rule
- Out-of-stock products with no price

**3.9 Identifier Fields**
- `identifier_exists` value distribution
- Products with `identifier_exists: no` AND blank brand (worst-case combination)
- Any GTINs or MPNs present?

**3.10 Variant Structure**
- Item groups with only 1 variant (potentially a parent row rather than a true variant)
- Item groups with 8+ variants (check for size coverage)
- Whether size, color, or material are used as variant dimensions in any title or attribute field

**3.11 Image Analysis**
- Image link completeness
- HTTP vs HTTPS URLs
- Additional images present (avg count per product)
- Image URLs with spaces or special characters

**3.12 Custom Labels**
- Which custom_label fields are populated vs empty
- What values are in use (value_counts for each populated label)
- Whether labels are being used strategically (material, AOV band, margin tier, product type) vs just category name
- How many custom_label slots remain unused

**3.13 Product Type**
- Are product_type values present?
- Last node analysis — is the most specific node actually useful?
- Products appearing in multiple conflicting taxonomy paths

**3.14 Shipping**
- Is the `shipping` field populated?
- If not, flag that account-level GMC shipping settings must be confirmed

---

## Priority Hierarchy

This hierarchy is a fixed Door4 standard agreed with the PPC team. It is not generated by AI reasoning. Apply it when scoring and ordering every issue found. **Performance Max items carry higher weight than Shopping-only items** because PMax is used more frequently across Door4 accounts.

---

### Tier 1: Feed Integrity — Fixed Order, Non-Negotiable

These items are always addressed first, in this exact sequence, regardless of what the grill-me session reveals. They cause disapprovals, break auction eligibility, or make the feed unreadable by Google.

| # | Check | Why it matters |
|---|-------|----------------|
| 1 | Product identity — brand, GTIN/MPN, identifier_exists | Google needs to know what the product is before anything else. Blank brand + no GTIN + identifier_exists: no is the worst possible combination. Brand is almost always a plugin default issue and is almost always fixable immediately. |
| 2 | Availability accuracy | Out-of-stock products serving ads wastes budget and harms account quality scores. In-stock products marked unavailable lose impressions entirely. Check both directions. |
| 3 | Price accuracy and completeness | Missing prices cause immediate disapprovals. Prices that do not match the landing page cause policy violations. For made-to-order products, verify the deposit vs full price question is handled correctly. |
| 4 | Image link validity | Broken or missing image links cause disapprovals. HTTP images are rejected. Images with spaces or special characters in the URL frequently fail. No image = no ad. |
| 5 | Landing page URL validity and variant routing | Dead links or links that land on a parent product page rather than the specific variant create a poor experience and policy risk. Variant rows should route to the correct variant URL. |
| 6 | Parent row contamination | Parent/base product rows competing alongside their own variants splits impressions and inflates auction costs. In most setups, parent rows should be excluded from the active feed. |

---

### Tier 2: Query Matching and Relevance — Context-Sensitive Ordering

These items directly affect which searches the feed appears for. Poor performance here means spend on the wrong queries, or no impressions for the right ones. The grill-me session may elevate specific items — for example, if a material-based ad test is live, item 10 moves to the top of this tier.

| # | Check | Why it matters | PMax relevance |
|---|-------|----------------|----------------|
| 7 | Title quality — structure, differentiators, keyword signals | Single highest-impact optimisation field. Titles drive query matching in Shopping and asset quality in PMax. Must include brand or material signal, product type, key variant dimension. Duplication patterns waste half the title. | High |
| 8 | Google product category mapping | Google uses this to route products to the right auction. Missing or incorrect taxonomy IDs mean Google guesses — often wrong for niche categories. Critical for PMax asset group organisation. | High |
| 9 | Description quality and length | Used for query matching and PMax asset scoring. Short descriptions reduce long-tail match surface. Should include material, key features, and use cases — not just a rephrased title. | High |
| 10 | Material, colour, and size attributes | Explicit attribute fields improve matching for filtered and faceted searches. Required for campaign segmentation if material-based ad tests are active. | High |
| 11 | Product type taxonomy depth and accuracy | Used alongside google_product_category for routing. Deep, accurate product_type paths give Google more signal. Watch for WooCommerce paths that list every possible category rather than the most specific one. | Medium |

---

### Tier 3: Bid Strategy and Campaign Control — Context-Sensitive Ordering

These items will not break the feed or kill impressions, but leave significant efficiency headroom on the table. Only flag these if the account has the campaign structure to act on them.

| # | Check | Why it matters | PMax relevance |
|---|-------|----------------|----------------|
| 12 | Custom label strategy — price tier, margin, material, seasonality | Custom labels are the primary mechanism for bid segmentation in Shopping and asset group organisation in PMax. Unused labels are unused levers. Standard useful labels: price band, product category, material, margin tier, seasonal priority. | High |
| 13 | Additional images — quantity and quality | PMax uses additional images as creative assets across Display, YouTube, and Demand Gen. More high-quality images increases asset coverage and ad variation. Minimum 3 additional images per product group. Lifestyle images weighted higher than product-on-white. | High — PMax only |
| 14 | Shipping data completeness | Only a problem if account-level GMC shipping settings are not configured. Always verify at account level before treating as a feed issue. When shipping is feed-level, it enables shipping annotations in ads. | Low |
| 15 | Sale price and promotion fields | Sale price annotations require both sale_price and sale_price_effective_date. Without effective_date, Google ignores the sale price. Only relevant during active promotional periods. | Medium |

---

**Context-sensitivity rule:** If the grill-me session reveals that a Tier 2 or Tier 3 item is directly blocking a live test or campaign strategy, elevate it in the Issues widget and state why. Tier 1 order is never changed.

---

## Step 4: Audit Report Widget

Build using the Visualizer tool. The widget must have two tabs.

**Tab 1 — Issues**

Header stats bar (4 metric cards):
- Total products in feed
- Critical issues count (red)
- Medium issues count (amber)
- Product groups count

Legend row: fix layer colour key (Shoptimised = blue, Sheets supplemental = green, WooCommerce = amber, Dev = red)

Issues list — grouped by severity, ordered by the priority hierarchy within each group. Each issue row contains:
- Issue number (from the hierarchy where applicable)
- Severity badge (C / M / L)
- Issue title
- Issue detail — specific counts and context from the Python analysis
- Fix layer tag (colour-coded)
- Where a Tier 2 or 3 item has been elevated due to grill-me context, a short note explaining why

**Tab 2 — Fix Workflow**

Grouped by fix layer, ordered by priority:
- Shoptimised rules — immediate, no external dependency
- Sheets supplemental feed — immediate, requires content work
- Confirm before acting (Dev / client) — questions that must be answered first

Each workflow step contains a step number (circle), step title, and a detail line with specific rule logic or question to ask directed at the right person.

**Design conventions:**
- Severity badges: C (red background), M (amber background), L (gray background)
- Fix layer tags: colour-coded pills — Shoptimised (blue), Sheets supplemental (green), WooCommerce (amber), Dev (red)
- Stat cards: `var(--color-background-secondary)` background, no border
- Issue rows: `border-bottom: 0.5px solid var(--color-border-tertiary)`
- Workflow steps: numbered circles, `var(--color-background-info)` fill, `var(--color-text-info)` text
- No em-dashes in widget text
- UK English throughout

---

## Step 5: Discussion

After the widget, do NOT produce the actions list. Invite the user to review and push back first:

> "That is the full picture. Before I pull together the actions list, does anything here look wrong, already in progress, or lower priority than the analysis suggests?"

This is a genuine back-and-forth. The user may tell you:
- Some issues are already being worked on (remove from actions)
- Some apparent issues are intentional (e.g. identical prices across variants is correct for this client)
- Some Tier 3 items should be elevated due to account context not covered in the grill-me
- The fix layer for a specific item is wrong (e.g. they use a different tool than Shoptimised)

Update your understanding based on this conversation. Do not proceed to Step 6 until the user signals they are ready. If the user requests changes to how issues are categorised or prioritised, acknowledge and confirm before proceeding.

---

## Step 6: Output -- Obsidian Markdown Document

Once the user confirms the discussion is complete, produce a single Obsidian-compatible markdown document. Write it to `/mnt/user-data/outputs/` as `[client-slug]-feed-audit.md`.

**Document structure:**

```
# [Client Name] Shopping Feed Audit
Date, prepared by, feed source, product count

## Context
2-3 sentences: feed source, campaign types it feeds, and current state. No findings -- just enough to orient someone opening the file a week later.

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
  - **Steps:** The specific things to action -- fields, rules, tool, owner. Enough detail to execute without reopening the audit conversation.
```

**Phase guidance -- mapping from fix layers to phases:**

- Phase 1: Shoptimised rules that can be implemented immediately with no structural rebuild required -- brand field fix, google_product_category mapping, parent row exclusion, OOS product exclusion, shipping rule
- Phase 2: Work that requires effort or planning -- title rewrites via Sheets supplemental feed, description improvements, custom label strategy rebuild
- Phase 3: Actions blocked on an external dependency -- clearly name the owner (dev, client, another team member) in the Steps field. This is where all "confirm before acting" items land.
- Phase 4: Items to check at a future date -- state the review date or trigger condition in the Steps field (e.g. "Review once Oak/Pine variation structure is confirmed by dev")

**Backlog:**

A simple bullet list (not task cards) of Tier 3 items identified during the audit but explicitly out of scope for this cycle. Nothing gets lost. No checkboxes -- these are not in the queue yet.

**Writing guidelines:**

- Use only findings confirmed through the discussion step -- do not introduce new observations at output stage
- Every field (Issue, Solution, Steps) is one sentence or a short list -- no explanatory paragraphs
- Steps should be specific enough to action without referring back to the audit conversation
- Phase 3 Steps must name the dependency owner
- Hierarchy tier numbers can be referenced in task titles for traceability (e.g. "T1.1 -- Fix brand field")
- No em dashes anywhere in the document
- UK English throughout

Present the file to the user using `present_files` once written.

---

## Step 7: WOL

After the document is written, generate a Working Out Loud message following the `/wol` skill (tone, style, format, and output rules all apply).

**Feed audit-specific content to cover:**

- What was audited and what it feeds (Shopping, PMax, or both)
- The main issues found (2-4 headline problems -- not an exhaustive list)
- What is being done about them (Phase 1 actions and any significant Phase 2 items)
- Who owns what if there are Phase 3 dependencies

Do not produce a summary of every finding. The WOL is a team-facing overview of the issues and the plan -- not a condensed version of the audit document.

---

## Fix Layer Reference

| Fix layer | Output phase | When to use |
|-----------|-------------|-------------|
| Shoptimised rule | Phase 1 | Field can be populated or corrected using data already in the feed (brand, google_product_category, exclusion rules, custom labels, shipping) |
| Sheets supplemental feed | Phase 2 | Requires content rewriting Shoptimised cannot handle natively -- primarily titles and descriptions |
| WooCommerce / plugin | Phase 2 or 3 | Needs fixing at source in the CMS or feed plugin config (description length, pricing data, variant structure) |
| Dev / confirm first | Phase 3 | Requires a question answered by the development team or client before the fix can be defined |

---

## Important Caveats — Always Apply

1. Shipping: if the shipping field is empty, always confirm GMC account-level shipping settings before treating it as a disapproval risk.
2. GTIN/MPN: for made-to-order or bespoke products, `identifier_exists: no` is often correct. Flag it but do not recommend adding fake GTINs.
3. Parent rows: confirm exclusion of parent rows only where it is safe to do so — some feed setups intentionally include parent rows for specific campaign structures.
4. Price variation: before flagging all-same-price variants as an error, confirm with the client — many brands genuinely charge the same price regardless of size or variant.
5. Do not treat every absent field as a critical issue — apply the hierarchy and only escalate absences that directly affect Tier 1 and Tier 2 checks.
