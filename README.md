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

**Sprint 1 — Define and Establish (in progress).** Baseline files are set up. First drafts of the requirements, architecture and persistence plan are written. Decisions: Supabase (Postgres) is the database and pytest is the test runner. Next: the source and dataset census, then the first Core behavior (pay normalization) with a test. No feature code yet.

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

TBD — added once the first code lands in Sprint 1. Python 3.11+.

```bash
cp .env.example .env   # fill in local values; never commit .env
```

## Dependencies

TBD. Every dependency will be justified in [`docs/architecture.md`](docs/architecture.md).

## Data and Ethics

Public postings and public datasets only. No content from private contract work. Raw data is kept out of git. See `AGENTS.md` §4.

## Documentation

- [`docs/requirements.md`](docs/requirements.md) — requirements and acceptance criteria
- [`docs/architecture.md`](docs/architecture.md) — components, boundaries, data model
- [`docs/sprint-status.md`](docs/sprint-status.md) — detailed progress and verification
- [`docs/ai-usage.md`](docs/ai-usage.md) — consequential AI decisions
- [`AGENTS.md`](AGENTS.md) — rules for AI-assisted work in this repository

## Known Limitations

- Nothing is implemented yet.
- The market time series starts only when collection starts; history before that depends on archived pages (TBD).
- No human raters are recruited; the quality side uses public datasets.
