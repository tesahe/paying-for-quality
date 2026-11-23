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

Sprint 4 follows the plan I set at the start of the project: **harden what exists, and start the quality side** with SummEval-style agreement and expert vs. crowd. The quality side is half of the project's question, so the agreement math had to be trustworthy before any real data goes through it. The LLM extractor and the review commands wait until Sprint 5.

| Area | What I had the AI do | My direction and decisions | Verification |
|---|---|---|---|
| Plan | Turn my Sprint 4 plan into steps, matched to the Sprint 4 assignment | I set the scope: the quality slice from my plan plus hardening, commits along the way. I merge and push myself | The plan is the commit list on `sprint-4` |
| Agreement math | Implement the agreement metric in Core and check it against published values | I required a published worked example as the test, not just values the AI computed itself | Krippendorff's example reproduced: 0.743 nominal, 0.849 interval |
| Dataset input | A SummEval reader that sends every score through Core validation | I chose a reader tested on a hand-made fixture now; I'll download the real file in Sprint 5 | Off-scale and non-numeric scores counted and treated as missing (tested) |
| Hardening | Review error handling at the database boundary | I accepted cause-specific, safe error messages and retrying the connect only; I rejected retrying every operation, and a retry library | `tests/adapters/test_db_errors.py`; 32 Supabase tests pass |

**Consequential AI contribution (which agreement metric decides "expert vs. crowd"):**
- **The question.** My plan, and AC-6.1, named Fleiss' kappa as the first agreement metric. Is that the right measure for the data the project will actually use?
- **What the AI recommended.** Krippendorff's alpha instead, at the interval level. Its reasons:
  - SummEval's scores are 1–5 ratings. Fleiss' kappa treats them as unordered categories, so a 4 vs. 5 counts as the same disagreement as a 1 vs. 5.
  - SummEval has 3 experts and 5 crowd raters per summary. Fleiss' kappa assumes the same number of raters on every item and no missing ratings.
  - Alpha weighs disagreement by its size, allows missing ratings, and works for both groups, so expert and crowd agreement are measured the same way.
- **How I evaluated it.** I weighed it against what the number is for: comparing expert and crowd quality fairly, on the same scale, for a cost-of-quality argument. A metric that can't tell "nearly agree" from "completely disagree" would understate expert consistency. Alpha also needs no new dependency: it is about 30 lines of standard-library code, which keeps Core pure.
- **What I decided.**
  - **Accepted:** Krippendorff's alpha (nominal and interval) in `core/agreement.py`, with AC-6.1 changed and the reason recorded in `docs/requirements.md`.
  - **Modified:** undefined agreement returns `None` (shown blank) rather than a number. Dataset scores are validated in Core and counted when rejected (new AC-6.5).
  - **Rejected:** adding the `krippendorff` or `scipy` package.
- **How it was verified.**
  - Core reproduces Krippendorff's (2011) published worked example: 4 observers, 12 units, missing values; 0.743 nominal, 0.849 interval.
  - Hand-computed cases cover perfect agreement, systematic disagreement, rater order and undefined tables.
  - One check caught the AI out: its hand-computed expected value for the expert-crowd correlation was wrong (0.9934, then 0.99432). The test's exact-fraction assertion failed, and the correct value is 0.99419. That is why the test states the exact fraction rather than trusting a typed decimal.
  - 186 tests pass offline (up from 133), and 32 pass on Supabase.
- **Limitation.** The real SummEval file hasn't been run yet, so there is no real expert-vs-crowd result. Interval alpha also assumes the 1–5 steps are equally spaced.
