"""Repository contract: the same behavior from SQLite and (opt-in) Supabase Postgres."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from paying_for_quality.core.entities import (
    Outcome, PayQuote, PayUnit, Posting, RawPostingDoc, SourceInfo, ValidationResult,
)
from paying_for_quality.core.errors import Issue, IssueCode

T0 = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
SOURCE = SourceInfo("test-board", "ashby", "board", "Acme", "staff", True, "2026-11-09", "note")
DOC = RawPostingDoc("job-1", "https://example.test/1", "Data Lead", "Acme", "Pay: $100,000 per year")

POSTING = Posting(
    company="Acme", title="Data Lead", platform="Acme", domain="operations", seniority=None,
    credentials=("MBA",), posted_at="2026-11-01",
    pay_quotes=(
        PayQuote(Decimal(100000), Decimal(100000), "USD", PayUnit.YEAR, Decimal("48.08"), Decimal("48.08"),
                 "$100,000 per year"),
    ),
)


def add_raw(repo):
    source_id = repo.upsert_source(SOURCE)
    return source_id, repo.insert_raw_posting(source_id, DOC, "hash-1", "test-board/hash-1.json", T0)


def test_apply_schema_is_idempotent(repo):
    repo.apply_schema()
    assert repo.count_rows("schema_version") == 1


def test_upsert_source_keeps_one_row_and_updates(repo):
    first = repo.upsert_source(SOURCE)
    second = repo.upsert_source(SourceInfo("test-board", "ashby", "board", "Acme Inc", "staff", False))
    assert first == second
    assert repo.count_rows("source") == 1
    assert repo.query("SELECT company FROM source").rows == (("Acme Inc",),)


def test_raw_posting_lookup_and_uniqueness(repo):
    source_id, raw_id = add_raw(repo)
    assert repo.find_raw_posting(source_id, "job-1", "hash-1") == raw_id
    assert repo.find_raw_posting(source_id, "job-1", "other-hash") is None
    assert repo.has_listing(source_id, "job-1")
    assert not repo.has_listing(source_id, "job-2")
    with pytest.raises(Exception):
        repo.insert_raw_posting(source_id, DOC, "hash-1", "x", T0)  # UNIQUE (source, external_id, hash)


def test_collection_run_round_trip(repo):
    source_id = repo.upsert_source(SOURCE)
    run_id = repo.start_collection_run(source_id, T0)
    repo.finish_collection_run(run_id, T0, "ok", 3, 1, 2)
    assert repo.query("SELECT status, n_new, n_changed, n_unchanged FROM collection_run").rows == (("ok", 3, 1, 2),)


def test_accepted_extraction_writes_posting_and_pay(repo):
    _, raw_id = add_raw(repo)
    assert [p.raw_posting_id for p in repo.pending_extraction()] == [raw_id]
    repo.record_extraction(raw_id, "fake", "v0", T0, '{"x": 1}', ValidationResult(Outcome.ACCEPTED, POSTING))
    assert repo.pending_extraction() == []
    assert repo.count_rows("posting") == 1
    (row,) = repo.query("SELECT unit, hourly_min_usd, evidence FROM pay_quote").rows
    assert row[0] == "year" and Decimal(str(row[1])) == Decimal("48.08") and row[2] == "$100,000 per year"


def test_review_extraction_writes_review_item_not_posting(repo):
    _, raw_id = add_raw(repo)
    result = ValidationResult(Outcome.REVIEW, POSTING, (Issue(IssueCode.LOW_CONFIDENCE, "confidence"),))
    repo.record_extraction(raw_id, "fake", "v0", T0, "{}", result)
    assert repo.count_rows("posting") == 0
    assert repo.query("SELECT status FROM review_item").rows == (("open",),)


def test_rejected_extraction_is_audited_only(repo):
    _, raw_id = add_raw(repo)
    result = ValidationResult(Outcome.REJECTED, None, (Issue(IssueCode.EVIDENCE_NOT_FOUND, "pay"),))
    repo.record_extraction(raw_id, "fake", "v0", T0, "{}", result)
    assert repo.count_rows("posting") == 0 and repo.count_rows("review_item") == 0
    assert repo.query("SELECT outcome FROM extraction_run").rows == (("rejected",),)


def test_pending_extraction_only_latest_version_and_limit(repo):
    source_id, old_id = add_raw(repo)
    new_id = repo.insert_raw_posting(source_id, DOC, "hash-2", "p2", T0)
    other = RawPostingDoc("job-2", "u", "Other", "Acme", "text")
    other_id = repo.insert_raw_posting(source_id, other, "hash-3", "p3", T0)
    assert [p.raw_posting_id for p in repo.pending_extraction()] == [new_id, other_id]
    assert len(repo.pending_extraction(limit=1)) == 1
    assert old_id not in [p.raw_posting_id for p in repo.pending_extraction()]


def test_count_rows_rejects_unknown_tables(repo):
    with pytest.raises(ValueError):
        repo.count_rows("source; DROP TABLE source")
