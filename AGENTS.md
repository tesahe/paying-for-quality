# Agent & Development Instructions (CIT 381)

This repository is for an academic software engineering project for **CIT 381**.
This file serves as the canonical AI and developer instruction guide for the project. It is a living document and will be improved as the project develops.

---

## 1. Core Operating Principles

1. **Academic Context:** This is a CIT 381 course project. All work must align with course specifications, grading rubrics, and clean software architecture standards.
2. **Agent Workflow (subagents allowed):**
   - Subagents may be used for research, review and independent work (e.g. fresh-context "goldfish" reviews, parallel checks of separate docs).
   - The main session owns the result: it reviews subagent output before acting on it, and subagents follow every rule in this file.
   - Subagents do not commit, merge, push, or edit canonical docs directly; they report, and the main session applies agreed changes.
   - Keep work focused on the current task deliverables.
3. **Secrets & Security:**
   - **Never** expose, print, log, commit, or request secrets, API keys, tokens, or private credentials.
   - Strictly keep secrets in `.env` and verify they are omitted from git tracking.
   - Use `.env.example` as a template for public configuration keys.
4. **Repository Boundaries & `.gitignore` Compliance:**
   - Respect `.gitignore` rules and repository boundaries at all times.
   - Do not stage or track generated build artifacts, temporary caches, virtual environments, or platform-specific metadata files (`.DS_Store`).
5. **Bounded Changes:**
   - Prefer small, bounded, and modular changes over broad, sweeping, or unrelated rewrites.
   - Modify only files relevant to the active user prompt or sprint objective.
6. **Preserve Existing Behavior:**
   - Maintain existing working code, tests, and interfaces unless the requested task explicitly requires changing or refactoring them.
   - Preserve comments, architectural boundaries, and configuration setups.
7. **Verification & Testing:**
   - Always run or recommend relevant verification (unit tests, linting, syntax checks, or schema validation) following code modifications.
   - Ensure the Engineering Core remains fully verifiable through automated unit tests without requiring a running database or server.
8. **Truthfulness & Handling Uncertainty:**
   - Clearly identify uncertainty and ask for clarification rather than inventing project facts, requirements, or fictitious domain assumptions.
   - Flag any missing domain specifications as "To Be Determined (TBD)".

---

## 2. Architectural Boundaries (Engineering Core)

- **Pure Domain Isolation:** All business logic, validation, pay normalization, and quality/agreement math belong inside the `core` layer.
- **Zero Framework Dependency in Core:** The Core layer must not import database drivers, ORMs, HTTP frameworks (e.g., Express, Flask, FastAPI), LLM SDKs, or external web APIs.
- **Inward Dependency Rule:** External layers (CLI, web UI, database adapters, collectors, LLM clients) depend on the Core abstractions and interfaces (Ports), never the reverse.
- **LLM Output Is Untrusted:** Anything produced by a language model (extracted fields, judge scores, summaries) is a *candidate* until a Core validation function accepts it. An LLM never produces a number that is shown to the user without Core validation.

---

## 3. Project Context

- **Project:** Paying for Quality — an analysis tool for the AI human-data industry (companies such as Mercor, Scale, Surge, Invisible that hire experts to produce AI training and evaluation data).
- **Guiding question:** Is the pay premium for expertise (market side) justified by the quality difference experts produce (quality side), and do LLM judges change that trade-off?
- **Framing (Sprint 3): "Cost of Quality".** For a labeling job, which mix of experts, crowd raters and LLM judges reaches the quality needed at the lowest cost, and when is the expert premium worth paying?
- **Price side:** pay rates from any source (public job-board APIs, official wage statistics, cited published figures) → Core validation and hourly normalization → one `rate_observation` table → aggregate analysis.
- **Quality side:** load public multi-rater datasets → agreement and rater-quality metrics → LLM-judge comparison.
- **Out of class scope:** the paid human-subject experiment, ethics (IRB) approval, and the research paper. The software should keep that experiment a configuration change, not a rebuild.
- Scope details live in `README.md` and `docs/requirements.md`. Unsettled decisions are marked **TBD** there.

---

## 4. Data and Ethics Guardrails (hard rules)

