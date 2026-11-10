"""FR-4: named SQL analyses. Run on SQLite by default and on Supabase with `pytest -m supabase`,
which proves the SQL is portable."""

from decimal import Decimal

import pytest

from paying_for_quality.adapters.llm.fake import FakeExtractor
from paying_for_quality.app.market import collect, extract
from paying_for_quality.app.reporting import available_queries, run_query
from paying_for_quality.core.entities import ExtractionCandidate, PayQuoteCandidate
from paying_for_quality.core.errors import PfqError
from tests.fakes import FakeSource, doc, source_info


def hourly(low, high, domain="medicine", confidence=None):
    evidence = f"${low} - ${high} per hour"
    return evidence, ExtractionCandidate(
        company="Acme", title="Reviewer", domain=domain, confidence=confidence,
        pay_quotes=(PayQuoteCandidate(low, high, "hour", evidence),),
    )


def load(repo, raw_store, clock, scripted):
    """scripted: external_id -> (evidence text, candidate)."""
    docs = [doc(eid, text=f"Pay: {text}") for eid, (text, _) in scripted.items()]
    collect(source_info(), FakeSource(docs), repo, raw_store, clock)
    extract(FakeExtractor({eid: c for eid, (_, c) in scripted.items()}), repo, raw_store, clock)


def rows_by_domain(result):
    return {row[1]: (row[2], Decimal(str(row[3]))) for row in result.rows}


def test_median_of_three(repo, raw_store, clock):  # AC-4.1
    load(repo, raw_store, clock, {"a": hourly(30, 50), "b": hourly(50, 70), "c": hourly(70, 90)})  # mids 40/60/80
    result = run_query(repo, "pay_by_domain")
    assert result.columns == ("segment", "domain", "n", "median_hourly_usd")
    assert rows_by_domain(result) == {"medicine": (3, Decimal("60"))}


def test_median_of_four_averages_the_middle_two(repo, raw_store, clock):
    load(repo, raw_store, clock, {
        "a": hourly(40, 40, "law"), "b": hourly(50, 50, "law"), "c": hourly(70, 70, "law"), "d": hourly(90, 90, "law"),
    })
    assert rows_by_domain(run_query(repo, "pay_by_domain")) == {"law": (4, Decimal("60"))}


def test_rejected_and_review_postings_are_excluded(repo, raw_store, clock):  # AC-4.2
    _, invented = hourly(500, 500)
    load(repo, raw_store, clock, {
        "ok": hourly(40, 40),
        "unsure": hourly(300, 300, confidence=0.2),
        "invented": ("$40 - $40 per hour", invented),  # claims $500 but the posting says $40
    })
    assert rows_by_domain(run_query(repo, "pay_by_domain")) == {"medicine": (1, Decimal("40"))}


def test_only_the_latest_version_of_a_listing_counts(repo, raw_store, clock):
    load(repo, raw_store, clock, {"a": hourly(40, 40)})
    load(repo, raw_store, clock, {"a": hourly(60, 60)})  # same listing, new text and pay
    assert rows_by_domain(run_query(repo, "pay_by_domain")) == {"medicine": (1, Decimal("60"))}


def test_pay_transparency(repo, raw_store, clock):
    no_pay = ("no pay stated", ExtractionCandidate(company="Acme", title="Engineer"))
    load(repo, raw_store, clock, {"a": hourly(40, 40), "b": no_pay, "c": no_pay, "d": hourly(50, 50)})
    ((source, segment, postings, with_pay, pct),) = run_query(repo, "pay_transparency").rows
    assert (source, segment, postings, with_pay) == ("fake-board", "staff", 4, 2)
    assert Decimal(str(pct)) == Decimal("50.0")


def test_unknown_query_lists_the_available_ones(repo):
    with pytest.raises(PfqError, match="pay_by_domain"):
        run_query(repo, "drop_everything")
    assert available_queries() == ["pay_by_domain", "pay_transparency"]
