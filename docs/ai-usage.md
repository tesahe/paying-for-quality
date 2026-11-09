# AI Usage

How I use AI tools on this project, what I keep, change or reject, and how AI-assisted work is verified. I don't keep full conversation histories here.

## Tools

- Claude Code (Anthropic), run as a single agent under the rules in `AGENTS.md`.

## Sprint 1 Log

| Area | What I had the AI do | My direction and decisions | Verification |
|---|---|---|---|
| Project switch and scope | Read the course instructions and compare my draft scope against the remaining sprint deadlines | I chose the topic and the research question. I moved from my earlier placeholder project to this one in a new repository, as agreed with the instructor | Deadlines and required documents checked against the Canvas pages in `class-instructions/` |
| Baseline files | Draft `AGENTS.md`, `.gitignore`, `.env.example`, `README.md` and the document stubs | I kept the course baseline in `AGENTS.md` and added project guardrails (public data only, no contract-work content, raw data out of git) | `.env` and `data/raw/` are git-ignored; `.env.example` holds names only |

**Consequential AI contribution (scope):** my draft scope had a posting collector, a rating app with recruited raters, a demand nowcast, and a budget planner. The AI flagged three problems: a few weeks of postings is too little data for a credible forecast, I have no approved way to recruit raters, and the budget planner depended on both halves being finished. I rejected the budget planner myself. I accepted replacing recruited raters with public datasets that publish several raters' labels per item, and replacing the nowcast with cross-sectional analysis (pay premiums, pay spread across platforms) that works from one snapshot. I modified the framing so both halves answer one question: is the price of expertise justified by its value? This is not verified yet; the source census and dataset check in Sprint 1 will show whether enough public data exists.
