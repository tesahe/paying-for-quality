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


# --- rates (FR-9) ----------------------------------------------------------------------------
from paying_for_quality.core.entities import RateCandidate, RateSourceInfo  # noqa: E402
from paying_for_quality.core.rates import validate_rate  # noqa: E402

RATE_SOURCE = RateSourceInfo("cited-rates", "cited", "literature", True, "2026-11-09", "test")


def observation(key="mtbench-expert", hourly=35):
    candidate = RateCandidate(
        external_key=key, amount_min=hourly, amount_max=hourly, unit="hour", engagement="contractor",
        rater_kind="expert", domain="reasoning_general", provenance_kind="dataset_paper",
        citation_url="https://arxiv.org/abs/2306.05685", citation_note="around $35 per hour",
    )
    return validate_rate(candidate).observation


def test_upsert_rate_source_keeps_one_row(repo):
    first = repo.upsert_rate_source(RATE_SOURCE)
    second = repo.upsert_rate_source(RateSourceInfo("cited-rates", "cited", "literature", False))
    assert first == second
    assert repo.count_rows("rate_source") == 1


def test_insert_rate_is_idempotent_on_external_key(repo):
    source_id = repo.upsert_rate_source(RATE_SOURCE)
    assert repo.insert_rate(source_id, observation(), T0) is True
    assert repo.insert_rate(source_id, observation(hourly=99), T0) is False  # same key: never overwritten
    assert repo.insert_rate(source_id, observation(key="other"), T0) is True
    rows = repo.query("SELECT external_key, hourly_min_usd FROM rate_observation ORDER BY external_key").rows
    assert [(key, Decimal(str(value))) for key, value in rows] == [("mtbench-expert", Decimal(35)), ("other", Decimal(35))]


def test_current_posted_pay_lists_only_current_accepted_hourly_quotes(repo):
    source_id, raw_id = add_raw(repo)
    repo.record_extraction(raw_id, "fake", "v0", T0, "{}", ValidationResult(Outcome.ACCEPTED, POSTING))
    pay = repo.current_posted_pay()
    assert [(p.raw_posting_id, p.quote_index, p.unit, p.title) for p in pay] == [(raw_id, 0, "year", "Data Lead")]

    # A newer snapshot of the same listing with no accepted extraction hides the old one.
    repo.insert_raw_posting(source_id, DOC, "hash-2", "test-board/hash-2.json", T0)
    assert repo.current_posted_pay() == []
