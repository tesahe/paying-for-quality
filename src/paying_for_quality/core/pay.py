"""Pay parsing and normalization to an hourly USD range.

Conversion assumptions live here and nowhere else:
8 hours/day, 40 hours/week, 2,080 hours/year, 2,080/12 hours/month.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .entities import PayQuote, PayQuoteCandidate, PayUnit
from .errors import Issue, IssueCode

HOURS_PER_UNIT: dict[PayUnit, Decimal] = {
    PayUnit.HOUR: Decimal(1),
    PayUnit.DAY: Decimal(8),
    PayUnit.WEEK: Decimal(40),
    PayUnit.MONTH: Decimal(2080) / Decimal(12),
    PayUnit.YEAR: Decimal(2080),
}

_UNIT_ALIASES: dict[str, PayUnit] = {
    **{a: PayUnit.HOUR for a in ("hour", "hr", "h", "hourly", "per hour", "/hr", "/hour")},
    **{a: PayUnit.DAY for a in ("day", "daily", "per day", "/day")},
    **{a: PayUnit.WEEK for a in ("week", "wk", "weekly", "per week", "/week")},
    **{a: PayUnit.MONTH for a in ("month", "mo", "monthly", "per month", "/month")},
    **{a: PayUnit.YEAR for a in ("year", "yr", "annual", "annually", "annum", "yearly", "salary", "per year", "/year", "/yr")},
    **{a: PayUnit.TASK for a in ("task", "per task", "item", "per item")},
    **{a: PayUnit.PROJECT for a in ("project", "per project")},
}

_CENT = Decimal("0.01")
SUFFIX_MULTIPLIER = {"k": 1_000, "m": 1_000_000}


def parse_amount(value: Any) -> Decimal | None:
    """Parse 52000, "52,000", "$52,000", "52k", "1.5M" or "$45.50" into a Decimal. None if unparseable."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    text = str(value).strip().lower().replace("$", "").replace(",", "").replace("usd", "").strip()
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*([km]?)", text)
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    return amount * SUFFIX_MULTIPLIER.get(match.group(2), 1)


def parse_unit(value: str | None) -> PayUnit | None:
    if value is None:
        return None
    return _UNIT_ALIASES.get(value.strip().lower())


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def normalize_pay_quote(candidate: PayQuoteCandidate) -> tuple[PayQuote | None, tuple[Issue, ...]]:
    """Validate one pay quote candidate and convert it to hourly USD.

    Returns (None, issues) when the quote is unusable, or (quote, issues) where the issues are
    informational only (the quote is kept, but its hourly fields may be None).
    """
    raw_min, raw_max = candidate.amount_min, candidate.amount_max
    if raw_min is None and raw_max is None:
        return None, (Issue(IssueCode.MISSING_FIELD, "amount", "no pay amount given"),)

    amount_min = parse_amount(raw_min if raw_min is not None else raw_max)
    amount_max = parse_amount(raw_max if raw_max is not None else raw_min)
    if amount_min is None or amount_max is None or amount_min <= 0 or amount_max <= 0:
        return None, (Issue(IssueCode.AMOUNT_INVALID, "amount", f"{raw_min!r} to {raw_max!r}"),)
    if amount_min > amount_max:
        return None, (Issue(IssueCode.RANGE_INVERTED, "amount", f"{amount_min} > {amount_max}"),)

    unit = parse_unit(candidate.unit)
    if unit is None:
        return None, (Issue(IssueCode.UNIT_UNKNOWN, "unit", repr(candidate.unit)),)

    currency = (candidate.currency or "USD").strip().upper()
    issues: list[Issue] = []
    hourly_min = hourly_max = None

    if currency != "USD":
        issues.append(Issue(IssueCode.CURRENCY_UNSUPPORTED, "currency", currency))
    elif unit in HOURS_PER_UNIT:
        hours = HOURS_PER_UNIT[unit]
        hourly_min, hourly_max = to_cents(amount_min / hours), to_cents(amount_max / hours)
    else:  # task / project
        minutes = parse_amount(candidate.minutes_per_task)
        if minutes is not None and minutes > 0:
            factor = Decimal(60) / minutes
            hourly_min, hourly_max = to_cents(amount_min * factor), to_cents(amount_max * factor)
        else:
            issues.append(
                Issue(IssueCode.UNIT_NOT_NORMALIZABLE, "unit", f"per-{unit.value} pay with no time per {unit.value}")
            )

    quote = PayQuote(
        amount_min=amount_min,
        amount_max=amount_max,
        currency=currency,
        unit=unit,
        hourly_min_usd=hourly_min,
        hourly_max_usd=hourly_max,
        evidence=candidate.evidence,
    )
    return quote, tuple(issues)
