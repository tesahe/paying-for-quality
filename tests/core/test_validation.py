"""FR-2: extraction validation, including the evidence check that blocks invented pay figures."""

from paying_for_quality.core.entities import ExtractionCandidate, Outcome, PayQuoteCandidate
from paying_for_quality.core.errors import IssueCode
from paying_for_quality.core.validation import ValidationPolicy, validate_extraction

RAW = (
    "Senior Physician Reviewer\n"
    "Help train medical AI models. Compensation:  $90 – $120 per hour, paid weekly.\n"
    "Requires an MD and active license."
)


def candidate(*quotes, **kw):
    fields = dict(company="Acme Data", title="Senior Physician Reviewer", domain="medicine", pay_quotes=quotes)
    fields.update(kw)
    return ExtractionCandidate(**fields)


def pay(amount_min, amount_max, evidence, unit="hour"):
    return PayQuoteCandidate(amount_min=amount_min, amount_max=amount_max, unit=unit, evidence=evidence)


def codes(result):
    return [issue.code for issue in result.issues]


def test_valid_candidate_is_accepted():  # AC-2.1
    result = validate_extraction(candidate(pay(90, 120, "$90 - $120 per hour")), RAW)
    assert result.outcome is Outcome.ACCEPTED
    assert result.issues == ()
    assert result.posting.title == "Senior Physician Reviewer"
    assert [str(q.hourly_max_usd) for q in result.posting.pay_quotes] == ["120.00"]


def test_evidence_matching_ignores_case_dashes_and_whitespace():
    result = validate_extraction(candidate(pay(90, 120, "COMPENSATION: $90 – $120  PER HOUR")), RAW)
    assert result.outcome is Outcome.ACCEPTED


def test_invented_pay_figure_is_rejected():  # AC-2.2
    result = validate_extraction(candidate(pay(150, 200, "$150 - $200 per hour")), RAW)
    assert result.outcome is Outcome.REJECTED
    assert result.posting is None
    assert codes(result) == [IssueCode.EVIDENCE_NOT_FOUND]


def test_amount_not_in_real_evidence_quote_is_rejected():
    # The quote is real, but the amount was changed: an LLM "rounding up" pay.
    result = validate_extraction(candidate(pay(95, 120, "$90 – $120 per hour")), RAW)
    assert result.outcome is Outcome.REJECTED
    assert codes(result) == [IssueCode.EVIDENCE_NOT_FOUND]


def test_missing_evidence_is_rejected():
    result = validate_extraction(candidate(pay(90, 120, "")), RAW)
    assert codes(result) == [IssueCode.EVIDENCE_NOT_FOUND]


def test_number_formats_match():
    raw = "Salary: $52,000 per year. Bonus: up to 10k."
    accepted = validate_extraction(candidate(pay("52000", None, "$52,000 per year", unit="year")), raw)
    assert accepted.outcome is Outcome.ACCEPTED
    assert str(accepted.posting.pay_quotes[0].hourly_min_usd) == "25.00"
    k_suffix = validate_extraction(candidate(pay(10000, None, "up to 10k", unit="year")), raw)
    assert IssueCode.EVIDENCE_NOT_FOUND not in codes(k_suffix)


def test_k_suffix_only_when_not_part_of_a_word():
    from decimal import Decimal

    from paying_for_quality.core.validation import numbers_in

    assert numbers_in("$52,000 known bonus") == {Decimal(52000)}
    assert numbers_in("$90hr or 120 K") == {Decimal(90), Decimal(120000)}
    assert numbers_in("$160K – $1.5M • Offers Equity") == {Decimal(160000), Decimal(1500000)}
    assert numbers_in("10 Mbps") == {Decimal(10)}


def test_low_confidence_goes_to_review():  # AC-2.3
    result = validate_extraction(candidate(pay(90, 120, "$90 – $120 per hour"), confidence=0.4), RAW)
    assert result.outcome is Outcome.REVIEW
    assert result.posting is not None  # kept so a reviewer can accept it
    assert codes(result) == [IssueCode.LOW_CONFIDENCE]


def test_deterministic_extractor_has_no_confidence_check():
    result = validate_extraction(candidate(pay(90, 120, "$90 – $120 per hour"), confidence=None), RAW)
    assert result.outcome is Outcome.ACCEPTED


def test_out_of_band_hourly_goes_to_review():
    raw = "Pay: $2 per hour"
    result = validate_extraction(candidate(pay(2, None, "$2 per hour")), raw)
    assert result.outcome is Outcome.REVIEW
    assert codes(result) == [IssueCode.OUT_OF_BAND]


def test_policy_thresholds_are_configurable():
    strict = ValidationPolicy(hourly_ceiling_usd=100)
    result = validate_extraction(candidate(pay(90, 120, "$90 – $120 per hour")), RAW, strict)
    assert result.outcome is Outcome.REVIEW


def test_rejection_beats_review():
    result = validate_extraction(
        candidate(pay(150, 200, "$150 - $200 per hour"), confidence=0.1),
        RAW,
    )
    assert result.outcome is Outcome.REJECTED
    assert set(codes(result)) == {IssueCode.EVIDENCE_NOT_FOUND, IssueCode.LOW_CONFIDENCE}


def test_missing_title_is_rejected():
    result = validate_extraction(candidate(title="  "), RAW)
    assert result.outcome is Outcome.REJECTED
    assert codes(result) == [IssueCode.MISSING_FIELD]


def test_posting_without_pay_is_accepted():
    # Many postings don't state pay; that is data (pay transparency), not an error.
    result = validate_extraction(candidate(), RAW)
    assert result.outcome is Outcome.ACCEPTED
    assert result.posting.pay_quotes == ()


def test_informational_issue_does_not_block_acceptance():
    raw = "Pay: $5 per task"
    result = validate_extraction(candidate(pay(5, None, "$5 per task", unit="task")), raw)
    assert result.outcome is Outcome.ACCEPTED
    assert codes(result) == [IssueCode.UNIT_NOT_NORMALIZABLE]
