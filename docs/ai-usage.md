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

## Sprint 2 Log

| Area | What I had the AI do | My direction and decisions | Verification |
|---|---|---|---|
| Plan | Turn the Sprint 2 goal into a step plan (environment, Core, census, schema, use cases, CLI, Supabase check, docs) | I approved the plan with two choices: no real LLM until Sprint 3, and keep the `sprint-2` branch name | Each step ended with tests and a commit on the sprint branch |
| Core and storage | Implement pay normalization, extraction validation, the shared SQL repository and the two schemas | I required Supabase as the real database while tests stay offline | 89 tests pass with no credentials; the same 25 database tests pass on Supabase |
| Supabase setup | Write a setup guide (session pooler, separate schema, RLS, free-plan pausing) | I created the project and filled in `.env` myself; the connection string was never shared in chat | Security-relevant claims checked against Supabase's current docs; RLS enabled on every table (tested) |
| Real run | Run collect → extract → query against Supabase and explain every non-accepted result | I reviewed the three non-accepted postings (a $0 grant, two $5M research grants) | Recorded in `docs/sprint-status.md`; one bug found and fixed with a regression test |

**Consequential AI contribution (source census → market segments):**
- **What the AI suggested.** Its census of about 15 AI-data companies' public job-board APIs found ~530 postings, but only ~16 with hourly pay. It flagged that these APIs list mostly the companies' **staff** roles, while the **expert contractor gigs** my research question is really about sit on the companies' own platform sites, which need a separate terms review.
- **What I decided.** I accepted the finding and chose to split the market side into `staff` and `expert` segments. Sprint 2 runs on Ashby (Mercor, Handshake), a public API with structured compensation that also lists the strategy and ops roles I'm applying for. Expert gigs move to Sprint 3, after their terms are read.
- **What I modified.** I asked for the job-board providers' API docs to be read before any source was enabled, not just robots.txt. The result is recorded per source in `data/sources.toml`.
- **What I rejected.** Collecting from the platform sites now: their robots.txt files allow most pages, but I haven't read their terms.
- **How it was verified.** `scripts/source_census.py` re-runs the counts. The registry blocks unchecked sources, which is tested. The real run showed 142 of 160 accepted postings state pay, almost all as annual salaries.
