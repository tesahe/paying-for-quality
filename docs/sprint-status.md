# Sprint Status

## Sprint 3: Expansion and Integration: the source-agnostic rate model

**Branch:** `sprint-3` · **Status:** complete (merged into `main`, branch kept)

### The improvement

**Every pay figure, from any source, now enters through one Core-validated, cited, hourly-USD path** and is stored in one table, `rate_observation`. It builds on Sprint 2:
- it reuses Core pay normalization, the registry's terms gate, the shared SQL repository and the CLI;
- the Sprint 2 posting pipeline is unchanged and becomes one rate source among three.

```
pfq init-db                           →  migrates a Sprint 2 database (version 1) to version 2
pfq rates load --source cited-rates   →  data/rates.toml (7 published figures, each cited)
pfq rates load --source bls-oews      →  BLS OEWS hourly medians for 8 expert occupations (outside option)
pfq rates load --source job-boards    →  rates from accepted job-board postings, with engagement from the posting
pfq query rates_by_domain             →  median hourly rate by domain and rater kind (aggregate, no company names)
```

**Why this improvement (scope decision).** The plan going in was an LLM extractor measured on 100 hand-labeled postings. Checking the data source first changed it:
- Expert contractor pay sits on the companies' own platform sites. Their terms forbid collection: Mercor's terms §2.2 and Alignerr's "Restrictions" item 8 both cover manual copying too.
- This is a public project aimed at jobs in the same industry.

The owner therefore reframed the project as **"Cost of Quality"** (`AGENTS.md` §3–4). Pay is a cited input from neutral public sources. Without a source-agnostic rate model the price side has no data, so this became the Sprint 3 improvement, and the LLM extractor moved to Sprint 4.

**Requirement:** FR-9 with AC-9.1–9.6 (`docs/requirements.md`). **Code path:** `docs/architecture.md`, "Code path: `pfq rates load`".

### What was built

- **Core** (standard library only):
  - `core/vocab.py`: closed vocabularies for domain, engagement, rater kind and provenance, plus `domain_from_title`.
  - `core/rates.py::validate_rate`: vocabulary, then citation, then `normalize_pay_quote`, then the $1–$500/h band. Any issue rejects. New codes `CITATION_MISSING` and `VOCAB_UNKNOWN`.
- **Storage:**
  - numbered migrations (`schema/migrations/<dialect>/002_rate_observation.sql`) applied by `pfq init-db`;
  - tables `rate_source` and `rate_observation`. The latter has no company column, which enforces the aggregate-only rule in the schema.
- **Rate sources** (`[[rate_source]]` in `data/sources.toml`):
  - `CitedRates`;
  - `BlsOewsRates`, with BLS's required retrieval date and disclaimer in each citation;
  - `JobBoardRates`.
- **CLI:** `pfq rates load`; `pfq sources` also lists rate sources; `pfq init-db` reports the version. Query: `rates_by_domain`.

### Automated tests

| Command | Expected | Observed (2026-11-09) |
|---|---|---|
| `.venv/bin/pytest` (no network, no `.env` needed) | All pass; Supabase tests deselected | **133 passed, 32 deselected** (Sprint 2: 89) |
| `.venv/bin/pytest -m supabase` (needs `PFQ_TEST_DATABASE_URL`) | Repository, use-case and query tests pass on real Postgres in throwaway schemas | **32 passed, 133 deselected** (~2.5 min; Sprint 2: 25). An earlier run the same day had 11 setup errors and 1 failure on the Postgres side; it took 8.5 minutes of wall-clock time against about 2 minutes of test time. The failing tests passed when rerun alone, and a full rerun passed. The cause is unconfirmed; slow or dropped connections to Supabase's pooler are the likely suspect |

What the new tests check:
- **AC-9.1 (rejection):** an uncited rate is rejected with `CITATION_MISSING` and writes nothing.
- **AC-9.2 (normalization):** $104,000 a year becomes $50.00/h, `outside_option`.
- **AC-9.3 (job-board rates):** a Contract hourly posting becomes exactly one `contractor`/`expert` rate linked to its posting. A full-time one becomes `employee`/`staff`. Loading twice adds nothing.
- **AC-9.4 (aggregate query):** `rates_by_domain` gives medians across three provenance kinds, with no company column.
- **AC-9.5 (migration):** a version-1 database with data migrates to version 2 with its rows kept, and ends up with the same tables as a fresh database. A second run is a no-op. A broken migration leaves version 1.
- **AC-9.6 (terms gate):** an unchecked rate source is refused before any fetch, through both the use case and the CLI.
- **Committed data:** every entry in `data/rates.toml` passes Core validation and carries a retrieval date.
- **Schema:** the CHECK constraints match the Core vocabularies, and the dialects have the same migration numbers.
- **BLS adapter:** tested against the live response shape, including top-coded and suppressed values.

### Manual / integration check: real run against Supabase (2026-11-09)

