"""Turn an untrusted ExtractionCandidate into an accepted, rejected or review verdict."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .entities import ExtractionCandidate, Outcome, PayQuote, PayQuoteCandidate, Posting, ValidationResult
from .errors import REJECT_CODES, REVIEW_CODES, Issue, IssueCode
from .pay import SUFFIX_MULTIPLIER, normalize_pay_quote, parse_amount


@dataclass(frozen=True)
class ValidationPolicy:
    """Thresholds. Provisional until the Sprint 3 extraction-accuracy evaluation."""

    min_confidence: float = 0.7
    hourly_floor_usd: Decimal = Decimal(5)
    hourly_ceiling_usd: Decimal = Decimal(500)


DEFAULT_POLICY = ValidationPolicy()

_DASHES = re.compile(r"[‐-―−]")
_SPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)(?:\s?([kKmM])(?![a-zA-Z]))?")


def normalize_text(text: str) -> str:
    """Case-fold, unify dashes and collapse whitespace so evidence matching ignores formatting."""
    return _SPACE.sub(" ", _DASHES.sub("-", text)).strip().casefold()


def numbers_in(text: str) -> set[Decimal]:
    """All numbers in a text, commas removed and k/M suffixes expanded (52k -> 52000, 1.5M -> 1500000)."""
    found: set[Decimal] = set()
    for digits, suffix in _NUMBER.findall(text):
        value = Decimal(digits.replace(",", ""))
        found.add(value * SUFFIX_MULTIPLIER.get(suffix.lower(), 1))
    return found


def check_evidence(quote: PayQuoteCandidate, raw_text: str) -> Issue | None:
    """The evidence must be a real quote from the posting and must contain the stated amounts.

    This is the guard against invented numbers: an extractor cannot report pay that the
    posting does not actually say.
    """
    evidence = normalize_text(quote.evidence or "")
    if not evidence:
        return Issue(IssueCode.EVIDENCE_NOT_FOUND, "pay_quotes.evidence", "no evidence quote given")
    if evidence not in normalize_text(raw_text):
        return Issue(IssueCode.EVIDENCE_NOT_FOUND, "pay_quotes.evidence", "quote does not appear in the posting")
    numbers = numbers_in(quote.evidence)
    for raw in (quote.amount_min, quote.amount_max):
        amount = parse_amount(raw)
        if amount is not None and amount > 0 and amount not in numbers:
            return Issue(IssueCode.EVIDENCE_NOT_FOUND, "pay_quotes.amount", f"{amount} is not in the evidence quote")
    return None


def validate_extraction(
    candidate: ExtractionCandidate, raw_text: str, policy: ValidationPolicy = DEFAULT_POLICY
) -> ValidationResult:
    """Accept, reject or send to review. Any reject code wins over any review code."""
    issues: list[Issue] = []

    for name in ("company", "title"):
        if not (getattr(candidate, name) or "").strip():
            issues.append(Issue(IssueCode.MISSING_FIELD, name))

    quotes: list[PayQuote] = []
    for quote_candidate in candidate.pay_quotes:
        evidence_issue = check_evidence(quote_candidate, raw_text)
        if evidence_issue:
            issues.append(evidence_issue)
            continue
        quote, quote_issues = normalize_pay_quote(quote_candidate)
        issues.extend(quote_issues)
        if quote is None:
            continue
        quotes.append(quote)
        for hourly in (quote.hourly_min_usd, quote.hourly_max_usd):
            if hourly is not None and not (policy.hourly_floor_usd <= hourly <= policy.hourly_ceiling_usd):
                issues.append(Issue(IssueCode.OUT_OF_BAND, "pay_quotes.hourly", f"${hourly}/h"))
                break

    if candidate.confidence is not None and candidate.confidence < policy.min_confidence:
        issues.append(Issue(IssueCode.LOW_CONFIDENCE, "confidence", f"{candidate.confidence:.2f}"))

    codes = {issue.code for issue in issues}
    if codes & REJECT_CODES:
        return ValidationResult(Outcome.REJECTED, None, tuple(issues))

    posting = Posting(
        company=(candidate.company or "").strip(),
        title=(candidate.title or "").strip(),
        platform=candidate.platform,
        domain=candidate.domain,
        seniority=candidate.seniority,
        credentials=tuple(candidate.credentials),
        posted_at=candidate.posted_at,
        pay_quotes=tuple(quotes),
    )
    outcome = Outcome.REVIEW if codes & REVIEW_CODES else Outcome.ACCEPTED
    return ValidationResult(outcome, posting, tuple(issues))
