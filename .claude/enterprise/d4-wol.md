---
name: wol
description: When the user asks for a WOL message, generate a Working Out Loud update summarising the work completed in the current conversation. Output in chat only — Slack is used for tone context, not for sending.
---

## What is a WOL

A Working Out Loud message is a brief, casual Slack update posted to the internal team channel after completing a task or piece of client work. It keeps the team informed of what's been done without being a formal report. It reads like a human wrote it mid-flow — not polished corporate copy, not bullet points, not AI output.

---

## How to generate a WOL

### Step 1: Pull Slack context

The client's internal Slack channel is specified in the project context. Use the Slack MCP to fetch the last 10 messages from that channel (excluding bot messages and very short messages under 20 characters). Use these to calibrate tone — match the register your team actually uses, not a generic "professional" voice.

### Step 2: Build the message

Draw on three sources:
- **Conversation history** — what was actually done, discussed, and decided in this chat
- **Project context** — client name, account background, goals, and any standing context from the project documents
- **Slack history** — tone calibration and any live context (blockers, decisions, strategy) that is relevant to mention

Construct the message around these elements, in order of relevance:

1. **What you did** — the task or piece of work completed
2. **Why** — the rationale or strategic reason behind it (only include if non-obvious)
3. **Current state** — what's live, paused, running, or pending as a result
4. **Next steps** — concrete actions coming up (only include if there are clear next steps worth flagging)

Not every WOL needs all four. If there's no meaningful "why" or no clear next steps, leave them out. Don't pad.

### Step 3: Output

Output the message directly in the chat window — no explanation, no preamble, no "here's your WOL." Just the message, ready to copy-paste into Slack. Do not send the message to Slack or any other channel. The Slack MCP is used only to fetch context in Step 1, never to post.

---

## Tone and style

- First person, past tense for what was done
- Casual and direct — write like a competent person talking to colleagues, not a copywriter
- Slightly more considered than a pure stream of consciousness, but still natural
- Specific: name the client, the platform, the campaigns, the numbers where relevant
- British English
- Plain flowing prose by default, but headers and bullet points are fine if they make the message more readable and glanceable
- Keep it skimmable — a colleague scanning Slack should immediately understand what's happening in the account
- Never use em dashes (—). Rewrite the sentence if needed. Em dashes read as AI output and will cause people to tune out.
- Length: 3–6 sentences is the target. Long enough to be informative, short enough to be skimmable

---

## Example register (for tone calibration only — do not copy structure)

> With us cycling out a lot of assets, i've gone ahead and created an advantage+ campaign for facebook which will house the assets we've gone ahead and paused. We are moving quite quickly with the assets since we have so many, and at the moment we are only keeping the ones that are hitting the ground running. While this will work for the majority of cases, there may be some exceptions where assets that started poorly have another chance to squeeze out some more value. Have put this live at a £20 per day budget, and will keep a close eye on it.

> Been building out Google Ads brand campaigns for defib today — 7 brands in total. Each campaign follows the same structure: 4 ad groups per brand, each with an RSA built around brand-specific and generic store-level headlines. I've also paused the ad groups in the campaigns that referenced these brands, so one element of the search overlap has been addressed. Next steps are to get the other brands into the catch all campaign, then tidy up the generics campaigns to remove the remaining overlap.
