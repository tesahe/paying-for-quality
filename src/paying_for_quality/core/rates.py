"""Validate a pay rate from any source into one hourly-USD, cited observation.

Every rate (job-board posting, government statistic, published figure) passes through
`validate_rate`, so the cost-of-quality analysis never has to know where a number came from: only
its provenance, which is kept with it.

A rate is either accepted or rejected (there is no review queue for rates). The rate table must hold
hourly USD, so quotes that cannot be normalized are rejected rather than kept with empty fields.
"""

from __future__ import annotations

from .entities import PayQuoteCandidate, RateCandidate, RateObservation, RateValidation
from .errors import Issue, IssueCode
from .pay import normalize_pay_quote
from .validation import DEFAULT_POLICY, ValidationPolicy
from .vocab import DOMAINS, Engagement, ProvenanceKind, RaterKind

_ENGAGEMENTS = frozenset(e.value for e in Engagement)
_RATER_KINDS = frozenset(k.value for k in RaterKind)
_PROVENANCE = frozenset(p.value for p in ProvenanceKind)


def _vocab_issues(candidate: RateCandidate) -> list[Issue]:
    issues = []
    for name, value, allowed in (
        ("domain", candidate.domain, DOMAINS),
        ("engagement", candidate.engagement, _ENGAGEMENTS),
        ("rater_kind", candidate.rater_kind, _RATER_KINDS),
        ("provenance_kind", candidate.provenance_kind, _PROVENANCE),
    ):
        if value not in allowed:
            issues.append(Issue(IssueCode.VOCAB_UNKNOWN, name, repr(value)))
    return issues


def _citation_issue(candidate: RateCandidate) -> Issue | None:
    """Job-board rates link to their stored posting; every other rate must cite a public source."""
    if candidate.provenance_kind == ProvenanceKind.JOB_BOARD.value:
        if candidate.raw_posting_id is None:
            return Issue(IssueCode.CITATION_MISSING, "raw_posting_id", "job-board rate without its posting")
        return None
    if not (candidate.citation_url or "").strip():
        return Issue(IssueCode.CITATION_MISSING, "citation_url", "no public source given")
    return None


def validate_rate(candidate: RateCandidate, policy: ValidationPolicy = DEFAULT_POLICY) -> RateValidation:
    issues: list[Issue] = []
    if not (candidate.external_key or "").strip():
        issues.append(Issue(IssueCode.MISSING_FIELD, "external_key"))
    issues.extend(_vocab_issues(candidate))
    citation = _citation_issue(candidate)
    if citation:
        issues.append(citation)

    quote, quote_issues = normalize_pay_quote(
        PayQuoteCandidate(
            amount_min=candidate.amount_min,
            amount_max=candidate.amount_max,
            unit=candidate.unit,
            evidence=candidate.citation_note,
            currency=candidate.currency,
        )
    )
    issues.extend(quote_issues)

    if quote is not None and quote.hourly_min_usd is not None and quote.hourly_max_usd is not None:
        for hourly in (quote.hourly_min_usd, quote.hourly_max_usd):
            if not (policy.hourly_floor_usd <= hourly <= policy.hourly_ceiling_usd):
                issues.append(Issue(IssueCode.OUT_OF_BAND, "hourly", f"${hourly}/h"))
                break

    if issues or quote is None or quote.hourly_min_usd is None or quote.hourly_max_usd is None:
        # Any issue rejects: a rate table holds only clean, hourly, cited figures.
        return RateValidation(None, tuple(issues))

    observation = RateObservation(
        external_key=candidate.external_key.strip(),
        amount_min=quote.amount_min,
        amount_max=quote.amount_max,
        currency=quote.currency,
        unit=quote.unit,
        hourly_min_usd=quote.hourly_min_usd,
        hourly_max_usd=quote.hourly_max_usd,
        engagement=candidate.engagement,
        rater_kind=candidate.rater_kind,
        domain=candidate.domain,
        provenance_kind=candidate.provenance_kind,
        occupation=candidate.occupation,
        region=candidate.region,
        as_of=candidate.as_of,
        citation_url=(candidate.citation_url or None),
        citation_note=candidate.citation_note,
        raw_posting_id=candidate.raw_posting_id,
    )
    return RateValidation(observation, ())
