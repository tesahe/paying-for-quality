# Sprint Status

## Sprint 1: Define and Establish

**Branch:** `sprint-1` · **Status:** in progress

### Done

- Repository created with the course baseline files: `README.md`, `AGENTS.md`, `.gitignore`, `.gitattributes`, `.env.example`.
- First draft of [`docs/requirements.md`](requirements.md): primary user, 8 functional requirements with target sprints, 8 design constraints, CLI expectations, Given/When/Then acceptance criteria, and an Exploration Zone.
- First draft of [`docs/architecture.md`](architecture.md): Core / use cases / adapters / CLI layers, ports, CLI boundary, data model (market and quality tables) and persistence plan.
- Verification intent for four behaviors: pay normalization, extraction validation, idempotent collection, agreement metrics (in `docs/requirements.md`).

### Decisions

| Decision | Choice | Reason |
|---|---|---|
| Database | Supabase (hosted Postgres) is the system of record. Tests and offline runs use a local database behind the same `Repository` port | Real Postgres for collected data and SQL analysis; tests still run with no credentials or network |
| Test runner | pytest | Fixtures and markers; opt-in Supabase tests stay out of the default run |
| LLM provider | TBD (a low-cost "flash"-class model is the leading option); spending cap kept low | Fake adapters are the default until chosen |

### Verification

No code yet, so there is no test result to report. The first test (pay normalization, AC-3.1–3.5) is the next code step.

### Next

- Source census: which public posting sources exist, how many postings each has, and what their robots.txt and terms allow.
- Dataset check: SummEval and the other candidates — fields, rater types, licenses.
- Core entities and ports; pay normalization with its first pytest test.
- Ask the professor how this project's sprints map to the course calendar.

### Known Limitations

- Nothing is implemented yet.
- LLM provider, spending cap, extraction thresholds and the domain vocabulary are still TBD (see `docs/architecture.md`, Open Decisions).

### Peer Feedback

Not applicable yet.
