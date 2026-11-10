# Paying for Quality

An analysis tool for the AI human-data industry: the companies (Mercor, Scale, Surge, Invisible and others) that hire experts to produce AI training and evaluation data.

## The Question

Expert AI-training work often pays far more than comparable generalist work. This project asks:

> **Is the pay premium for expertise justified by the quality difference experts produce, and do LLM judges change that trade-off?**

It answers the question from two sides:

| Side | Measures | How |
|---|---|---|
| **Market** | The *price* of expertise | Collect public job postings, extract pay and requirements with an LLM, validate them, and estimate what credentials, domains and platforms add to pay |
| **Quality** | The *value* of expertise | Load public datasets where several raters labeled the same items, measure agreement and rater quality, and compare expert, crowd and LLM-judge labels |

The economics: efficiency-wage theory says firms overpay when quality is hard to monitor. LLM judges make monitoring cheap, which should shrink the premium.

## Who It Is For

- People who run human-data projects (pricing, recruiting, quality control) and want market and quality benchmarks.
- Contractors deciding what expert AI-training work is worth.
- Researchers studying this labor market.

## Current Sprint Status

**Sprint 2: Narrow Working System (in progress).** The market pipeline works end to end on Supabase:
- `pfq collect` pulls public postings (Ashby: Mercor, Handshake).
- `pfq extract` runs a deterministic baseline extractor through Core validation. A pay figure counts only if it is quoted in the posting.
- `pfq query` reports median hourly pay and pay transparency.

The real run collected 163 postings: 160 accepted, 2 sent to review and 1 rejected. `pytest` shows 89 passing with no credentials, plus 25 passing against Supabase.

Next (Sprint 3): LLM extraction measured against about 100 hand-labeled postings, and a terms review of the expert-gig platforms.

Details: [`docs/sprint-status.md`](docs/sprint-status.md).

## Planned Components

1. **Collector** — scheduled collection of public postings (robots.txt and terms respected).
2. **Extraction** — an LLM proposes structured fields; the Core validates them and normalizes pay to hourly.
3. **Pay analysis** — pay index, credential premiums (hedonic regression), pay spread across platforms.
4. **Storage + SQL** — Supabase (Postgres) with raw, cleaned and analysis layers; tests use a local database so they run without credentials.
5. **Dataset ingest** — public multi-rater datasets (candidates TBD after the dataset check).
6. **Rater quality** — agreement metrics, rater scorecards, expert vs. crowd.
7. **LLM-judge audit** — judge–expert agreement, bias checks, cost of human vs. LLM labeling.
8. **Synthesis** — price of expertise vs. value of expertise.

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
.venv/bin/pfq init-db                          # create the schema
.venv/bin/pfq sources                          # registered sources and whether they may be collected
.venv/bin/pfq collect --source ashby-mercor    # one request to a public job-board API
.venv/bin/pfq extract                          # baseline extractor + Core validation
.venv/bin/pfq query pay_by_domain              # or pay_transparency; add --json
.venv/bin/pytest -m supabase                   # optional: tests against Supabase (needs PFQ_TEST_DATABASE_URL)
```

## Dependencies

Each is justified in [`docs/architecture.md`](docs/architecture.md#dependencies).
- `psycopg[binary]`: the Postgres driver for Supabase.
- `pytest`: tests.

Core, the SQLite path, HTTP and `.env` loading use only the standard library.

## Data and Ethics

Public postings and public datasets only. No content from private contract work. Raw data is kept out of git. See `AGENTS.md` §4.

## Documentation

- [`docs/requirements.md`](docs/requirements.md) — requirements and acceptance criteria
- [`docs/architecture.md`](docs/architecture.md) — components, boundaries, data model
- [`docs/sprint-status.md`](docs/sprint-status.md) — detailed progress and verification
- [`docs/ai-usage.md`](docs/ai-usage.md) — consequential AI decisions
- [`AGENTS.md`](AGENTS.md) — rules for AI-assisted work in this repository

## Known Limitations

- **Staff roles only so far.** Public job-board APIs list the companies' own employees. Expert contractor gigs are on platform sites that are blocked until their terms are reviewed.
- **No LLM extraction yet.** The baseline extractor uses structured compensation or a regex, and department stands in for domain.
- Non-USD pay is kept but excluded from hourly figures. Validation thresholds are provisional.
- The quality side (rater agreement, LLM judges) is not started.
- The market time series starts only when collection starts; history before that depends on archived pages (TBD).
- No human raters are recruited; the quality side uses public datasets.
