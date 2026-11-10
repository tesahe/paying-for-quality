"""Ashby adapter, against a small hand-made response in the API's documented shape (no real data)."""

import pytest

from paying_for_quality.adapters.sources.ashby import URL, AshbySource
from paying_for_quality.core.errors import SourceFetchError

RESPONSE = {
    "apiVersion": "1",
    "jobs": [
        {
            "id": "11111111-aaaa", "title": " Strategic Projects Lead ", "isListed": True,
            "department": "Operations", "employmentType": "FullTime", "jobUrl": "https://jobs.example/1",
            "publishedAt": "2026-11-01T10:00:00.000+00:00",
            "descriptionPlain": "Run expert data programs end to end.",
            "compensation": {
                "compensationTierSummary": "$150K – $200K • Offers Equity",
                "summaryComponents": [
                    {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD",
                     "minValue": 150000, "maxValue": 200000},
                    {"compensationType": "EquityPercentage", "interval": "NONE", "currencyCode": None,
                     "minValue": None, "maxValue": None},
                ],
            },
        },
        {"id": "22222222-bbbb", "title": "Hidden role", "isListed": False, "descriptionPlain": "x"},
        {"id": "33333333-cccc", "title": "No pay role", "isListed": True, "descriptionPlain": "Great team."},
    ],
}


def make_source(response=RESPONSE):
    calls = []

    def fetch(url):
        calls.append(url)
        return response

    return AshbySource("acme", "Acme", fetch=fetch), calls


def test_one_request_with_compensation():
    source, calls = make_source()
    list(source.list_postings())
    assert calls == [URL.format(board="acme")]
    assert "includeCompensation=true" in calls[0]


def test_unlisted_postings_are_skipped():
    source, _ = make_source()
    assert [d.external_id for d in source.list_postings()] == ["11111111-aaaa", "33333333-cccc"]


def test_doc_text_includes_the_compensation_summary():
    source, _ = make_source()
    first = next(iter(source.list_postings()))
    assert first.title == "Strategic Projects Lead"
    assert first.company == "Acme"
    assert first.text.endswith("Compensation: $150K – $200K • Offers Equity")
    assert first.metadata["department"] == "Operations"
    assert first.posted_at.startswith("2026-11-01")


def test_unexpected_response_is_a_fetch_error():
    source, _ = make_source({"error": "nope"})
    with pytest.raises(SourceFetchError):
        list(source.list_postings())