| Step | Result |
|---|---|
| `pfq init-db` (Supabase still at version 1, holding the Sprint 2 data) | `Applied migration(s) 2; schema is at version 2.` Then `pay_transparency` still shows Mercor 81/83 and Handshake 61/77 (data kept) |
| `pfq init-db` again | `Schema is up to date (version 2).` |
| `pfq rates load --source cited-rates` | `7 rates: 7 new, 0 unchanged, 0 rejected`; on re-run `0 new, 7 unchanged` |
| `pfq rates load --source bls-oews` (live BLS API, 8 GETs) | `8 rates: 8 new, 0 unchanged, 0 rejected` (May 2025 estimates) |
| `pfq rates load --source job-boards` | `139 rates: 139 new`: the 142 accepted postings that state pay, minus the 3 in GBP or EUR (not hourly USD) |
| `pfq query rates_by_domain` | 18 rows. Examples below |

| domain | rater kind | n | median $/h | sources |
|---|---|---|---|---|
| stem_science | expert | 2 | 103.25 | job-board contract role + GPQA paper |
| stem_science | outside_option | 1 | 82.81 | BLS, physicists |
| coding | staff | 40 | 128.61 | job boards |
| coding | outside_option | 1 | 65.38 | BLS, software developers |
| reasoning_general | expert | 1 | 35.00 | MT-Bench paper |
| none | crowd | 4 | 9.50 | Prolific guidance, Mechanical Turk study |

**What this first output already shows (not yet a finding).**
- The expert rates on hand (in `stem_science`: the CBRNE red-teaming role at a $111.50/h midpoint and GPQA at $95/h; the cybersecurity red-teaming role, $95/h, is counted under `coding`) sit above the experts' outside option ($82.81/h for physicists).
- Crowd rates sit an order of magnitude lower.
- The expert sample is tiny (n = 1–2 per domain). Sprint 4's quality side supplies the other half of the comparison.

### Known limitations

