# Paying for Quality: the Cost of Quality in AI Data Work

An analysis tool for the AI human-data industry: the companies (Mercor, Scale, Surge, Invisible and others) that hire experts to produce AI training and evaluation data.

## The Question

Expert AI-training work often pays far more than comparable generalist work. This project asks:

> **Is the pay premium for expertise justified by the quality difference experts produce, and do LLM judges change that trade-off?**

Put practically: **for a labeling job, which mix of experts, crowd raters and LLM judges reaches the quality you need at the lowest cost?** It answers from two sides:

| Side | Measures | How |
|---|---|---|
| **Price** | What an hour of expert, crowd and staff work costs, and what the expert earns elsewhere | Load pay rates from neutral public sources, validate and normalize them to hourly USD in one cited table: public job-board APIs, BLS wage statistics, and published figures from papers and researcher guidance |
| **Quality** | The *value* of expertise | Load public datasets where several raters labeled the same items, measure agreement and rater quality, and compare expert, crowd and LLM-judge labels |

**Sourcing rule:** job listings come only from public job-board APIs, never from a company's own website or work platform. Job-board results are published as industry aggregates, never as named-company comparisons (`AGENTS.md` §4).

The economics: efficiency-wage theory says firms overpay when quality is hard to monitor. LLM judges make monitoring cheap, which should shrink the premium.

## Who It Is For

- People who run human-data projects (pricing, recruiting, quality control) and want market and quality benchmarks.
- Contractors deciding what expert AI-training work is worth.
- Researchers studying this labor market.

## Current Sprint Status

**Sprint 4: Strengthen and Review (complete on `sprint-4`).** The strengthening work is **database failure handling**. Every connection failure used to give the same "check DATABASE_URL" message whatever the cause, and errors in the middle of a command showed only "unexpected OperationalError".
- Every database error now ends in a handled message that names the likely cause and the next step, and never repeats the host or user (`adapters/storage/db_errors.py`).
- Connecting is retried only for transient causes (timeout, no free slots). Operations are never replayed: the server has rolled them back, and every load is idempotent, so the message says to re-run.
- The Supabase test fixture no longer leaves throwaway schemas behind when a connection dies (two such orphans were found).
- First quality slice (original plan): Krippendorff's alpha in Core, which reproduces the published worked example, plus `pfq quality summeval` (expert vs. crowd per dimension; real file not downloaded yet).

Tests: `pytest` gives **186 passed** with no credentials (Sprint 3: 133); **32 passed** against Supabase on the final run (an earlier run hit a dropped connection; see `docs/sprint-status.md`).

Known limitation: the cause of the intermittent dropped connections on Supabase's pooler is still unproven. They are now reported clearly and cleaned up, not prevented.
Peer feedback: not received (see `docs/sprint-status.md`).
Next (Sprint 5): the LLM judge comparison, the real SummEval run, the LLM extractor and the first price-vs-value summary.

Details: [`docs/sprint-status.md`](docs/sprint-status.md).

## Planned Components

1. **Collector** — collection of public job-board postings (robots.txt and terms respected). Built.
2. **Extraction** — a deterministic baseline now; an LLM proposes structured fields in Sprint 5. Core validates either and normalizes pay to hourly.
3. **Rate model** — pay rates from any source (cited file, BLS, job boards) in one validated, cited table. Built in Sprint 3.
4. **Storage + SQL** — Supabase (Postgres) with raw, cleaned and analysis layers; tests use a local database so they run without credentials.
5. **Dataset ingest** — public multi-rater datasets. A SummEval reader is built (Sprint 4); storing ratings in the database comes in Sprint 5.
6. **Rater quality** — agreement metrics, rater scorecards, expert vs. crowd. Krippendorff's alpha and expert vs. crowd are built (Sprint 4); scorecards are not.
7. **LLM-judge audit** — judge–expert agreement, bias checks, cost of human vs. LLM labeling.
8. **Synthesis** — the cost of quality: cost per unit of agreement for expert, crowd and LLM-judge labeling.

What is committed for the class versus kept as Exploration Zone is defined in [`docs/requirements.md`](docs/requirements.md).

## Setup

Python 3.11+ (developed on 3.13).

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[dev,postgres]"
.venv/bin/pytest                 # runs with no .env, network or database
cp .env.example .env             # then set DATABASE_URL (Supabase session-pooler URI); never commit .env
```

To try the tool without Supabase, set `DATABASE_URL=sqlite:///./pfq.db` in `.env`.

## Run

```bash
.venv/bin/pfq init-db                          # create the schema, or migrate an existing database
.venv/bin/pfq sources                          # registered sources and whether they may be collected
.venv/bin/pfq collect --source ashby-mercor    # one request to a public job-board API
.venv/bin/pfq extract                          # baseline extractor + Core validation
.venv/bin/pfq query pay_by_domain              # or pay_transparency; add --json
.venv/bin/pfq rates load --source cited-rates  # data/rates.toml; also: bls-oews (live BLS API), job-boards
.venv/bin/pfq query rates_by_domain            # median hourly rate by domain and rater kind
.venv/bin/pfq quality summeval                 # alpha and expert vs. crowd; needs the SummEval file in data/raw/summeval/
.venv/bin/pytest -m supabase                   # optional: tests against Supabase (needs PFQ_TEST_DATABASE_URL)
```

## Dependencies

Each is justified in [`docs/architecture.md`](docs/architecture.md#dependencies).
- `psycopg[binary]`: the Postgres driver for Supabase.
- `pytest`: tests.

Core (including the agreement math), the SQLite path, HTTP, `.env` loading and the connect retry use only the standard library.

## Data and Ethics

- **Allowed:** public job-board API postings, official statistics, published figures and public datasets. Never a company's own website or work platform, and no content from private contract work.
- **Citations:** every hand-entered rate cites its source (`data/rates.toml`).
- **Aggregates only:** job-board results are published as aggregates.
- Raw data is kept out of git. See `AGENTS.md` §4.

BLS data is retrieved through the BLS Public Data API (dates in each record's citation). BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov.

## Documentation

- [`docs/requirements.md`](docs/requirements.md) — requirements and acceptance criteria
- [`docs/architecture.md`](docs/architecture.md) — components, boundaries, data model
- [`docs/sprint-status.md`](docs/sprint-status.md) — detailed progress and verification
- [`docs/ai-usage.md`](docs/ai-usage.md) — consequential AI decisions
- [`AGENTS.md`](AGENTS.md) — rules for AI-assisted work in this repository

## Known Limitations

- **Small expert sample.** Few public job-board postings are contract expert roles, and cited figures are a handful. Every query row shows `n`; none is a market estimate.
- **Provisional rules.** Domain comes from title keywords; contract and temporary roles are treated as expert work. LLM extraction replaces both in Sprint 5.
- **Cited figures differ in date and meaning** (a platform minimum vs. a paper's average). Each citation note says which.
- **BLS** returns only the latest estimates, and excludes the self-employed.
- No LLM extraction yet; `pfq review` is not built; non-USD pay is excluded from hourly figures.
- The quality side has started with agreement metrics only. The SummEval file has not been run yet, and rater scorecards, stored labels and LLM judges are not built. No human raters are recruited; it uses public datasets.
- Collection is run by hand.
