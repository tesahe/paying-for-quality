"""Domain entities. Plain frozen dataclasses with no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from .errors import Issue


class PayUnit(str, Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    TASK = "task"
    PROJECT = "project"


class Outcome(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVIEW = "review"


@dataclass(frozen=True)
class SourceInfo:
    """One entry of the source registry (data/sources.toml)."""

    slug: str
    kind: str
    board: str
    company: str
    segment: str  # "staff" (company employees) or "expert" (contractor gigs)
    terms_checked: bool
    robots_checked_at: str | None = None
    terms_note: str = ""


@dataclass(frozen=True)
class RawPostingDoc:
    """One posting as fetched from a source, before any extraction."""

    external_id: str
    url: str
    title: str
    company: str
    text: str
    posted_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PayQuoteCandidate:
    """A pay figure as proposed by an extractor. Untrusted until validated."""

    amount_min: Any
    amount_max: Any
    unit: str | None
    evidence: str
    currency: str = "USD"
    minutes_per_task: Any = None


@dataclass(frozen=True)
class ExtractionCandidate:
    """Everything an extractor proposes for one posting. Untrusted until validated."""

    company: str | None
    title: str | None
    platform: str | None = None
    domain: str | None = None
    seniority: str | None = None
    credentials: tuple[str, ...] = ()
    posted_at: str | None = None
    pay_quotes: tuple[PayQuoteCandidate, ...] = ()
    confidence: float | None = None  # None = deterministic extractor, no confidence score


@dataclass(frozen=True)
class PayQuote:
    """A validated pay quote. Hourly fields are None when not normalizable."""

    amount_min: Decimal
    amount_max: Decimal
    currency: str
    unit: PayUnit
    hourly_min_usd: Decimal | None
    hourly_max_usd: Decimal | None
    evidence: str


@dataclass(frozen=True)
class Posting:
    company: str
    title: str
    platform: str | None
    domain: str | None
    seniority: str | None
    credentials: tuple[str, ...]
    posted_at: str | None
    pay_quotes: tuple[PayQuote, ...]


@dataclass(frozen=True)
class ValidationResult:
    outcome: Outcome
    posting: Posting | None
    issues: tuple[Issue, ...] = ()