- **Small expert sample.** Only 3 public job-board postings are contract roles, and 2 of them give hourly pay (the Handshake "AI Red Teamer" roles). The cited figures are a handful. Every row shows `n`, and none should be read as a market estimate.
- **Provisional rules.** Domain comes from title keywords (`domain_from_title`). `contractor`/`temporary` are taken to mean `expert` (`rater_kind_for`). Both are to be replaced by LLM extraction (Sprint 4).
- **BLS** returns only the latest estimates (no history). Its wages exclude the self-employed, which matters for writers, translators and lawyers.
- **Cited figures** differ in date (2017–2026) and meaning (a platform minimum vs. a paper's average). The `citation_note` says which; the query does not adjust for it.
- `rates_by_domain` is a simple median; no weighting or adjustment.
- **Carried over:** no LLM extraction; `pfq review` not built; collection run by hand; Supabase's free plan pauses after about 7 days idle.
- **The Sprint 2 recorded demo has not been recorded yet.**

### Next step (Sprint 4)

- First quality slice: load SummEval, then agreement metrics and expert vs. crowd.
- The LLM extractor, evaluated on hand labels. The likely corpus is dataset papers, to recover rater pay and qualifications.
- `pfq review` commands.
- Required hardening (error handling, dependency justification, a bounded refactor). This includes the Supabase test run that failed once in Sprint 3 (above): add connection retry or timeout handling, or record the cause.

### Peer feedback

**Status: not received by submission.** No feedback from Peer Review 1 (the course's separate peer-review assignment) on this project had reached me before the Sprint 3 submission. **Follow-up:** I will ask my assigned reviewer for their recommendations. In Sprint 4 I will record at least one recommendation and whether I accepted, adapted, postponed or rejected it, with the reason.

### Sprint 3 commits

On `sprint-3`: a docs status fix, the Core rate model, migrations and rate storage, rate sources and the CLI, tests for each, and docs. The branch was then merged into `main` (`merge: sprint-3 into main`) and kept.

---

## Sprint 2: Narrow Working System

**Branch:** `sprint-2` · **Status:** complete (merged into `main` in `ed7247f`, branch kept). The recorded demo has not been made yet.

### Working now

One narrow, database-backed slice of the market pipeline, end to end, on Supabase Postgres and local SQLite:

```
pfq collect --source ashby-mercor  →  raw snapshots (data/raw/) + raw_posting rows
pfq extract                        →  baseline extractor → Core validation → posting / pay_quote / review_item
pfq query pay_by_domain            →  median hourly pay by segment and department
```

- **Core:**
  - Pay normalization to hourly USD (`core/pay.py`).
  - Extraction validation with named issue codes and an **evidence check**: a pay figure must appear, quoted, in the posting text, which blocks invented numbers (`core/validation.py`).
- **Storage:** one shared SQL repository with SQLite and Supabase adapters, two schema files kept in sync by a test, Row Level Security on every Supabase table, and a separate `pfq` schema not exposed through Supabase's Data API.
- **Source:**
  - The Ashby public job-board API for Mercor and Handshake, with a source registry (`data/sources.toml`) that blocks any source whose terms are unchecked.
  - Carried over from Sprint 1: the **source census** (`scripts/source_census.py`; results in `docs/architecture.md`, "Data Sources").
- **Extraction:** a deterministic baseline extractor (no LLM, $0) that uses the source's structured compensation and falls back to a pay regex. The real LLM extractor is Sprint 3.
- **CLI:** `pfq init-db | sources | collect | extract | query`.

### Automated tests

| Command | Expected | Observed (2026-11-09) |
|---|---|---|
| `.venv/bin/pytest` (no network, no `.env` needed) | All pass; Supabase tests deselected | **89 passed, 25 deselected** |
| `.venv/bin/pytest -m supabase` (needs `PFQ_TEST_DATABASE_URL`) | Repository contract, use-case and query tests pass on real Postgres, each in a throwaway schema | **25 passed** (~80 s) |

What the tests cover:
- the pay acceptance criteria AC-3.1–3.5;
- the extraction criteria AC-2.1–2.4, including invented pay and changed amounts;
- idempotent collection, AC-1.1–1.3;
- the portable median query, AC-4.1–4.2, on both databases;
- that Core imports only the standard library (AC-DC-2);
- that the CLI never prints the database password (AC-DC-4);
- the full collect → extract → query path through the CLI.

### Manual / integration check: real run against Supabase (2026-11-09)

| Step | Result |
|---|---|
| `pfq init-db` | `Schema is up to date.`; tables created in schema `pfq` |
| `pfq collect --source ashby-mercor` (twice) | `86 new` then `0 new, 0 changed, 86 unchanged` (idempotent) |
| `pfq collect --source ashby-handshake` | `77 new` |
| `pfq collect --source mercor-platform` | Refused: `has not passed its robots.txt/terms check`, exit 1 |
| `pfq extract` | `163 postings: 160 accepted, 2 sent to review, 1 rejected` |
| `pfq query pay_transparency` | Mercor 81/83 postings state pay (97.6%); Handshake 61/77 (79.2%) |
| `pfq query pay_by_domain` | 18 departments, e.g. engineering n = 50, median $114.18/h; operations n = 11, $91.35/h |

The real run turned up a bug: a blocked source with no adapter reported "no collector" instead of the terms refusal. It was fixed in `8b0645b`, with a regression test.

Every non-accepted extraction was the right call:
- **Rejected (1):** a "$0 – $0" grant listing.
- **Review (2):** two research-fund grants at "$5M per year", which would be $2,403.85/h. They're grants, not jobs.
- **Accepted but excluded from hourly figures (3):** postings paid in GBP or EUR (`CURRENCY_UNSUPPORTED`).

### Decisions this sprint

| Decision | Choice | Reason |
|---|---|---|
| First source | Ashby (Mercor, Handshake) | Public, unauthenticated API with structured compensation; one request per board per run |
| Market segments | `staff` vs. `expert` per source | The census showed public APIs list staff roles. Expert gigs are on platform sites that need a terms review |
| Extractor before the LLM | Deterministic baseline | A $0 working pipeline now, and a baseline the Sprint 3 LLM must beat |
| Dependencies | `psycopg[binary]`, `pytest`; no HTTP or dotenv library | The standard library can't talk to Postgres; everything else is a single GET or a `KEY=VALUE` file |
| Python | 3.13 venv | The system default is 3.15; 3.13 has prebuilt driver packages |

### Known limitations

- **No LLM extraction yet.** `domain` is the source's department and `seniority` a title keyword; credentials are not extracted.
- **Staff roles only.** The expert-gig segment that most directly measures "price of expertise" is blocked until the platforms' terms are reviewed.
- Validation thresholds ($5–$500/h, confidence 0.7) are provisional.
- Non-USD pay is kept but excluded from hourly figures.
- `pfq review` commands are not built; review items can only be inspected in the database.
- Collection is run by hand. Weekly scheduling is not set up, and Supabase's free plan pauses after about 7 days of low activity.
- The dataset check (SummEval and others, licenses) has not started.
- The recorded demo has not been recorded yet.

### Next step (Sprint 3)

The focused improvement is **real LLM extraction with measured accuracy**:
- an LLM `Extractor` adapter;
- about 100 hand-labeled postings;
- per-field accuracy compared with the baseline;
- `pfq review` commands;
- a terms review of the expert-gig platforms.

### Recorded demo outline (about 3 minutes)

1. `pytest`: all tests pass, with no credentials needed.
2. `pfq sources`: three sources ready, the expert platform blocked.
3. `pfq init-db`, then `pfq collect --source ashby-mercor` twice, showing "0 new" on the second run.
4. `pfq extract`: accepted, review and rejected counts, with the issue codes.
5. `pfq query pay_by_domain`.
6. The Supabase Table Editor (schema `pfq`): the same rows, plus `extraction_run` showing the rejected $0 grant.

### Peer feedback

Not received during Sprint 2 (see Sprint 3 for the current status).

---

## Sprint 1: Define and Establish

**Branch:** `sprint-1` · **Status:** complete (merged into `main`, branch kept)

- Baseline files; first drafts of the requirements (8 FRs, 8 constraints, acceptance criteria, verification intent for 4 behaviors) and of the architecture (layers, ports, CLI boundary, data model, persistence plan).
- Decisions: Supabase Postgres with a local test database; pytest.
- Carried into Sprint 2: the source census (done) and the first pay-normalization test (done). The dataset check is still open.
