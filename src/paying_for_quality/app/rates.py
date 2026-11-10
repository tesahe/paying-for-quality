"""Rate use case: load pay rates from any RateSource through one Core validation path (FR-9).

Also holds `JobBoardRates`, the RateSource that turns already-accepted job-board postings into rate
observations. It needs the repository and the raw store, so it lives with the use cases rather than
with the outside-world adapters.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterator

from ..core.entities import RateCandidate, RateSourceInfo
from ..core.errors import SourceNotAllowed
from ..core.ports import RateSource, RawStore, Repository
from ..core.rates import validate_rate
from ..core.serialization import doc_from_json
from ..core.vocab import Engagement, RaterKind, domain_from_title

Clock = Callable[[], datetime]

# Ashby `employmentType` → engagement. Anything else is "unknown".
EMPLOYMENT_TYPES = {
    "FullTime": Engagement.EMPLOYEE,
    "PartTime": Engagement.EMPLOYEE,
    "Contract": Engagement.CONTRACTOR,
    "Intern": Engagement.INTERN,
    "Temporary": Engagement.TEMPORARY,
}


def rater_kind_for(engagement: Engagement) -> RaterKind:
    """Provisional rule: contract and temporary roles price expert data work; the rest is staff."""
    if engagement in (Engagement.CONTRACTOR, Engagement.TEMPORARY):
        return RaterKind.EXPERT
    return RaterKind.STAFF


@dataclass
class LoadRatesResult:
    source: str
    new: int = 0
    unchanged: int = 0
    rejected: int = 0
    issue_counts: Counter = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return self.new + self.unchanged + self.rejected


def load_rates(info: RateSourceInfo, source: RateSource, repo: Repository, now: Clock) -> LoadRatesResult:
    """Validate every candidate in Core and store the accepted ones. Re-running adds nothing new."""
    if not info.terms_checked:
        raise SourceNotAllowed(
            f"rate source '{info.slug}' has not passed its terms check (terms_checked = false in the registry)"
        )
    rate_source_id = repo.upsert_rate_source(info)
    result = LoadRatesResult(info.slug)
    for candidate in source.list_rates():
        verdict = validate_rate(candidate)
        if verdict.observation is None:
            result.rejected += 1
            result.issue_counts.update(issue.code.value for issue in verdict.issues)
            continue
        if repo.insert_rate(rate_source_id, verdict.observation, now()):
            result.new += 1
        else:
            result.unchanged += 1
    return result


class JobBoardRates:
    """Rates from current, Core-accepted job-board postings with hourly-normalizable USD pay.

    Engagement comes from the source's structured employment type (kept in the raw snapshot); the
    domain from explicit title keywords. No company name is carried into the rate (aggregate-only rule).
    """

    def __init__(self, repo: Repository, raw_store: RawStore) -> None:
        self.repo = repo
        self.raw_store = raw_store

    def list_rates(self) -> Iterator[RateCandidate]:
        for pay in self.repo.current_posted_pay():
            doc = doc_from_json(self.raw_store.get(pay.raw_path))
            engagement = EMPLOYMENT_TYPES.get(str(doc.metadata.get("employmentType")), Engagement.UNKNOWN)
            yield RateCandidate(
                external_key=f"{pay.raw_posting_id}:{pay.quote_index}",
                amount_min=pay.amount_min,
                amount_max=pay.amount_max,
                unit=pay.unit,
                currency=pay.currency,
                engagement=engagement.value,
                rater_kind=rater_kind_for(engagement).value,
                domain=domain_from_title(pay.title),
                provenance_kind="job_board",
                as_of=doc.posted_at,
                raw_posting_id=pay.raw_posting_id,
            )