1. **Public data only.** Collect only publicly posted job listings and publicly released datasets.
2. **Respect each source.** Check robots.txt and terms of service before adding a source; record the result. Collect gently (rate-limit, identify the client generically, no login-walled pages).
3. **Raw data stays out of git.** Raw pages and downloaded datasets live under `data/raw/` (git-ignored). Only schemas, small hand-made label files, and code are committed.
4. **No contract-work content, ever.** Nothing from the owner's paid AI-training work (tasks, guidelines, rates, screenshots) may enter this repository. That work is under NDA.
5. **Rater data is separable.** Any human rating data that is not from a public dataset is stored separately and is synthetic or self-generated unless the instructor approves otherwise.
6. **Respect dataset licenses.** Record the license of every dataset used.
7. **Job listings only from public job-board APIs.** Postings come only from the ATS feeds employers use to distribute jobs (e.g. Ashby, Greenhouse). Never collect from, or copy by hand from, a company's own website or work platform (e.g. work.mercor.com, alignerr.com), whatever its robots.txt says.
8. **Aggregates only.** Public outputs built on job-board data show industry aggregates. No rankings or comparisons of named companies' pay. `rate_observation` deliberately has no company column.
9. **Every hand-entered figure is cited.** Each entry in `data/rates.toml` names a public source (URL), the retrieval date and its license or terms. Figures the owner knows from contract work are never entered, even when a public source states the same number.

---

## 5. Repository Workflow

- **Branches:** one branch per sprint (`sprint-1`, `sprint-2`, …). Each sprint branch is merged into `main` and **kept** after merging.
- **Do not merge or push** unless the owner explicitly says to in that request.
- **Commit prefixes:** `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`, `merge:`. 
- **Canonical documents only:** `README.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/sprint-status.md`, `docs/ai-usage.md`. Do not create other progress or reflection documents (no `manual-verification.md`, no `ai-implementation-review.md`). Working files (drift reports, EGM briefs, drafts and review reports) live in `planning/`, which is git-ignored; see §6.
- **Course instructions** are kept locally in `class-instructions/` (git-ignored) and are the source of truth for sprint requirements.

---

## 6. Documentation Alignment (adapted from the Elephant-Goldfish Model)

The docs must describe the code as it is. This section borrows EGM's drift detection and fresh-eyes review and makes them a routine part of every sprint.

### Two kinds of documents

| Kind | Files | Expected change |
|---|---|---|
| **Foundational** | `docs/architecture.md` (layers, ports, data model, boundary), `docs/requirements.md` (FRs, constraints, acceptance criteria) | Rarely. A change needs a stated reason, recorded under "What Changed This Sprint" |
| **Sprint** | `README.md` Current Sprint Status, `docs/sprint-status.md`, `docs/ai-usage.md`, requirement status columns | Every sprint |

Docs name concrete file paths, modules, commands, tables and issue codes, so drift is checkable. When a doc describes something without a path, add the path.

### Drift check (run without being asked)

**When:** before any sprint merge to `main`; after a series of commits touching `core/`, `app/`, `adapters/`, `schema/`, `queries/` or `cli.py`; and whenever docs are being updated.

**How:**
1. **List the claims.** For each canonical doc, list its concrete claims: paths, modules, functions, tables and columns, CLI commands and flags, issue codes, constants and thresholds, dependencies, test command and counts, sprint status.
2. **Verify against the current source.** Read the files and run the documented test command; never rely on memory. Use the observed result.
3. **Report only the differences,** in these categories:
   - **Missing:** the doc describes it; the code lacks it.
   - **Undocumented:** the code has it; no doc mentions it.
   - **Model mismatch:** tables, columns, dataclass fields or enums differ.
   - **Shortcut:** a hard-coded value where the doc says configurable or TBD.
   - **Architectural divergence:** a different pattern, library or file location than documented.
   - **Stale status:** wrong counts, test results or sprint state.
4. **Write the report** to `planning/drift/YYYY-MM-DD_DRIFT_REPORT.md` (git-ignored), one `## <doc>` heading per doc with bullets, or "No drift detected".
5. **Resolve each item:**
   - Sprint docs: fix directly.
   - Foundational docs or code: propose the change and ask the owner which side is wrong. Never quietly change code to match a doc, or a foundational doc to match code.
6. **Goldfish pass** (at sprint end): a fresh subagent with no conversation context reads only the docs and the code, repeats steps 1–3, and also flags anything a new reader could not understand without the chat history. Merge its findings into the report.

The owner can also run `/egm:egm-drift-report` directly. Point its output at `planning/drift/`.

### Planning and solidifying docs with EGM (owner-invoked)

- **`/egm:egm-brainstorm`**: test a feature or a doc direction against what is already built; brief goes to `planning/`.
- **`/egm:egm-draft`**: draft the design; draft goes to `planning/`.
- **`/egm:egm-review`** and **`/egm:egm-review-loop`**: fresh-reviewer critique of a draft or a canonical doc.
- **`/egm:egm-resolve`**: decide each finding.
- **Rules:**
  - All EGM output is written to `planning/`, never to the repo root or `docs/designs/`. Agreed content is then folded into the canonical docs.
  - Accepted or rejected review findings are good evidence for the sprint's entry in `docs/ai-usage.md`.
  - **Never run `/egm:egm-bootstrap`**: per-folder READMEs break the canonical-documents rule.
