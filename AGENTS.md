# Agent & Development Instructions (CIT 381)

This repository is for an academic software engineering project for **CIT 381**.
This file serves as the canonical AI and developer instruction guide for the project. It is a living document and will be improved as the project develops.

---

## 1. Core Operating Principles

1. **Academic Context:** This is a CIT 381 course project. All work must align with course specifications, grading rubrics, and clean software architecture standards.
2. **Single-Agent Development Workflow:**
   - Operate strictly within a single-agent development workflow.
   - Do not trigger parallel or multi-agent background processes unless specifically directed.
   - Keep interactions structured, linear, and focused on current task deliverables.
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
- **Market side:** collect public job postings → LLM extraction → Core validation and pay normalization → SQLite → pay analysis.
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

---

## 5. Repository Workflow

- **Branches:** one branch per sprint (`sprint-1`, `sprint-2`, …). Each sprint branch is merged into `main` and **kept** after merging.
- **Do not merge or push** unless the owner explicitly says to in that request.
- **Commit prefixes:** `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`, `merge:`. 
- **Canonical documents only:** `README.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/sprint-status.md`, `docs/ai-usage.md`. Do not create other progress or reflection documents (no `manual-verification.md`, no `ai-implementation-review.md`).
- **Course instructions** are kept locally in `class-instructions/` (git-ignored) and are the source of truth for sprint requirements.
