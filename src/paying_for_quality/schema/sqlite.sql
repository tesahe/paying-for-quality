-- SQLite schema (local runs and tests). Must declare the same tables and columns as postgres.sql;
-- tests/adapters/test_schema_parity.py enforces this. Market tables only (quality tables: Sprint 4).

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    board TEXT NOT NULL,
    company TEXT NOT NULL,
    segment TEXT NOT NULL CHECK (segment IN ('staff', 'expert')),
    terms_checked INTEGER NOT NULL,
    robots_checked_at TEXT,
    terms_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS collection_run (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES source (id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'ok', 'error')),
    n_new INTEGER NOT NULL DEFAULT 0,
    n_changed INTEGER NOT NULL DEFAULT 0,
    n_unchanged INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS raw_posting (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES source (id),
    external_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    url TEXT,
    title TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (source_id, external_id, content_hash)
);

CREATE TABLE IF NOT EXISTS extraction_run (
    id INTEGER PRIMARY KEY,
    raw_posting_id INTEGER NOT NULL REFERENCES raw_posting (id),
    extractor TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    candidate_json TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('accepted', 'rejected', 'review')),
    issues_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posting (
    id INTEGER PRIMARY KEY,
    raw_posting_id INTEGER NOT NULL REFERENCES raw_posting (id),
    extraction_run_id INTEGER NOT NULL UNIQUE REFERENCES extraction_run (id),
    company TEXT NOT NULL,
    platform TEXT,
    title TEXT NOT NULL,
    domain TEXT,
    seniority TEXT,
    credentials_json TEXT NOT NULL,
    posted_at TEXT
);

CREATE TABLE IF NOT EXISTS pay_quote (
    id INTEGER PRIMARY KEY,
    posting_id INTEGER NOT NULL REFERENCES posting (id),
    amount_min REAL NOT NULL,
    amount_max REAL NOT NULL,
    currency TEXT NOT NULL,
    unit TEXT NOT NULL,
    hourly_min_usd REAL,
    hourly_max_usd REAL,
    evidence TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_item (
    id INTEGER PRIMARY KEY,
    extraction_run_id INTEGER NOT NULL UNIQUE REFERENCES extraction_run (id),
    status TEXT NOT NULL CHECK (status IN ('open', 'accepted', 'rejected')),
    decided_at TEXT,
    note TEXT
);

CREATE INDEX IF NOT EXISTS raw_posting_listing ON raw_posting (source_id, external_id);
CREATE INDEX IF NOT EXISTS extraction_run_raw ON extraction_run (raw_posting_id);
CREATE INDEX IF NOT EXISTS pay_quote_posting ON pay_quote (posting_id);

INSERT INTO schema_version (version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
