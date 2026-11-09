"""Named validation issues. Every Core rejection or review carries one of these codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IssueCode(str, Enum):
    # Fatal: the candidate (or pay quote) cannot be trusted.
    MISSING_FIELD = "MISSING_FIELD"
    AMOUNT_INVALID = "AMOUNT_INVALID"
    RANGE_INVERTED = "RANGE_INVERTED"
    UNIT_UNKNOWN = "UNIT_UNKNOWN"
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    # Needs a human look.
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OUT_OF_BAND = "OUT_OF_BAND"
    # Informational: the quote is kept, but has no hourly figure.
    UNIT_NOT_NORMALIZABLE = "UNIT_NOT_NORMALIZABLE"
    CURRENCY_UNSUPPORTED = "CURRENCY_UNSUPPORTED"


REJECT_CODES = frozenset(
    {
        IssueCode.MISSING_FIELD,
        IssueCode.AMOUNT_INVALID,
        IssueCode.RANGE_INVERTED,
        IssueCode.UNIT_UNKNOWN,
        IssueCode.EVIDENCE_NOT_FOUND,
    }
)
REVIEW_CODES = frozenset({IssueCode.LOW_CONFIDENCE, IssueCode.OUT_OF_BAND})


class PfqError(Exception):
    """A handled error. The message is shown to the user, so it must never contain secrets."""


class SourceNotAllowed(PfqError):
    """The source has not passed its robots.txt / terms check."""


class SourceFetchError(PfqError):
    """A posting source could not be reached or returned unusable data."""


class ConfigError(PfqError):
    """Missing or invalid configuration (.env, registry)."""


class StorageError(PfqError):
    """The database could not be reached or rejected an operation."""


@dataclass(frozen=True)
class Issue:
    code: IssueCode
    field: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "field": self.field, "detail": self.detail}
