"""FR-3: pay normalization. Expected values were worked out by hand from the stated hour constants."""

from decimal import Decimal

import pytest

from paying_for_quality.core.entities import PayQuoteCandidate, PayUnit
from paying_for_quality.core.errors import IssueCode
from paying_for_quality.core.pay import normalize_pay_quote, parse_amount, parse_unit


def quote(amount_min, amount_max, unit, **kw):
    return PayQuoteCandidate(amount_min=amount_min, amount_max=amount_max, unit=unit, evidence="x", **kw)


@pytest.mark.parametrize(
    "amount_min, amount_max, unit, expected_min, expected_max",
    [
        ("$52,000", None, "year", "25.00", "25.00"),  # AC-3.1: 52,000 / 2,080
        (40, 60, "hour", "40.00", "60.00"),  # AC-3.2
        (300, None, "day", "37.50", "37.50"),  # AC-3.3: 300 / 8
        (2000, 2400, "week", "50.00", "60.00"),  # 40 h/week
        (8000, None, "month", "46.15", "46.15"),  # 8000 / (2080/12) = 46.153...
        ("120k", "150k", "annual", "57.69", "72.12"),  # 'k' suffix and unit alias
        (45.5, None, "/hr", "45.50", "45.50"),  # float input, alias
    ],
)
def test_normalizes_to_hourly(amount_min, amount_max, unit, expected_min, expected_max):
    result, issues = normalize_pay_quote(quote(amount_min, amount_max, unit))
    assert issues == ()
    assert result.hourly_min_usd == Decimal(expected_min)
    assert result.hourly_max_usd == Decimal(expected_max)


def test_single_figure_sets_both_ends():
    result, _ = normalize_pay_quote(quote(None, 75, "hour"))
    assert (result.amount_min, result.amount_max) == (Decimal(75), Decimal(75))


def test_per_task_without_time_is_kept_but_not_normalized():  # AC-3.4
    result, issues = normalize_pay_quote(quote(5, None, "per task"))
    assert result is not None
    assert result.unit is PayUnit.TASK
    assert result.hourly_min_usd is None and result.hourly_max_usd is None
    assert [i.code for i in issues] == [IssueCode.UNIT_NOT_NORMALIZABLE]


def test_per_task_with_stated_time_is_normalized():
    result, issues = normalize_pay_quote(quote(5, None, "task", minutes_per_task=10))
    assert issues == ()
    assert result.hourly_min_usd == Decimal("30.00")  # $5 per 10 minutes


@pytest.mark.parametrize("amount", [-40, 0, "-$40", "forty", "$"])
def test_invalid_amount_is_rejected(amount):  # AC-3.5
    result, issues = normalize_pay_quote(quote(amount, None, "hour"))
    assert result is None
    assert [i.code for i in issues] == [IssueCode.AMOUNT_INVALID]


def test_inverted_range_is_rejected():  # AC-3.5
    result, issues = normalize_pay_quote(quote(60, 40, "hour"))
    assert result is None
    assert [i.code for i in issues] == [IssueCode.RANGE_INVERTED]


def test_missing_amount_is_rejected():
    result, issues = normalize_pay_quote(quote(None, None, "hour"))
    assert result is None
    assert [i.code for i in issues] == [IssueCode.MISSING_FIELD]


@pytest.mark.parametrize("unit", [None, "fortnight", ""])
def test_unknown_unit_is_rejected(unit):
    result, issues = normalize_pay_quote(quote(40, None, unit))
    assert result is None
    assert [i.code for i in issues] == [IssueCode.UNIT_UNKNOWN]


def test_non_usd_is_kept_without_hourly():
    result, issues = normalize_pay_quote(quote(40, None, "hour", currency="eur"))
    assert result.currency == "EUR"
    assert result.hourly_min_usd is None
    assert [i.code for i in issues] == [IssueCode.CURRENCY_UNSUPPORTED]


def test_parsers():
    assert parse_amount("$1,234.50") == Decimal("1234.50")
    assert parse_amount(True) is None
    assert parse_amount("1.5M") == Decimal("1500000")
    assert parse_unit("annum") is PayUnit.YEAR
    assert parse_unit("  Hourly ") is PayUnit.HOUR
    assert parse_unit("decade") is None
