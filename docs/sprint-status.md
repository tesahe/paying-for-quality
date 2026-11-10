# Sprint Status

## Sprint 2: Narrow Working System

**Branch:** `sprint-2` · **Status:** in progress (implementation and docs done; demo recording and merge pending)

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

None received yet.

---

## Sprint 1: Define and Establish

**Branch:** `sprint-1` · **Status:** complete (merged into `main`, branch kept)

- Baseline files; first drafts of the requirements (8 FRs, 8 constraints, acceptance criteria, verification intent for 4 behaviors) and of the architecture (layers, ports, CLI boundary, data model, persistence plan).
- Decisions: Supabase Postgres with a local test database; pytest.
- Carried into Sprint 2: the source census (done) and the first pay-normalization test (done). The dataset check is still open.
