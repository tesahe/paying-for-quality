-- Migration 002 (Postgres): the source-agnostic rate model (FR-9, Sprint 3).
-- Every pay figure, from any source, is stored here after Core validation (core/rates.py).
-- There is deliberately no company column: job-board rates are published as aggregates only.
-- Vocabulary CHECKs must match core/vocab.py (tests/adapters/test_schema_parity.py).

CREATE TABLE IF NOT EXISTS rate_source (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    provenance_kind TEXT NOT NULL CHECK (provenance_kind IN ('job_board', 'gov_statistic', 'literature', 'dataset_paper', 'self_timed')),
    terms_checked BOOLEAN NOT NULL,
    checked_at TEXT,
    terms_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rate_observation (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rate_source_id BIGINT NOT NULL REFERENCES rate_source (id),
    external_key TEXT NOT NULL,
    amount_min NUMERIC(14, 2) NOT NULL,
    amount_max NUMERIC(14, 2) NOT NULL,
    currency TEXT NOT NULL,
    unit TEXT NOT NULL,
    hourly_min_usd NUMERIC(10, 2) NOT NULL,
    hourly_max_usd NUMERIC(10, 2) NOT NULL,
    engagement TEXT NOT NULL CHECK (engagement IN ('employee', 'contractor', 'intern', 'temporary', 'unknown')),
    rater_kind TEXT NOT NULL CHECK (rater_kind IN ('expert', 'crowd', 'staff', 'outside_option')),
    domain TEXT NOT NULL CHECK (domain IN ('coding', 'math', 'stem_science', 'medicine', 'law', 'finance', 'writing_humanities', 'languages',
                                       'reasoning_general', 'none')),
    provenance_kind TEXT NOT NULL CHECK (provenance_kind IN ('job_board', 'gov_statistic', 'literature', 'dataset_paper', 'self_timed')),
    occupation TEXT,
    region TEXT,
    as_of TEXT,
    citation_url TEXT,
    citation_note TEXT NOT NULL DEFAULT '',
    raw_posting_id BIGINT REFERENCES raw_posting (id),
    loaded_at TIMESTAMPTZ NOT NULL,
    UNIQUE (rate_source_id, external_key)
);

CREATE INDEX IF NOT EXISTS rate_observation_domain ON rate_observation (domain, rater_kind);

ALTER TABLE rate_source ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_observation ENABLE ROW LEVEL SECURITY;
