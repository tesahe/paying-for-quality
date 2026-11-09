-- Postgres schema (Supabase). Applied inside the configured schema (default "pfq") via search_path,
-- so table names are unqualified. Must declare the same tables and columns as sqlite.sql.
-- RLS is enabled on every table: tables created outside the Supabase dashboard do not get it by
-- default. The owning role (used by this tool) bypasses RLS; Data API roles get no access.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    board TEXT NOT NULL,
    company TEXT NOT NULL,
    segment TEXT NOT NULL CHECK (segment IN ('staff', 'expert')),
    terms_checked BOOLEAN NOT NULL,
    robots_checked_at TEXT,
    terms_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS collection_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES source (id),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'ok', 'error')),
    n_new INTEGER NOT NULL DEFAULT 0,
    n_changed INTEGER NOT NULL DEFAULT 0,
    n_unchanged INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS raw_posting (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES source (id),
    external_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    url TEXT,
    title TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    UNIQUE (source_id, external_id, content_hash)
);

CREATE TABLE IF NOT EXISTS extraction_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raw_posting_id BIGINT NOT NULL REFERENCES raw_posting (id),
    extractor TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    candidate_json JSONB NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('accepted', 'rejected', 'review')),
    issues_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS posting (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    raw_posting_id BIGINT NOT NULL REFERENCES raw_posting (id),
    extraction_run_id BIGINT NOT NULL UNIQUE REFERENCES extraction_run (id),
    company TEXT NOT NULL,
    platform TEXT,
    title TEXT NOT NULL,
    domain TEXT,
    seniority TEXT,
    credentials_json JSONB NOT NULL,
    posted_at TEXT
);

CREATE TABLE IF NOT EXISTS pay_quote (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    posting_id BIGINT NOT NULL REFERENCES posting (id),
    amount_min NUMERIC(14, 2) NOT NULL,
    amount_max NUMERIC(14, 2) NOT NULL,
    currency TEXT NOT NULL,
    unit TEXT NOT NULL,
    hourly_min_usd NUMERIC(10, 2),
    hourly_max_usd NUMERIC(10, 2),
    evidence TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_item (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    extraction_run_id BIGINT NOT NULL UNIQUE REFERENCES extraction_run (id),
    status TEXT NOT NULL CHECK (status IN ('open', 'accepted', 'rejected')),
    decided_at TIMESTAMPTZ,
    note TEXT
);

CREATE INDEX IF NOT EXISTS raw_posting_listing ON raw_posting (source_id, external_id);
CREATE INDEX IF NOT EXISTS extraction_run_raw ON extraction_run (raw_posting_id);
CREATE INDEX IF NOT EXISTS pay_quote_posting ON pay_quote (posting_id);

ALTER TABLE schema_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE source ENABLE ROW LEVEL SECURITY;
ALTER TABLE collection_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_posting ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE posting ENABLE ROW LEVEL SECURITY;
ALTER TABLE pay_quote ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_item ENABLE ROW LEVEL SECURITY;

INSERT INTO schema_version (version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
