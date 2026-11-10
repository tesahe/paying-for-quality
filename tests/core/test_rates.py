"""Rate validation: one Core path for every pay source (FR-9)."""

from dataclasses import replace
from decimal import Decimal

import pytest

from paying_for_quality.core.entities import RateCandidate
from paying_for_quality.core.errors import IssueCode
from paying_for_quality.core.rates import validate_rate
from paying_for_quality.core.vocab import domain_from_title


def cited(**overrides):
    base = RateCandidate(
        external_key="bls-29-1229",
        amount_min=104000,
        amount_max=104000,
        unit="year",
        engagement="employee",
        rater_kind="outside_option",
        domain="medicine",
        provenance_kind="gov_statistic",
        occupation="29-1229",
        citation_url="https://www.bls.gov/oes/",
        citation_note="May 2024 national estimate",
    )
    return replace(base, **overrides)


def codes(result):
    return {issue.code for issue in result.issues}


def test_annual_government_wage_becomes_hourly_with_its_citation():  # AC-S3.2
    result = validate_rate(cited())
    assert result.accepted
    obs = result.observation
    assert obs.hourly_min_usd == obs.hourly_max_usd == Decimal("50.00")
    assert obs.rater_kind == "outside_option"
    assert obs.citation_url == "https://www.bls.gov/oes/"


@pytest.mark.parametrize("url", [None, "", "   "])
def test_hand_entered_rate_without_citation_is_rejected(url):  # AC-S3.1
    result = validate_rate(cited(citation_url=url, provenance_kind="literature"))
    assert not result.accepted
    assert IssueCode.CITATION_MISSING in codes(result)


def test_job_board_rate_needs_its_posting_not_a_url():
    job = cited(provenance_kind="job_board", citation_url=None, rater_kind="expert", engagement="contractor",
                amount_min=65, amount_max=158, unit="hour", domain="stem_science")
    assert IssueCode.CITATION_MISSING in codes(validate_rate(job))
    accepted = validate_rate(replace(job, raw_posting_id=7))
    assert accepted.accepted
    assert (accepted.observation.hourly_min_usd, accepted.observation.hourly_max_usd) == (Decimal("65.00"), Decimal("158.00"))


@pytest.mark.parametrize(
    "field, value",
    [("domain", "astrology"), ("engagement", "volunteer"), ("rater_kind", "robot"), ("provenance_kind", "rumor")],
)
def test_values_outside_the_vocabulary_are_rejected(field, value):
    result = validate_rate(cited(**{field: value}))
    assert not result.accepted
    assert IssueCode.VOCAB_UNKNOWN in codes(result)


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"amount_min": 5, "amount_max": 5, "unit": "task"}, IssueCode.UNIT_NOT_NORMALIZABLE),
        ({"currency": "EUR"}, IssueCode.CURRENCY_UNSUPPORTED),
        ({"amount_min": 2_000_000, "amount_max": 2_000_000}, IssueCode.OUT_OF_BAND),
        ({"amount_min": 90, "amount_max": 40, "unit": "hour"}, IssueCode.RANGE_INVERTED),
        ({"unit": "fortnight"}, IssueCode.UNIT_UNKNOWN),
    ],
)
def test_rates_that_cannot_be_clean_hourly_usd_are_rejected(overrides, code):
    result = validate_rate(cited(**overrides))
    assert not result.accepted
    assert code in codes(result)


def test_low_published_crowd_wage_is_kept():
    """The rate floor is $1/h, not the $5/h posting floor: a ~$2/h crowd median is a real figure."""
    result = validate_rate(cited(amount_min=2, amount_max=2, unit="hour", rater_kind="crowd", domain="none",
                                 provenance_kind="literature"))
    assert result.accepted


def test_missing_external_key_is_rejected():
    assert IssueCode.MISSING_FIELD in codes(validate_rate(cited(external_key=" ")))


@pytest.mark.parametrize(
    "title, domain",
    [
        ("AI Red Teamer, CBRNE (Remote)", "stem_science"),
        ("AI Red Teamer, Cybersecurity (Remote)", "coding"),
        ("Legal Expert", "law"),
        ("Software Engineer Intern", "coding"),
        ("Operations Lead", "none"),
        (None, "none"),
    ],
)
def test_domain_from_title(title, domain):
    assert domain_from_title(title) == domain
