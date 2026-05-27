---
name: grill-me
description: Interview the user relentlessly about a task until reaching shared understanding, resolving each branch of the decision tree. Use at the start of a conversation when the user wants to align before starting work.
---

Interview me relentlessly about every aspect of this task until we reach shared understanding. Walk down each branch of the decision tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask questions one at a time.

Before asking anything, read the client's project context — CLAUDE.md and any context files — to establish what is already known about the client, platform, KPIs, account structure, and objectives. Do not ask about what project context already covers. If you are making an assumption from project context that could plausibly be wrong for this specific task, state the assumption and ask me to confirm rather than asking from scratch.

Start with one open question: what are we working on?

Branch from there. The gaps to resolve are:
- **Current state** — what is live, broken, or in place right now
- **Desired outcome** — what does done look like, specifically
- **Constraints** — budget, timeline, platform rules, or anything that limits the approach
- **Scope** — what is in and out of scope

Keep going until every branch of the decision tree is resolved.

Then write a short summary: what we are doing, why, the starting state, what done looks like, and the approach. Do not start work until I explicitly confirm.
