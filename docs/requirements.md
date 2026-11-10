# Requirements

> **Status:** Sprint 3. Living engineering intent, not a fixed contract. Each requirement has a target sprint and a status (`Planned`, `Partial`, `Implemented`, `Deferred`). Implemented requirements link to their code and tests in [Implementation Map](#implementation-map). Unsettled values are marked **TBD**.

## Purpose and User

**Primary user:** an operations, pricing or quality lead at an AI human-data company (or a client buying from one). They run labeling programs that hire experts, and they need to decide **which mix of experts, crowd raters and LLM judges reaches the quality they need at the lowest cost**. Today they lack two things:

1. **Rate benchmarks** (the price side): what an hour of expert, crowd and staff work costs, and what the same expert earns outside AI data work. Since Sprint 3 these come from three kinds of public source, all stored in one validated, cited table (FR-9):
   - **public job-board APIs** (Ashby; the ATS feeds employers use to distribute jobs), published as aggregates only;
   - **official wage statistics** (BLS OEWS hourly medians: the expert's outside option);
   - **cited published figures** (papers that state what their raters were paid, platform pay guidance written for researchers).

   The companies' own websites and work platforms are **not** used, by decision. Their terms forbid collection (Sprint 3 check), and this public project should take nothing from their work (`AGENTS.md` §4.7–4.9).
2. **A quality audit** (the value side): how much better expert labels actually are than crowd labels, which raters to trust, and whether an LLM judge could replace or route some human review.

**Question the tool answers:** is the pay premium for expertise justified by the quality difference experts produce, and do LLM judges change that trade-off? ("Cost of Quality".)

**Interaction surface:** a command-line tool, `pfq`. There is no graphical UI in class scope.

## Functional Requirements

| ID | Requirement | Target sprint | Status |
|---|---|---|---|
| FR-1 | **Collect postings.** The user can collect public job postings from a configured source. Each posting's raw content is stored once per version, and re-running collection does not create duplicates. | S2 | **Implemented** (Ashby. A Greenhouse adapter is not built yet. Expert-gig platform sites are not collected, by decision: `AGENTS.md` §4.7) |
| FR-2 | **Extract and validate posting fields.** The user can run extraction on collected postings. An extractor proposes fields (company, platform, title, domain, seniority, credentials, pay, posted date). Core validation accepts the result, rejects it, or sends it to a review queue. Every rejection or review carries named issue codes. | S2 (validation, baseline extractor), S4 (LLM extractor) | **Partial**: validation and audit trail implemented; the extractor is the deterministic baseline. The LLM extractor moved to S4 |
| FR-3 | **Normalize pay to hourly.** Every accepted pay quote is converted to an hourly USD range, or explicitly marked as not normalizable with a reason. | S1 (Core + test), S2 (integrated) | **Implemented** |
| FR-4 | **Query the pay market.** The user can run named, committed SQL analyses over job-board postings: hourly pay by segment and department, and the share of postings that state pay. Results are industry aggregates (`AGENTS.md` §4.8). | S2 | **Implemented**: `pay_by_domain` (by segment and source department) and `pay_transparency`. Credential comparisons need LLM extraction (S4+) |
| FR-5 | **Review and evaluate extraction.** The user can list, accept or reject queued extractions. The tool reports per-field extraction accuracy against a hand-labeled set of about 100 documents. | S4 (moved from S3) | **Deferred to S4**, together with the LLM extractor. The likely corpus is dataset papers (rater pay, rater qualifications), not job postings |
| FR-6 | **Audit rater quality.** The user can load a public multi-rater dataset (SummEval first). They can then compute inter-rater agreement, per-rater scorecards, ambiguous items, and expert vs. crowd agreement. | S4 | Planned |
| FR-7 | **Compare an LLM judge.** The user can run an LLM judge on a dataset's items. The tool reports judge vs. expert agreement alongside expert vs. crowd agreement, plus the judge's cost. | S5 | Planned |
| FR-8 | **Summarize the cost of quality.** The user can produce a short report comparing the expert pay premium (from `rate_observation`) with the expert quality difference (quality side), as cost per unit of agreement for expert, crowd and LLM-judge labeling. Every number in it comes from Core or a committed SQL query. | S5 | Planned |
| FR-9 | **Load pay rates from any source.** The user can load pay rates from a registered rate source: a cited file (`data/rates.toml`), BLS OEWS wages, or accepted job-board postings. Each rate passes one Core validation (vocabulary, citation, hourly USD normalization, plausibility), is stored once with its provenance, and can be queried as an aggregate by domain and rater kind. | S3 | **Implemented** |

## Implementation Map

| Requirement | Code | Tests |
|---|---|---|
| FR-1 | `app/market.py::collect`, `adapters/sources/ashby.py`, `adapters/sources/registry.py`, `adapters/storage/raw_store.py` | `tests/app/test_collect.py`, `tests/adapters/test_ashby.py` |
| FR-2 | `core/validation.py`, `app/market.py::extract`, `adapters/llm/baseline.py`, `adapters/llm/fake.py` | `tests/core/test_validation.py`, `tests/app/test_extract.py`, `tests/adapters/test_baseline_extractor.py` |
| FR-3 | `core/pay.py` | `tests/core/test_pay.py` |
| FR-4 | `queries/pay_by_domain.sql`, `queries/pay_transparency.sql`, `app/reporting.py` | `tests/app/test_queries.py` (SQLite, and Supabase with `-m supabase`) |
| FR-9 | `core/rates.py`, `core/vocab.py`, `app/rates.py`, `adapters/rates/cited.py`, `adapters/rates/bls.py`, `queries/rates_by_domain.sql`, `data/rates.toml`, `data/sources.toml` (`[[rate_source]]`) | `tests/core/test_rates.py`, `tests/app/test_rates.py`, `tests/adapters/test_cited_rates.py`, `tests/adapters/test_bls.py`, `tests/test_cli.py` (rates) |
| DC-1 | `adapters/storage/*`, `schema/*.sql`, `schema/migrations/*/*.sql` | `tests/adapters/test_repository_contract.py`, `tests/adapters/test_schema_parity.py`, `tests/adapters/test_migrations.py` |
| DC-2 | `core/` | `tests/core/test_core_purity.py` |
| DC-4 | `adapters/storage/postgres_repository.py`, `cli.py` | `tests/test_cli.py::test_connection_error_never_shows_the_password` |
| DC-6 | `data/sources.toml`, `adapters/sources/http.py` | `tests/app/test_collect.py`, `tests/test_cli.py` (blocked sources) |
| DC-8 | `pyproject.toml` (`-m 'not supabase'`) | `pytest` with no `.env` |

## Design and Constraint Requirements

| ID | Constraint |
|---|---|
| DC-1 | **Database.** Collected and cleaned data persists in **Supabase (hosted Postgres)**. Automated tests use fakes and a local database, so they run without Supabase credentials or network access. Both go through one `Repository` port with two adapters. The schema is kept portable between the two, and anything dialect-specific stays inside an adapter. JSON or file storage alone is not the system of record. |
| DC-2 | **Pure Core.** Validation, pay normalization and agreement math live in `core` and use only the Python standard library: no database, HTTP, or LLM imports. |
| DC-3 | **LLM output is untrusted.** No LLM-produced value (extracted field, judge score) reaches an analysis table, query result or report unless Core validation accepted it. The raw LLM output is kept for audit. |
| DC-4 | **Secrets.** The Supabase connection string and keys, plus the LLM API key, live only in `.env` (git-ignored). They never appear in source, logs, error messages or the database. `.env.example` lists names only. |
| DC-5 | **LLM spending cap.** LLM calls stop before an estimated monthly spend would pass `LLM_MONTHLY_BUDGET_USD`. The cap is set low; the exact value is **TBD**. The LLM provider and model are **TBD**. Until they are chosen, the deterministic baseline extractor is the default and no LLM is called. |
| DC-6 | **Public data, collected gently.** A source is enabled only after its robots.txt and terms are checked and the result is recorded. Requests are rate-limited, use a generic client name, and never touch login-walled pages. Job listings come only from public job-board APIs, never from a company's own website or work platform. Every hand-entered rate cites its source (`AGENTS.md` §4.7–4.9). |
| DC-7 | **Data handling.** Raw pages and downloaded datasets stay under `data/raw/`, out of git. Every dataset's license is recorded. Non-public rater data is stored separately from public data. Nothing from the owner's contract work enters the repository. |
| DC-8 | **Verification.** Tests run with `pytest` from the repo root and need no network, Supabase or API key. |

## Interaction / UX Expectations

- **One command per task.** Built: `pfq init-db`, `pfq sources`, `pfq collect`, `pfq extract`, `pfq rates load`, `pfq query`. Planned: `pfq review`, `pfq ingest`, `pfq evaluate`, `pfq report` (see `docs/architecture.md`).
- **Every command ends with a summary of what happened:** counts (e.g. "42 new, 118 unchanged", "37 accepted, 3 rejected, 2 sent to review"), not silence.
- **Errors say what went wrong and what to do next**, e.g. "DATABASE_URL is not set; copy .env.example to .env". There are no stack traces by default and no secret values in messages.
- **Re-running a command is safe.** Collection, extraction and dataset loading are idempotent.
- **No-key mode:** `pfq extract --extractor fake` (and the default deterministic `baseline` extractor) run the pipeline without an LLM, so a reviewer can try the tool without an API key.
- **Machine-readable output:** `--json` on `query`, `evaluate` and `report`.
- **Exit codes:** `0` success, `1` handled error, `2` usage error.

## Acceptance Criteria

Given/When/Then. IDs map to requirements (AC-3.1 belongs to FR-3).

**FR-1 Collect**
- **AC-1.1** Given a source whose fake returns 3 postings, when `collect` runs twice with unchanged content, then 3 raw snapshots exist and the second run reports "0 new, 3 unchanged".
- **AC-1.2** Given one of those postings changes its text, when `collect` runs again, then a second snapshot exists for that posting and the old one is kept.
- **AC-1.3** Given a source not marked as terms-checked, when `collect` targets it, then the command refuses with exit code 1 and fetches nothing.

**FR-2 Extract and validate**
- **AC-2.1** Given a candidate whose pay evidence quote appears in the raw text and whose fields are valid, when it is validated, then it is accepted and stored as a posting with its pay quotes.
- **AC-2.2** Given a candidate whose pay figure does not appear anywhere in the raw text, when it is validated, then it is rejected with `EVIDENCE_NOT_FOUND` and no posting row is created.
- **AC-2.3** Given a candidate below the confidence threshold (provisional: 0.7), or with an hourly figure outside the plausibility band (provisional: $5–$500), when it is validated, then it goes to the review queue, not to the posting table.
- **AC-2.4** Given any extraction, accepted or not, then its raw LLM output, extractor name and prompt version are stored.

**FR-3 Normalize pay**
- **AC-3.1** Given `$52,000 per year`, then the hourly result is `$25.00` (2,080 hours/year).
- **AC-3.2** Given `$40–$60 per hour`, then the hourly range is `$40.00–$60.00`.
- **AC-3.3** Given `$300 per day`, then the hourly result is `$37.50` (8 hours/day).
- **AC-3.4** Given `$5 per task` with no stated time per task, then the quote is kept, the hourly fields are empty, and the issue is `UNIT_NOT_NORMALIZABLE`.
- **AC-3.5** Given a negative amount, or a minimum above the maximum, then validation fails with `AMOUNT_INVALID` or `RANGE_INVERTED`.

**FR-4 Query**
- **AC-4.1** Given 3 accepted postings in domain "medicine" with hourly midpoints 40, 60 and 80, when `pfq query pay_by_domain` runs, then "medicine" shows a median of 60 and n = 3.
- **AC-4.2** Given postings that were rejected or are still in review, then they never appear in query results.

**FR-5 Review and evaluate extraction** (deferred to Sprint 4)
- **AC-5.1** Given an open review item, when the user accepts it, then a posting is created and the item's status is `accepted`. When they reject it, no posting is created.
- **AC-5.2** Given the hand-labeled set, when the evaluation runs, then it reports accuracy per field (e.g. pay, unit, domain) and lists every mismatch. The target accuracy is **TBD** after the first run.

**FR-6 Rater quality**
- **AC-6.1** Given a published worked example for Fleiss' kappa, then Core reproduces its value to 3 decimals.
- **AC-6.2** Given two raters who agree on every item, then Cohen's kappa is 1.0. Given that every label is the same single category, then kappa is reported as undefined with a reason, not as a crash or a misleading number.
- **AC-6.3** Given a simulated dataset where one rater is planted as random, then that rater has the lowest scorecard agreement.
- **AC-6.4** Given SummEval loaded, when `evaluate` runs, then it reports expert–expert, crowd–crowd and expert–crowd agreement for each criterion.

**FR-7 LLM judge**
- **AC-7.1** Given judge outputs where some are off-scale or unparseable, then only valid scores are stored as labels, failures are counted, and the counts appear in the result.
- **AC-7.2** Given a completed judge run, then the output shows judge–expert agreement next to expert–crowd agreement, plus the total cost of the run.

**FR-8 Report**
- **AC-8.1** Given market and quality results exist, when `pfq report` runs, then each number in the report can be traced to a named query or Core function (shown in the report's source notes).

**FR-9 Load pay rates** (Sprint 3; all six implemented and tested, see `docs/sprint-status.md`)
- **AC-9.1** Given a cited-rates entry with no citation, when `pfq rates load` runs, then it is rejected with `CITATION_MISSING` and no row is written.
- **AC-9.2** Given an annual government wage of $104,000 for an occupation mapped to `medicine`, then the stored rate is $50.00/h with `rater_kind = outside_option` and its citation.
- **AC-9.3** Given an accepted job-board posting with an hourly contract pay quote, when job-board rates are loaded, then exactly one rate exists with `engagement = contractor`, linked to its `raw_posting`. Loading again creates no duplicates.
- **AC-9.4** Given rates from three provenance kinds in one domain, when `pfq query rates_by_domain` runs, then it reports the median hourly rate per domain and rater kind with `n` and the number of provenance kinds, and no company names.
- **AC-9.5** Given a Sprint 2 (version 1) database, when `pfq init-db` runs, then the migrations bring it to version 2 with no data loss, and a second run is a no-op.
- **AC-9.6** Given a rate source that has not passed its terms check, then loading refuses with exit code 1 and fetches nothing.

**Constraints**
- **AC-DC-2** A test (or import check) confirms `core` imports no database, HTTP or LLM modules.
- **AC-DC-4** Given `DATABASE_URL` holds a password, when a connection error is reported, then the message does not contain the password.
- **AC-DC-5** Given the month's recorded spend plus the next call's estimate would exceed the cap, then the call is not made and the command stops with a clear message.
- **AC-DC-8** Given a fresh clone with no `.env`, then `pytest` passes.

## Verification Intent

These are the first behaviors to be proven with tests (the Sprint 1 requirement asks for at least three).

| Behavior | Normal case | Edge / error case | Expected result | Convincing evidence |
|---|---|---|---|---|
| Pay normalization (FR-3) | `$52,000/year`; `$40–60/hour` | `$5/task` with no time stated; negative amount; min > max | `$25.00`; `$40–60`; empty hourly + `UNIT_NOT_NORMALIZABLE`; validation errors | Table-driven `pytest` cases with values worked out by hand beforehand |
| Extraction validation (FR-2) | Candidate with evidence quotes found in the text | Candidate inventing a pay figure absent from the text; low confidence | Accepted; `EVIDENCE_NOT_FOUND`; sent to review | Tests using scripted fake-extractor outputs; later, real-LLM accuracy on the 100 hand-labeled postings (FR-5) |
| Idempotent collection (FR-1) | Two runs with unchanged content | Changed content; source not terms-checked | 3 snapshots then "0 new"; new version added; refusal | Use-case test with a fake source and local database; row counts asserted |
| Rate loading (FR-9) | A cited figure; an annual BLS wage; an hourly contract posting | No citation; an unknown domain; a per-task or EUR rate; an unchecked source; a version-1 database | Stored once with hourly USD; `CITATION_MISSING` / `VOCAB_UNKNOWN` / rejection; refusal before any fetch; migrated with data kept | Core, use-case, adapter, migration and CLI tests (`tests/core/test_rates.py` and others); a real Supabase migration and load |
| Agreement metrics (FR-6) | Published Fleiss' kappa example | Perfect agreement; one category only; missing labels | Matches published value; 1.0; "undefined" with reason; handled | Comparison with published values, plus a simulation where a planted bad rater must rank last |

## Exploration Zone (not committed for class)

These are interesting, but not graded and not promised before the course ends (Sprint 5, Dec 9, 2026):

- Hedonic regression of pay on credentials, domain and platform with proper controls (FR-4 covers simple comparisons only).
- Dawid–Skene rater model; full LLM-judge bias audit (position, verbosity, self-preference); cost of routing between human and LLM review.
- Wayback Machine backfill for pay history (coverage and terms **TBD**).
- A web dashboard or recurring public pay summaries.
- The research experiment (pay × announced AI monitoring), only after ethics approval. The design keeps this a configuration change, not a rebuild.

## Deferred / Out of Scope

- Recruiting human raters (no approved way to do so; public datasets are used instead).
- Demand forecasting (too little data for a credible forecast).
- Any content from private contract work.
