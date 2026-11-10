# Architecture

> **Status:** Sprint 3. Implemented on SQLite and Supabase Postgres: the posting path (collect → extract → validate → store → query, Sprint 2) and the **source-agnostic rate model** (any rate source → Core validation → `rate_observation` → aggregate query, Sprint 3). The quality side, the review commands and the real LLM extractor are still design. Open decisions are marked **TBD** and collected in [Open Decisions](#open-decisions).

## Overview

The system has two pipelines that share one database and meet at the analysis layer:

- **Price side (what expertise costs):** pay rates from any registered **rate source** → Core rate validation and hourly normalization → one `rate_observation` table → aggregate SQL analysis. The rate sources are:
  - a cited, hand-made file (`data/rates.toml`);
  - BLS OEWS wages (the expert's outside option);
  - accepted job-board postings, produced by the posting path: public job-board API → raw snapshot → extraction → Core validation → `posting` / `pay_quote`.
- **Quality side (value of expertise):** public multi-rater dataset → `item` / `rater` / `label` → Core agreement and rater-quality metrics → expert vs. crowd vs. LLM judge.

The code follows a ports-and-adapters layout. A pure **Core** holds all rules and math. **Use cases** orchestrate the Core through **ports** (interfaces). **Adapters** implement the ports for the outside world (HTTP, Supabase Postgres, SQLite, LLM APIs, dataset files). The **CLI** is the user-facing boundary and the only place where concrete adapters are wired together.

```mermaid
flowchart LR
    user([User]) --> cli[CLI: pfq]
    cli --> app[Use cases<br/>app/]
    app --> core[Core<br/>entities, validation,<br/>pay normalization, metrics]
    app --> ports{{Ports}}
    ports -.implemented by.-> src[PostingSource adapters<br/>Ashby (Greenhouse later)]
    ports -.implemented by.-> rates[RateSource adapters<br/>cited file, BLS OEWS, job boards]
    ports -.implemented by.-> llm[Extractor / Judge adapters<br/>baseline regex, fake; LLM in S4]
    ports -.implemented by.-> repo[Repository adapters<br/>Postgres / SQLite]
    ports -.implemented by.-> ds[DatasetLoader adapters<br/>SummEval, ...]
    repo --> db[(Supabase Postgres<br/>system of record)]
    repo --> local[(Local SQLite<br/>tests, offline runs)]
    src --> raw[(data/raw/)]
    rates --> bls([BLS Public Data API])
```

Dependencies point inward only: `cli → app → core`, and `adapters → core` (adapters implement ports defined in Core). Core imports nothing from `app`, `adapters` or `cli`.

## Components and Responsibilities

| Layer               | Package                         | Responsibility                                                                                                                                              | May import                                       |
| ------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| **Core**      | `paying_for_quality.core`     | Domain entities, validation of LLM candidates, pay normalization, agreement and rater-quality metrics, port definitions                                     | Python standard library only                     |
| **Use cases** | `paying_for_quality.app`      | One function/class per user action (collect, extract, load rates, query; later review, ingest, evaluate, report). Calls ports and Core and keeps run bookkeeping. Each repository write method wraps its own transaction | `core`                                         |
| **Adapters**  | `paying_for_quality.adapters` | HTTP posting sources, LLM extractor and judge clients, Postgres and SQLite repositories, dataset loaders, fakes for tests                                  | `core`, third-party libraries (each justified) |
| **CLI**       | `paying_for_quality.cli`      | Parse arguments, build adapters from config (composition root), call one use case, format output and exit code                                              | `app`, `adapters`, `core` types            |

Module layout (✓ = exists after Sprint 3):

```
src/paying_for_quality/
  core/
    entities.py      ✓ dataclasses: SourceInfo, RawPostingDoc, ExtractionCandidate, Posting, PayQuote, ...
    pay.py           ✓ unit conversion and hourly normalization
    validation.py    ✓ accept/reject/review extraction candidates (judge validation: S5)
    serialization.py ✓ canonical JSON and content hashes for snapshots and the audit trail
    ports.py         ✓ Protocol classes (see Ports)
    errors.py        ✓ issue codes and typed errors
    vocab.py         ✓ closed vocabularies: domains, engagement, rater kind, provenance kind; title → domain keywords
    rates.py         ✓ validate_rate: one validation path for a pay rate from any source
    agreement.py       Cohen's / Fleiss' kappa, Krippendorff's alpha, scorecards (S4)
  app/
    market.py        ✓ collect and extract use cases (review: S4)
    rates.py         ✓ load_rates use case; JobBoardRates (rates from accepted postings)
    reporting.py     ✓ named queries
    quality.py         ingest dataset, evaluate raters, run judge (S4–S5)
  adapters/
    sources/         ✓ ashby.py, http.py (gentle GET), registry.py (data/sources.toml)
    llm/             ✓ baseline.py (deterministic, no LLM), fake.py; LLM extractor in S4
    rates/           ✓ cited.py (data/rates.toml), bls.py (BLS OEWS hourly medians)
    storage/         ✓ sql_repository.py (shared SQL), sqlite_repository.py, postgres_repository.py, raw_store.py
    datasets/          summeval.py, ... (S4)
  schema/            ✓ sqlite.sql, postgres.sql = version 1 (shipped inside the package so `pfq init-db` finds them)
    migrations/      ✓ sqlite/, postgres/: numbered NNN_name.sql files applied in order (002_rate_observation.sql)
  queries/           ✓ pay_by_domain.sql, pay_transparency.sql, rates_by_domain.sql
  cli.py             ✓ `pfq` entry point and wiring
data/sources.toml    ✓ registry: [[source]] posting sources and [[rate_source]] rate sources, terms checks recorded per source
data/rates.toml      ✓ cited pay figures (hand-made, committed; every entry cites a public source)
scripts/source_census.py ✓ re-runnable census (counts only, stores nothing)
tests/               ✓ pytest: core/, adapters/, app/, test_cli.py
```

### Core rules (the Engineering Core)

The course calls the project's central, testable logic its "Engineering Core"; these rules are it. All are pure functions over plain data and are unit-testable without a database, network or API key.

1. **Pay normalization.** Convert a pay quote to an hourly USD figure.
   - Units and default conversions: `hour` ×1, `day` ÷8, `week` ÷40, `month` ÷(2080/12), `year` ÷2080. Constants live in one place in `core/pay.py` and are documented, not scattered.
   - `task` / `project` units are normalized only when the posting states a time per task; otherwise the quote is kept with `hourly_usd = NULL` and an issue code (`UNIT_NOT_NORMALIZABLE`).
   - Ranges keep both ends (`hourly_min_usd`, `hourly_max_usd`); a single figure sets both.
   - Money is `Decimal`, rounded to cents. Amounts accept `52,000`, `$52k` and `1.5M`.
   - Non-USD currencies: the quote is kept with empty hourly fields and `CURRENCY_UNSUPPORTED`. Conversion with a dated rate table is still **TBD**.
2. **Extraction validation** (`validate_extraction`). Turn an `ExtractionCandidate` into an accepted `Posting`, a rejection, or a review item.
   - **Reject** (`MISSING_FIELD`, `AMOUNT_INVALID`, `RANGE_INVERTED`, `UNIT_UNKNOWN`, `EVIDENCE_NOT_FOUND`):
     - Company or title is missing.
     - An amount is not positive, or the minimum is above the maximum.
     - The unit is not one of the allowed units.
     - The evidence check fails: each pay quote's evidence must appear in the posting text (ignoring case, dash style and whitespace), and its amounts must appear in that evidence. This is what stops invented numbers.
   - **Review** (`LOW_CONFIDENCE`, `OUT_OF_BAND`):
     - The extractor's confidence is below 0.7. A deterministic extractor reports no confidence and skips this check.
     - The hourly result is outside $5–$500.
     - Both thresholds are provisional until the extraction accuracy evaluation (Sprint 4).
   - Any reject code beats any review code.
3. **Agreement and rater quality.** Cohen's kappa (two raters), Fleiss' kappa and Krippendorff's alpha (many raters, missing labels allowed), per-rater scorecards (agreement with leave-one-out consensus or with expert consensus), and ambiguous-item detection (low per-item agreement).
4. **Rate validation** (`validate_rate`, `core/rates.py`). Turn a `RateCandidate` from any source into a `RateObservation` or a rejection. There is no review queue for rates.
   - **Vocabulary** (`VOCAB_UNKNOWN`). `domain`, `engagement`, `rater_kind` and `provenance_kind` must come from `core/vocab.py`. The schema's CHECK constraints list the same values (tested).
   - **Citation** (`CITATION_MISSING`). A job-board rate must link to its `raw_posting`; every other rate must cite a public source URL.
   - **Pay.** It reuses `normalize_pay_quote`. A rate that is not clean hourly USD is rejected (`UNIT_NOT_NORMALIZABLE`, `CURRENCY_UNSUPPORTED`, `AMOUNT_INVALID`, ...), because the table must hold comparable hourly figures.
   - **Plausibility** (`OUT_OF_BAND`). `RATE_POLICY` allows $1–$500/h. The floor is lower than the $5 used for postings, because published crowd wages (about $2/h median on Mechanical Turk) are real figures, not extraction errors.
5. **Judge validation.** An LLM judge score is accepted only if it is on the dataset's scale and parses cleanly; otherwise it is stored as a failed judge result and excluded from metrics.

**Rule: LLM output is untrusted.** Extractor and Judge adapters return *candidates*. Only Core validation turns a candidate into a value that is stored in an analysis table or shown to a user.

## Ports

Ports are `typing.Protocol` classes in `core/ports.py`. Use cases depend on these, never on concrete adapters. Every port has a fake used in tests.

| Port              | Method(s) (sketch)                                             | Real adapter                                                                           | Test fake                                       |
| ----------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `PostingSource` ✓ | `list_postings() -> Iterable[RawPostingDoc]`               | `AshbySource` (public job-board API); Greenhouse later                                 | `FakeSource`: fixed documents or a raised error  |
| `Extractor` ✓   | `extract(doc: RawPostingDoc) -> ExtractionCandidate`; `name`, `prompt_version` | `BaselineExtractor` (deterministic: structured compensation, else a pay regex). LLM client in S4 | `FakeExtractor`: scripted candidates, including invented pay and exceptions |
| `RateSource` ✓  | `list_rates() -> Iterable[RateCandidate]`                    | `CitedRates` (`data/rates.toml`), `BlsOewsRates` (BLS API), `JobBoardRates` (accepted postings; in `app/rates.py` because it reads the repository) | `FakeRates` in `tests/app/test_rates.py`; a fake fetch for BLS |
| `RawStore` ✓    | `put(slug, digest, bytes) -> path`; `get(path) -> bytes`     | `FileRawStore`: `data/raw/<source>/<sha256>.json`                                      | The same class on a temp folder                  |
| `Repository` ✓  | `apply_schema` (base schema + migrations), `upsert_source`, collection-run bookkeeping, `find_raw_posting` / `has_listing` / `insert_raw_posting` / `touch_raw_posting`, `pending_extraction`, `record_extraction`, `upsert_rate_source`, `insert_rate`, `current_posted_pay`, `query`, `count_rows`, `close` | `PostgresRepository` (Supabase); `SqliteRepository` (local) | Temporary SQLite file                            |
| `Judge`         | `score(item: Item, rubric: Rubric) -> JudgeCandidate`        | LLM client (provider **TBD**), S5                                                      | Returns scripted scores                         |
| `DatasetLoader` | `load() -> DatasetBundle` (dataset, items, raters, labels)   | One per public dataset (SummEval first), S4                                            | Small hand-made bundle                          |

`Repository` may later split into `MarketRepository` and `QualityRepository` if it grows too large; that split is a refactor, not a design change.

## Interface / API Boundary

The primary boundary is **CLI → use cases**. Each command builds a small request object, calls one use case, and receives a result object. The CLI never runs SQL, never calls an LLM, and never does pay or agreement math.

What crosses the boundary:

- **In:** the use case's arguments: a `SourceInfo` from the registry, port implementations built from config, and options such as `limit`. Request objects can be added if the argument lists grow.
- **Out:** plain result dataclasses: `CollectResult` (new / changed / unchanged), `ExtractResult` (accepted / review / rejected / failed, issue-code counts) and `QueryResult` (columns, rows). The CLI formats these as text tables or JSON (`--json`).
- **Errors:** domain and validation errors are returned as data or raised as typed exceptions from `core/errors.py`; the CLI maps them to messages and exit codes. Stack traces are not shown to the user by default.

Why it is useful: the same use cases can later sit behind a web UI or a scheduled job without change; tests can call use cases directly with fakes; and the CLI is thin enough to test with a few smoke tests.

The second boundary is **use cases → ports**. It keeps the Core testable without network or database, and lets a real LLM be swapped for a fake (or for a different provider) through configuration.

### CLI commands

| Command                                         | Use case                                                                     | Target sprint |
| ----------------------------------------------- | ---------------------------------------------------------------------------- | ------------- |
| `pfq init-db`                                 | Create the schema, or upgrade an existing database by applying newer migrations | S2 ✓ (migrations: S3 ✓) |
| `pfq sources`                                 | List registered sources and whether they may be collected                    | S2 ✓          |
| `pfq collect --source <slug>`                 | Pull postings from one source; store new or changed snapshots                | S2 ✓          |
| `pfq extract [--extractor baseline\|fake] [--limit N]` | Run extraction on unprocessed snapshots; validate; store or queue for review | S2 ✓ (LLM extractor: S4) |
| `pfq rates load --source <slug>`              | Load rates from one registered rate source through Core validation          | S3 ✓          |
| `pfq query <name> [--json]`                   | Run a named, committed SQL analysis (`pay_by_domain`, `pay_transparency`, `rates_by_domain`) | S2 ✓ (`rates_by_domain`: S3 ✓) |
| `pfq review list \| accept <id> \| reject <id>` | Work the low-confidence review queue                                         | S4            |
| `pfq ingest <dataset>`                        | Load a public multi-rater dataset                                            | S4            |
| `pfq evaluate --dataset <name>`               | Agreement metrics, rater scorecards, expert vs. crowd; optional judge run    | S4–S5        |
| `pfq report`                                  | Assemble the price-vs-value summary from Core results and SQL                | S5            |

Exit codes: `0` success; `1` handled error (validation, missing data, external service failure); `2` usage error (argparse default).

### Code path: `pfq extract` (Sprint 2)

This is the path that decides whether an extracted number can be trusted.

1. **`cli.main`** parses the arguments.
2. **`cmd_extract`** reads `.env` (environment variables win), then:
   - opens the repository chosen by the `DATABASE_URL` scheme (`open_repository`),
   - builds the extractor (`baseline` by default) and a `FileRawStore`,
   - calls one use case.
3. **`app.market.extract`** asks the repository for `pending_extraction(limit)`: the latest snapshot of each listing that has no extraction run yet. Older versions of a listing are skipped. For each pending snapshot it:
   1. **Loads the snapshot.** It reads the raw JSON from the raw store and rebuilds the `RawPostingDoc` (`doc_from_json`).
   2. **Calls `extractor.extract(doc)`.** The result is an `ExtractionCandidate`, which is untrusted.
      - If the extractor raises (an API error, for example), the posting is counted as `failed` and **not** recorded, so the next run retries it.
   3. **Calls `core.validation.validate_extraction(candidate, doc.text, policy)`**:
      - checks the required fields;
      - for each pay quote: the evidence check, then `normalize_pay_quote` (unit, range, currency, hourly conversion), then the plausibility band;
      - then the confidence check.
      - The resulting issue codes decide the outcome: any reject code → `rejected`; otherwise any review code → `review`; otherwise `accepted`.
   4. **Calls `repo.record_extraction(...)`.** In **one transaction** it always writes an `extraction_run` row, with the candidate JSON kept verbatim and the issues. Then it writes `posting` + `pay_quote` rows if accepted, or a `review_item` if sent to review. A rejected candidate leaves only the audit row.
4. **`ExtractResult`** carries the counts and the issue-code tallies back to the CLI, which prints e.g. `Extracted 163 postings with baseline-regex: 160 accepted, 2 sent to review, 1 rejected`, followed by the codes.

Key decision: only rows written in step 3.4 for accepted candidates feed the analysis queries. An invented or implausible figure can be inspected in `extraction_run`, but it never reaches `pay_by_domain`.

### Code path: `pfq rates load` (Sprint 3: the code path explained for this sprint)

This path decides whether a pay figure, from any source, may enter the rate table.

1. **`cli.main`** parses `rates load --source <slug>` and calls **`cmd_rates_load`**.
2. **`cmd_rates_load`**:
   - reads the `[[rate_source]]` registry (`registry.load_rate_registry`, `data/sources.toml`);
   - **refuses an unknown slug, or a source with `terms_checked = false`, before anything is built or fetched** (exit code 1);
   - opens the repository from `DATABASE_URL`;
   - builds one adapter with `build_rate_source`, by registry `kind`:
     - `cited` → `CitedRates(path)`;
     - `bls_oews` → `BlsOewsRates(occupations, retrieved_on=today)`;
     - `job_boards` → `JobBoardRates(repo, FileRawStore)`.
3. **`app.rates.load_rates`** checks the terms flag again (the use case does not trust its caller), then calls `repo.upsert_rate_source`. For each `RateCandidate` from `source.list_rates()`:
   - **Candidates differ by source, but the next steps don't.**
     - `CitedRates` parses one `[[rate]]` entry.
     - `BlsOewsRates` makes one GET per occupation to the BLS API through the gentle `get_json`, takes the latest annual point, and turns a top-coded or non-numeric value into an empty amount. The citation note carries the retrieval date and the disclaimer the BLS terms require.
     - `JobBoardRates` reads `repo.current_posted_pay()` (current, Core-accepted, hourly-normalizable quotes). It then reads the snapshot's `employmentType` from the raw store to set `engagement`, and `domain_from_title` to set `domain`. No company name is carried over.
   - **`core.rates.validate_rate(candidate)`** checks the vocabulary, then the citation (a URL, or `raw_posting_id` for job-board rates), then normalizes pay with `normalize_pay_quote`, then applies the $1–$500/h band. **Any issue rejects.** A rejection is counted with its issue codes and nothing is written.
   - **`repo.insert_rate(...)`** runs in one transaction. It writes the observation unless `(rate_source_id, external_key)` is already stored, in which case it changes nothing and reports `unchanged`. A stored rate is never overwritten, so a corrected figure needs a new id.
4. A **`LoadRatesResult`** goes back to the CLI, which prints for example `cited-rates: 7 rates: 7 new, 0 unchanged, 0 rejected`, then the issue-code tallies.

Key decision: `rate_observation` holds only validated, cited, hourly-USD figures and has no company column. `rates_by_domain` can therefore aggregate across sources without knowing where a number came from, and it cannot rank named companies (`AGENTS.md` §4.8).

## Data Sources

### Source census (2026-11-09)

Method: `scripts/source_census.py` queries the public job-board APIs for about 15 AI human-data companies, using one request per second and a generic client name. It prints counts only and stores nothing.

| Board | Company | Postings | With $ pay | With hourly pay |
|---|---|---|---|---|
| Greenhouse `scaleai` | Scale AI | 170 | 117 | 6 |
| Ashby `mercor` | Mercor | 86 | 86 | 6 |
| Ashby `handshake` | Handshake | 77 | 73 | 3 |
| Greenhouse `turing` | Turing | 46 | 23 | 0 |
| Greenhouse `snorkelai` | Snorkel AI | 43 | 42 | 1 |
| Ashby `surge-ai` | Surge AI | 35 | 0 | 0 |
| Greenhouse `prolific` | Prolific | 25 | 3 | 0 |
| Greenhouse `invisibletech` | Invisible | 20 | 14 | 0 |
| Greenhouse `toloka` | Toloka | 16 | 0 | 0 |
| Greenhouse `labelbox` | Labelbox | 10 | 8 | 0 |

No public board was found for micro1, DataAnnotation, Outlier or Alignerr.

**Finding: the market has two segments.** The public job-board APIs list mostly **staff roles**, meaning the companies' own employees, paid annual salaries. The **expert contractor gigs**, which are what "price of expertise" most directly means, are mostly on the companies' own platform sites (work.mercor.com, outlier.ai, dataannotation.tech, alignerr.com). Those need a per-site terms review before any collection. The data model records a `segment` (`staff` / `expert`) per source.

### Terms and robots checks

| Host | robots.txt | Provider docs |
|---|---|---|
| `boards-api.greenhouse.io` | Allows everything except `/embed/` | "Job Board data is publicly available, so authentication is not required for any GET endpoints." No rate limits or terms page linked |
| `api.ashbyhq.com` | None (401) | Unauthenticated GET. Described as a feed for an organization's own careers page. No rate limits, no terms page, no third-party restrictions stated |
| `work.mercor.com` | Allows `/` but disallows `/api/` | `mercor.com/terms` §2.2(b), (c), (e) prohibit scrapers and "automated or non-automated" copying (read 2026-11-09) |
| `alignerr.com` | Allows general crawling | Terms (read 2026-11-09 by an AI research subagent; quotes recorded in `docs/ai-usage.md`) prohibit crawling or scraping "through use of manual or automated means" (read 2026-11-09) |
| `outlier.ai`, `dataannotation.tech`, `micro1.ai` | Allow general crawling | Not fully read. Not needed: platform sites are excluded by decision |
| `api.bls.gov` (rate source) | n/a (API) | `bls.gov/developers/termsOfService.htm`: no end-use controls. Cite the retrieval date and state that "BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov." BLS material is public domain. v1 without a key: 25 queries per day |

Neither provider prohibits or invites third-party use. Collection therefore stays minimal: one request per board per run, about weekly, with a generic client name, only listed postings, and no application endpoints.

### Chosen sources

- **Sprint 2:** Ashby, for Mercor and Handshake. It has structured compensation (`compensation.summaryComponents[]` with type, interval, currency, min and max) and plain-text descriptions, and it includes the strategy and ops roles this project's owner is targeting.
- **Backup:** Greenhouse, for Scale AI. Pay appears in the description text only.
- **Sprint 3 decision: no company websites or work platforms.** Their terms forbid collection (above), and this public project takes nothing from these companies' own work (`AGENTS.md` §4.7). Expert pay comes instead from:
  - **contract roles that already appear on the public job boards**: `engagement` is read from each posting's structured employment type (e.g. Handshake's contract "AI Red Teamer" roles at $65–158/h);
  - **cited published figures** (`data/rates.toml`): papers that state their raters' pay (SummEval, MT-Bench, GPQA), and Prolific's researcher guidance;
  - **BLS OEWS hourly medians** for 8 expert occupations, as the outside option.

The registry lives in `data/sources.toml`. A source with `terms_checked = false` cannot be collected.

## Data Model and Persistence Plan

### Database approach

Hybrid: one `Repository` port, two adapters, chosen by `DATABASE_URL` in `.env`.

| | Supabase Postgres | Local SQLite |
|---|---|---|
| Role | System of record for collected and cleaned data; where weekly collection writes; where the SQL analyses run | Automated tests and offline/demo runs; lets a reviewer run the tool with no credentials |
| `DATABASE_URL` | `postgresql://...` connection string from the Supabase dashboard (session pooler if the network is IPv4-only) | `sqlite:///./pfq.db` (file git-ignored) |
| Driver | `psycopg` 3 over the connection string, **not** the Supabase REST client, so SQL stays the interface. Server-side prepared statements are off, because Supabase's poolers may not keep them | Standard-library `sqlite3` |
| Schema | `src/paying_for_quality/schema/postgres.sql`, applied inside schema `PFQ_DB_SCHEMA` (default `pfq`) via `search_path` | `src/paying_for_quality/schema/sqlite.sql` |

- **Plain SQL, written once.** `SqlRepository` holds all repository SQL, written with `?` placeholders. Each subclass changes only:
  - the placeholder style (`%s` for psycopg),
  - JSON parameters (`::jsonb` casts in Postgres),
  - timestamps (`timestamptz` vs. ISO-8601 text),
  - numbers (`NUMERIC` vs. `REAL`).
- **Named queries are portable too.** `pay_by_domain` computes its median with `ROW_NUMBER()` / `COUNT() OVER`, which both databases support, so the same query file runs on both. The query tests prove this by running against both.
- **Schemas kept in sync.** The two schema files must declare the same tables and columns, and `test_schema_parity.py` checks this.
- **IDs:** integer surrogate keys on every table (`GENERATED ALWAYS AS IDENTITY` in Postgres, `INTEGER PRIMARY KEY` in SQLite), plus `UNIQUE` constraints on natural keys so re-running a command is idempotent.
- **Timestamps** are UTC.
- **Schema version and migrations.**
  - A one-row `schema_version` table tracks the version.
  - The base schema files are version 1. Each later change is a numbered file in `schema/migrations/<dialect>/NNN_name.sql`.
  - `pfq init-db` (`SqlRepository.apply_schema`) creates the base schema if missing, then applies every migration newer than the stored version. Each migration runs in one transaction together with its version bump, so a failed migration leaves the previous version.
  - A fresh database and an upgraded one end up with identical tables (tested). Sprint 3 added `002_rate_observation.sql`.
  - No migration library is used: numbered SQL files are enough for one owner and two dialects. Foreign keys are enforced in both databases (`PRAGMA foreign_keys = ON` in SQLite).
- **Supabase exposure.** Tables live in a dedicated `pfq` schema rather than `public`, so they are not served by Supabase's auto-generated Data API. Row Level Security is enabled as a second guard. Only the server-side connection string is used; no anon or service keys are needed.
- **Three layers:** **raw** (what was fetched), **cleaned** (Core-validated rows), **analysis** (named queries over cleaned rows only). "Current" postings are the latest snapshot of each listing and the latest accepted extraction of that snapshot.

### Market tables (Sprint 2; rate tables Sprint 3; quality tables are added in Sprint 4)

| Table              | Key fields                                                                                                                                                                     | Notes                                                                                                                                                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `source`         | `id`, `slug` (unique), `kind`, `board`, `company`, `segment` (staff/expert), `terms_checked`, `robots_checked_at`, `terms_note`                                 | One row per collected board, copied from `data/sources.toml`; records the robots.txt / terms check required by `AGENTS.md` §4                                                                                     |
| `collection_run` | `id`, `source_id`, `started_at`, `finished_at`, `status` (running/ok/error), `n_new`, `n_changed`, `n_unchanged`, `error`                                     | One row per `pfq collect` run; observability for weekly collection. Failed runs keep their error message                                                                                                         |
| `raw_posting`    | `id`, `source_id`, `external_id`, `content_hash`, `raw_path`, `url`, `title`, `first_seen_at`, `last_seen_at`                                                  | Unique on (`source_id`, `external_id`, `content_hash`). Unchanged content only bumps `last_seen_at`; changed content inserts a new row. Body stored as a file under `data/raw/<source>/<hash>`, not in git |
| `extraction_run` | `id`, `raw_posting_id`, `extractor` (model or `fake`), `prompt_version`, `created_at`, `candidate_json`, `outcome` (accepted/rejected/review), `issues_json` | Audit trail: the untrusted LLM output is kept verbatim next to Core's verdict                                                                                                                                        |
| `posting`        | `id`, `raw_posting_id`, `extraction_run_id`, `company`, `platform`, `title`, `domain`, `seniority`, `credentials_json`, `posted_at`                        | Only Core-accepted extractions. Latest accepted run per `raw_posting` is current. `domain` currently holds the **source's department** (baseline extractor), not the expertise vocabulary; the vocabulary domain lives on `rate_observation` |
| `pay_quote`      | `id`, `posting_id`, `amount_min`, `amount_max`, `currency`, `unit`, `hourly_min_usd`, `hourly_max_usd`, `evidence`                                           | 0..n per posting (e.g. tiers or regions). `hourly_*` are NULL when not normalizable                                                                                                                                |
| `review_item`    | `id`, `extraction_run_id`, `status` (open/accepted/rejected), `decided_at`, `note`                                                                                   | Extractions sent to review (low confidence or out-of-band pay) waiting for a human decision. Extractor *failures* (exceptions) are counted but not recorded, so they are retried on the next run |
| `rate_source`    | `id`, `slug` (unique), `kind`, `provenance_kind`, `terms_checked`, `checked_at`, `terms_note` | One row per `[[rate_source]]` registry entry (Sprint 3) |
| `rate_observation` | `id`, `rate_source_id`, `external_key`, `amount_min`, `amount_max`, `currency`, `unit`, `hourly_min_usd`, `hourly_max_usd`, `engagement`, `rater_kind`, `domain`, `occupation`, `region`, `as_of`, `provenance_kind`, `citation_url`, `citation_note`, `raw_posting_id`, `loaded_at` | Every validated pay rate from any source (Sprint 3). Unique on (`rate_source_id`, `external_key`). CHECK constraints hold the Core vocabularies. **No company column**, by design. `raw_posting_id` links job-board rates to their snapshot |

### Quality tables

| Table         | Key fields                                                                                                                | Notes                                                                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `dataset`   | `id`, `slug` (unique), `name`, `license`, `source_url`, `origin` (public/synthetic)                           | License recorded per `AGENTS.md` §4.6                                                                                                   |
| `item`      | `id`, `dataset_id`, `external_id`, `payload_json`                                                                 | Unique on (`dataset_id`, `external_id`)                                                                                                |
| `rater`     | `id`, `dataset_id`, `external_id`, `kind` (expert/crowd/llm_judge)                                                | LLM judges are raters, so all agreement code treats them the same way                                                                      |
| `label`     | `id`, `item_id`, `rater_id`, `criterion`, `value`                                                               | Unique on (`item_id`, `rater_id`, `criterion`); `criterion` covers multi-aspect datasets (e.g. SummEval's coherence, fluency, ...) |
| `judge_run` | `id`, `dataset_id`, `rater_id`, `model`, `prompt_version`, `created_at`, `n_ok`, `n_failed`, `cost_usd` | Bookkeeping for each LLM-judge pass; the judge's accepted scores land in `label`                                                         |

### Relationships

- `source 1─n raw_posting 1─n extraction_run`; an accepted run yields `1 posting 1─n pay_quote`; a review outcome yields `1 review_item`.
- `dataset 1─n item`, `dataset 1─n rater`, `item n─n rater` through `label`.
- `rate_source 1─n rate_observation`; a job-board rate optionally links `n─1 raw_posting`.
- **Vocabularies** (`core/vocab.py`, also CHECK constraints in the schema):
  - `engagement`: `employee`, `contractor`, `intern`, `temporary`, `unknown`;
  - `rater_kind` (what labor a rate prices): `expert`, `crowd`, `staff`, `outside_option` (what the expert earns outside AI data work, e.g. from BLS);
  - `provenance_kind`: `job_board`, `gov_statistic`, `literature`, `dataset_paper`, `self_timed`.

  `source.segment` (staff/expert) is a coarse **default per posting source**. `rate_observation.rater_kind` is set **per rate**: a contract role on a "staff" job board becomes an `expert` rate.
- Market and quality families share no foreign keys. They meet in analysis views and in the report, joined on `domain`. The domain vocabulary is fixed in `core/vocab.py` (Sprint 3), aligned with MT-Bench's categories: `coding`, `math`, `stem_science`, `medicine`, `law`, `finance`, `writing_humanities`, `languages`, `reasoning_general`, `none`.

### What persists vs. what is transient

| Persists (database or `data/raw/`)                | Transient (never stored)                                               |
| --------------------------------------------------- | ---------------------------------------------------------------------- |
| Raw posting snapshots and their hashes              | HTTP sessions, retries, rate-limit state                               |
| Every extraction candidate, verdict and issue codes | Prompts after rendering (only `prompt_version` is stored)            |
| Accepted postings and pay quotes                    | Agreement metrics and scorecards (recomputed from `label` on demand) |
| Review decisions                                    | Intermediate dataframes / query results                                |
| Dataset items, raters, labels; judge runs and costs | API keys and other secrets (only in `.env`, never in the DB or logs) |

Metrics are recomputed rather than stored so that they always match the current labels. If a computation becomes slow, a cached results table can be added later.

**Non-public rater data** (synthetic data now; the research experiment later, only after approval) goes in a **separate database** (its own Supabase project or local SQLite file) with the same schema and `dataset.origin` set accordingly, so it never mixes with public data (`AGENTS.md` §4.5). The future 2×2 experiment is then a new dataset plus a `condition` attribute on items or raters, not a new architecture.

## Verification Approach by Layer

| Layer           | How it is tested                                                                                                    | Needs DB / network / key? |
| --------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| Core            | Unit tests on pay normalization, validation issue codes, agreement metrics against hand-computed or textbook values | No                        |
| Use cases       | Tests with `FakeSource`, `FakeExtractor`, a temp `FileRawStore` and the real repository (the `repo` fixture) | No                        |
| Repository + queries | One `repo` fixture runs the repository contract, use-case and query tests on a temporary SQLite file by default, and **also on Supabase Postgres** with `pytest -m supabase` (each run in a throwaway `pfq_test_<random>` schema, dropped afterwards) | SQLite: no. Postgres: yes (opt-in) |
| Schema parity   | Test that `postgres.sql` and `sqlite.sql` declare the same tables and columns, and that RLS is enabled on every Postgres table | No                        |
| Source adapter  | `AshbySource` against a small hand-made response in the documented shape (no real data committed)                  | No                        |
| CLI             | Smoke tests calling `main(argv)` with a fake fetch: the full collect → extract → query path, exit codes, and a check that error messages never show the password | No                        |
| Real LLM / HTTP | Manual or opt-in runs only, recorded in `docs/sprint-status.md`                                                   | Yes                       |

Test runner: **pytest**. The default command (`pytest` from the repo root) needs no network, Supabase credentials or API key. The verification intent for specific behaviors lives in `docs/requirements.md`.

## Dependencies

Policy: **Core stays standard-library only, permanently.** Adapters and analysis may add a dependency only when the standard library is clearly worse, and each one is listed here with its reason.

| Dependency | Status | Used by | Why |
|---|---|---|---|
| `pytest` ≥ 8 (extra `dev`) | In use | Tests | Clearer assertions, fixtures and parametrization than `unittest`; the `supabase` marker keeps live-database tests out of the default run |
| `psycopg[binary]` ≥ 3.2 (extra `postgres`) | In use | `PostgresRepository` | Python's standard library cannot talk to Postgres. Psycopg 3 is the maintained driver; the binary build needs no local libpq |
| HTTP client | Decided: none (standard-library `urllib`) | `adapters/sources/http.py` | One JSON GET per board per run doesn't justify a dependency |
| `.env` loading | Decided: none (15-line parser in `cli.py`) | CLI | `KEY=VALUE` lines only; python-dotenv isn't needed |
| LLM provider SDK | **TBD** | Extractor / Judge adapters | Depends on provider choice; plain HTTP is the alternative |
| numpy / pandas / statsmodels | **TBD**, Exploration Zone | Hedonic regression | Only if the regression moves into scope |

## Open Decisions

| # | Decision                                                  | Default until decided                    |
| - | --------------------------------------------------------- | ---------------------------------------- |
| 1 | LLM provider and model (a low-cost "flash"-class model is the leading option); exact monthly cap (low). Needed in S4 | Fake extractor/judge only |
| 2 | LLM SDK vs. plain HTTP                                    | Decided with the provider (S4)           |
| 3 | Non-USD pay conversion                                    | Flag (`CURRENCY_UNSUPPORTED`) and exclude from hourly figures |
| 4 | Final plausibility band and confidence threshold          | Provisional $5–$500/h and 0.7, reviewed after the S4 accuracy evaluation. Rates use their own $1–$500/h band (`RATE_POLICY`) |
| 5 | How job-board titles map to domains beyond keywords, and whether `contractor`/`temporary` always means `expert` | Provisional keyword table (`domain_from_title`) and rule (`rater_kind_for`) until LLM extraction in S4 |

**Decided in Sprint 1:** Supabase Postgres as the system of record with local SQLite for tests (hybrid); pytest as the test runner.
**Decided in Sprint 2:** psycopg 3; no HTTP or dotenv dependency; Ashby (Mercor, Handshake) as the first source; staff vs. expert market segments; a deterministic baseline extractor before any LLM.
**Decided in Sprint 3:**
- the "Cost of Quality" framing;
- no company websites or work platforms; job listings only from public job-board APIs;
- aggregate-only publication;
- a cited-rates file plus BLS OEWS as pay sources;
- the domain vocabulary;
- numbered SQL migrations;
- the LLM extractor moved to S4.

## What Changed This Sprint

**Sprint 1:** first draft of components, ports, CLI boundary, data model and persistence plan. Database changed from SQLite-only to Supabase Postgres plus local SQLite behind one `Repository` port; pytest chosen. No code yet.

**Sprint 2:**
- **Core.** Pay normalization; extraction validation with the evidence check; issue codes; ports; serialization.
- **New port.** `RawStore`, added so raw snapshots stay on disk under `data/raw/` while the database stores only their paths and hashes.
- **Storage.** The market-side tables exist in both databases behind one shared `SqlRepository`.
- **Source.** The Ashby source adapter and the source registry.
- **Extraction.** The deterministic `BaselineExtractor`, plus the fake.
- **Analysis.** Two portable named queries.
- **CLI.** The `pfq` commands `init-db`, `sources`, `collect`, `extract` and `query`.
- **Deviations from the Sprint 1 design:**
  - The schema files moved from `data/schema/` into the package, so an installed `pfq` can find them.
  - `source` gained `segment`, `board`, `company` and `terms_checked`. `raw_posting` gained `title`. `collection_run` gained `n_changed`.
  - The Extractor port takes the whole `RawPostingDoc` rather than only its text, so structured source fields such as Ashby's compensation can be used.

**Sprint 3: the source-agnostic rate model.**
- **Why the foundational docs changed.** The Sprint 2 census showed that expert contractor pay lives mostly on the companies' own platform sites. Their terms forbid collection (Mercor, Alignerr), and this is a public project aimed at the same industry. The owner therefore changed the price side:
  - pay is now a **cited input from neutral public sources**, not something taken from the companies;
  - the project is framed as "Cost of Quality".

  The posting path stays, as one rate source among several.
- **Core.** `core/vocab.py` (closed vocabularies, title → domain keywords) and `core/rates.py` (`validate_rate`). New reject codes `CITATION_MISSING` and `VOCAB_UNKNOWN`.
- **New port.** `RateSource`. New repository methods: `upsert_rate_source`, `insert_rate`, `current_posted_pay`. `apply_schema` now returns the migrations it applied.
- **Storage.**
  - numbered migrations (`schema/migrations/`);
  - tables `rate_source` and `rate_observation`;
  - schema version 2. Parity tests now cover base + migrations, and check the vocabulary constraints against Core.
- **Adapters and use case.** `CitedRates`, `BlsOewsRates`, `JobBoardRates`, `load_rates`.
- **CLI.** `pfq rates load --source <slug>`. `pfq sources` lists rate sources, and `pfq init-db` reports the version.
- **Analysis.** The `rates_by_domain` query.
- **Data.**
  - `data/rates.toml` (7 cited figures);
  - `[[rate_source]]` entries in `data/sources.toml`;
  - `mercor-platform` marked as not collected, by decision.
- **Doc corrections from the Sprint 3 drift check:**
  - the review queue does not hold failed extractions;
  - transactions belong to the repository;
  - `posting.domain` is the source department;
  - the full `Repository` method list;
  - the `--fake` flag is `--extractor fake`.
