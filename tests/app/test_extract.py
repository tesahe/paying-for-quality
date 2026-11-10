"""FR-2 integrated: Core validation decides what reaches the posting table; every attempt is audited."""

import json

from paying_for_quality.adapters.llm.fake import FakeExtractor
from paying_for_quality.app.market import collect, extract
from paying_for_quality.core.entities import ExtractionCandidate, PayQuoteCandidate
from tests.fakes import FakeSource, doc, source_info

RAW_TEXT = "Pay: $100,000 per year"


def candidate(amount, confidence=None, evidence="$100,000 per year"):
    return ExtractionCandidate(
        company="Acme", title="Data Lead", domain="operations", confidence=confidence,
        pay_quotes=(PayQuoteCandidate(amount, None, "year", evidence),),
    )


def setup(repo, raw_store, clock):
    collect(source_info(), FakeSource([doc("good"), doc("invented"), doc("unsure"), doc("broken")]),
            repo, raw_store, clock)
    return FakeExtractor({
        "good": candidate(100000),
        "invented": candidate(150000, evidence="$150,000 per year"),
        "unsure": candidate(100000, confidence=0.3),
        "broken": RuntimeError("provider timeout"),
    })


def test_outcomes_land_in_the_right_tables(repo, raw_store, clock):
    result = extract(setup(repo, raw_store, clock), repo, raw_store, clock)
    assert (result.accepted, result.rejected, result.review, result.failed) == (1, 1, 1, 1)
    assert result.issue_counts == {"EVIDENCE_NOT_FOUND": 1, "LOW_CONFIDENCE": 1}
    assert repo.count_rows("posting") == 1
    assert repo.count_rows("pay_quote") == 1
    assert repo.count_rows("review_item") == 1
    assert repo.count_rows("extraction_run") == 3  # the failed call is not recorded


def test_every_extraction_keeps_the_raw_candidate(repo, raw_store, clock):  # AC-2.4
    extract(setup(repo, raw_store, clock), repo, raw_store, clock)
    rows = repo.query(
        "SELECT rp.external_id, e.extractor, e.prompt_version, e.outcome, e.candidate_json"
        " FROM extraction_run e JOIN raw_posting rp ON rp.id = e.raw_posting_id ORDER BY rp.external_id"
    ).rows
    by_id = {r[0]: r for r in rows}
    assert by_id["invented"][3] == "rejected"
    stored = by_id["invented"][4]
    stored = stored if isinstance(stored, dict) else json.loads(stored)
    assert stored["pay_quotes"][0]["amount_min"] == 150000  # the untrusted value, kept verbatim for audit
    assert {r[1] for r in rows} == {"fake"} and {r[2] for r in rows} == {"none"}


def test_failed_postings_are_retried_and_done_ones_are_not(repo, raw_store, clock):
    extractor = setup(repo, raw_store, clock)
    extract(extractor, repo, raw_store, clock)
    extractor.scripted["broken"] = candidate(100000)
    again = extract(extractor, repo, raw_store, clock)
    assert (again.total, again.accepted) == (1, 1)


def test_limit(repo, raw_store, clock):
    result = extract(setup(repo, raw_store, clock), repo, raw_store, clock, limit=2)
    assert result.total == 2
