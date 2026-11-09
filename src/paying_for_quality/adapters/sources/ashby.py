"""Ashby public job-posting API: GET api.ashbyhq.com/posting-api/job-board/<board>?includeCompensation=true

One request per collection run. Only listed postings (isListed) are kept.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

from ...core.entities import RawPostingDoc
from ...core.errors import SourceFetchError
from .http import get_json

URL = "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
METADATA_KEYS = ("department", "team", "employmentType", "workplaceType", "location", "isRemote", "compensation")


def compensation_summary(job: dict[str, Any]) -> str:
    comp = job.get("compensation") or {}
    return comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary") or ""


def job_to_doc(job: dict[str, Any], company: str) -> RawPostingDoc:
    """The posting text is the plain description plus the compensation summary, so that any pay
    figure an extractor reports can be checked against text the posting actually shows."""
    text = (job.get("descriptionPlain") or "").strip()
    summary = compensation_summary(job)
    if summary:
        text = f"{text}\n\nCompensation: {summary}"
    return RawPostingDoc(
        external_id=str(job["id"]),
        url=job.get("jobUrl") or "",
        title=(job.get("title") or "").strip(),
        company=company,
        text=text,
        posted_at=job.get("publishedAt"),
        metadata={key: job.get(key) for key in METADATA_KEYS if job.get(key) is not None},
    )


class AshbySource:
    def __init__(self, board: str, company: str, fetch: Callable[[str], Any] = get_json) -> None:
        self.board = board
        self.company = company
        self._fetch = fetch

    def list_postings(self) -> Iterator[RawPostingDoc]:
        data = self._fetch(URL.format(board=self.board))
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise SourceFetchError(f"Ashby board '{self.board}' returned an unexpected response")
        for job in jobs:
            if job.get("isListed", True) and job.get("id"):
                yield job_to_doc(job, self.company)
