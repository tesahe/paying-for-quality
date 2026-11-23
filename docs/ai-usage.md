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

## Sprint 3 Log

| Area | What I had the AI do | My direction and decisions | Verification |
|---|---|---|---|
| Direction check | Compare the docs with the code (a drift check: list each concrete claim in the docs and verify it against the code, `AGENTS.md` §6) and challenge the planned Sprint 3 scope | I asked for a challenge rather than agreement. I accepted the drift findings: segment set per source, department stored as `domain`, `init-db` unable to upgrade, a review queue that never held failures | Each claim checked against the source; findings recorded in this sprint's doc corrections (`docs/architecture.md`, "What Changed") |
| Sources research | Two research subagents: BLS API terms, series-ID format and current values; published figures on rater pay with exact quotes | I required an exact quote and URL for every figure, and that anything unconfirmed be dropped | Spot-checked against the saved sources: MT-Bench "around $35", GPQA "approximately $95 per hour", BLS terms and the 2025 values. Every `data/rates.toml` entry is tested to pass Core validation |
| Implementation | Core rate model, migrations, adapters, CLI, tests, docs on `sprint-3` | I set the decisions first: aggregate-only output, the 10-domain vocabulary, numbered SQL migrations (no library), a new table beside `pay_quote`, the LLM extractor in Sprint 4 | 133 tests offline; 32 against Supabase; real migration and load on Supabase (`docs/sprint-status.md`) |

**Consequential AI contribution (data sourcing → the "Cost of Quality" reframe):**
- **What the AI produced.** It found that the expert pay my question needs sits on the companies' own work platforms. It had a subagent read their terms: Mercor's (§2.2) and Alignerr's ("Restrictions" item 8) prohibit scraping, including manual copying. It also found that some expert contract roles (Handshake "AI Red Teamer", $65–158/h) already appear on the public job boards, mislabeled as staff. It then proposed five alternatives: a cost-of-quality toolkit with pay as a cited input; aggregate-only job-board statistics; extraction from dataset papers; simulation; asking companies directly.
- **How I reviewed it.** I weighed it against what matters most to me: this is a public resume project aimed at jobs at these same companies. Scraping their platforms, or even publishing named-company pay comparisons, would look bad and could break their terms, even if robots.txt allows it.
- **What I decided.**
  - **Accepted:** the cost-of-quality framing (the first alternative), plus outside-option wages from BLS (the US Bureau of Labor Statistics' Occupational Employment and Wage Statistics, OEWS).
  - **Modified:** listings are kept, but **only from public job-board APIs, never company websites**, and job-board results are published as aggregates only. I had the rules written into `AGENTS.md` §4.7–4.9.
  - **Rejected:** collecting from or hand-copying the platform sites, and the original Sprint 3 scope (an LLM extractor on postings), which I moved to Sprint 4.
- **How it was verified.**
  - The platform terms were read by an AI subagent; its clause quotes (Mercor §2.2(b), (c), (e); Alignerr "Restrictions" item 8) are recorded in `docs/architecture.md`, "Terms and robots checks". The decision doesn't depend on them alone: the sourcing rule excludes every company website, whatever its terms say. The BLS terms and the paper figures were checked against saved copies of the sources.
  - The terms gate is tested (an unchecked rate source is refused before any fetch).
  - Citations are enforced in Core and tested (`CITATION_MISSING`).
  - The schema has no company column, so the aggregate-only rule holds in the data model itself.
  - The real run loaded 154 rates from three kinds of source, and `rates_by_domain` returned aggregates only.

## Sprint 4 Log

| Area | What I had the AI do | My direction and decisions | Verification |
|---|---|---|---|
| Plan | Read the Sprint 4 assignment, the project plan and the Sprint 3 follow-ups, then propose one strengthening focus | I asked it to follow the original plan (hardening plus the first quality slice), commit along the way and leave pushing to me | The plan is the commit list on `sprint-4` |
| Investigation | Reproduce the Sprint 3 "flaky Supabase run" follow-up | I approved restoring the paused Supabase project through the Supabase connector so the fix could be checked live | Redacted driver replies captured before and after the restore (`docs/sprint-status.md`) |
| Quality slice | Krippendorff's alpha in Core, a SummEval reader and `pfq quality summeval` | I chose to build the reader on a hand-made fixture and not download SummEval yet, to keep Sprint 4 centered on the strengthening work | Alpha reproduces Krippendorff's published example (0.743 nominal, 0.849 interval) |

**Consequential AI contribution (database failure handling: what to retry, and what to say):**
- **The question.** Sprint 3 left a follow-up: one Supabase test run had 11 setup errors with an unknown cause, and the suggested fix was "add connection retry or timeout handling".
- **What the AI found.** Probing the database showed that the project had paused itself after 13 idle days. The pooler's reply to a paused project is `FATAL: (ENOTFOUND) tenant/user … not found`, after about 13–15 seconds. `pfq` turned every connect failure into "check DATABASE_URL in .env", which sends the user to the wrong place, and an error during a command printed only "unexpected OperationalError".
- **What it recommended, and how that was evaluated.**
  - *Blanket retry with backoff on every database call* (the obvious reading of the follow-up): **rejected.** A retry would not help a paused project or a wrong password; it would only multiply a 15-second wait. Replaying an operation after a dropped connection is unsafe, because the server has already rolled back the transaction and a multi-step command could be half-repeated. Since every load is idempotent, re-running the command is the safe recovery.
  - *Retry the connect only, only for transient causes (timeout, no free slots), with a classified message for every failure*: **accepted** (`adapters/storage/db_errors.py`).
  - *A retry library (tenacity)*: **rejected.** It is one retry site, and a library would make wrapping operations easy, which the design rules out.
- **Where the AI's own change was wrong.** Its first fixture fix moved `apply_schema` inside the `try`, which assumed the orphan came from a failed setup. Once Supabase was back, the leftover schema `pfq_test_52d59e09` turned out to be **complete, at version 2**. The run had died after setup, so the first fix did not cover the observed case. A second fix drops the schema over a fresh connection when the old one is dead (`0b625a1`). Separately, a hand-computed expected correlation in a new test was wrong (0.9934, then 0.99432). The exact-fraction assertion failed and caught it; the right value is 0.99419.
- **How it was verified.**
  - 53 new offline test cases (186 in all, up from 133); the classifier is tested with the pooler's real reply text.
  - A live `pfq init-db` against the paused project printed the new "probably paused: restore it" message.
  - After the restore, the full Postgres suite and a live `pfq init-db` / `pfq query rates_by_domain` ran against Supabase (`docs/sprint-status.md`).
- **Limitation.** The cause of the original Sprint 3 failure is still not proven. The leftover schema shows that the connection died after setup; the most likely cause is the session pooler dropping or refusing connections, but it was not reproduced.
