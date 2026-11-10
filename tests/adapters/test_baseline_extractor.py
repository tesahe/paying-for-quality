"""Baseline (no-LLM) extractor. Its output must still pass Core validation to count."""

from decimal import Decimal

import pytest

from paying_for_quality.adapters.llm.baseline import BaselineExtractor, guess_seniority, text_quotes
from paying_for_quality.adapters.sources.ashby import job_to_doc
from paying_for_quality.core.entities import Outcome
from paying_for_quality.core.validation import validate_extraction
from tests.adapters.test_ashby import RESPONSE
from tests.fakes import doc


def test_structured_ashby_compensation_is_accepted_by_core():
    ashby_doc = job_to_doc(RESPONSE["jobs"][0], "Acme")
    candidate = BaselineExtractor().extract(ashby_doc)
    assert candidate.domain == "operations"
    assert candidate.seniority == "lead"
    assert len(candidate.pay_quotes) == 1  # equity is not a pay quote
    result = validate_extraction(candidate, ashby_doc.text)
    assert result.outcome is Outcome.ACCEPTED
    quote = result.posting.pay_quotes[0]
    assert (quote.hourly_min_usd, quote.hourly_max_usd) == (Decimal("72.12"), Decimal("96.15"))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("We pay $90 – $120 per hour, weekly.", ("90", "120", "hour")),
        ("Compensation: $150k/yr plus equity", ("150k", "150k", "yr")),
        ("Rate: $45.50 an hour", ("45.50", "45.50", "hour")),
        ("Salary $120,000 to $140,000 per year", ("120,000", "140,000", "year")),
    ],
)
def test_text_pay_patterns(text, expected):
    (quote,) = text_quotes(text)
    assert (quote.amount_min, quote.amount_max, quote.unit) == expected
    assert quote.evidence in text


def test_no_pay_phrase_gives_no_quote():
    assert text_quotes("Competitive pay. 5 years experience. $ signs alone mean nothing.") == []


def test_text_fallback_end_to_end():
    posting = doc("x", text="Physician reviewer. Pay: $90 - $120 per hour.", title="Senior Physician Reviewer")
    result = validate_extraction(BaselineExtractor().extract(posting), posting.text)
    assert result.outcome is Outcome.ACCEPTED
    assert result.posting.seniority == "senior"
    assert result.posting.pay_quotes[0].hourly_max_usd == Decimal("120.00")


@pytest.mark.parametrize(
    "title, expected",
    [("Software Engineer Intern", "intern"), ("Head of Ops", "head"), ("Leadership Coach", None), ("Analyst", None)],
)
def test_guess_seniority(title, expected):
    assert guess_seniority(title) == expected
