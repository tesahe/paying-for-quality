"""Closed vocabularies shared by every pay source (and, later, the quality side).

The domain list is aligned with MT-Bench's categories so that market rates and quality results can be
joined on `domain` (docs/architecture.md, "Relationships").
"""

from __future__ import annotations

import re
from enum import Enum

DOMAINS = frozenset(
    {
        "coding", "math", "stem_science", "medicine", "law", "finance",
        "writing_humanities", "languages", "reasoning_general", "none",
    }
)


class Engagement(str, Enum):
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"
    INTERN = "intern"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class RaterKind(str, Enum):
    """What kind of labor a rate prices."""

    EXPERT = "expert"  # domain experts doing data work (contract or gig)
    CROWD = "crowd"  # non-expert crowd raters
    STAFF = "staff"  # the companies' own employees (ops, quality, engineering, ...)
    OUTSIDE_OPTION = "outside_option"  # what an expert earns outside AI data work (e.g. BLS wages)


class ProvenanceKind(str, Enum):
    JOB_BOARD = "job_board"  # a public job-board API posting (Ashby, Greenhouse)
    GOV_STATISTIC = "gov_statistic"  # official statistics (BLS OEWS)
    LITERATURE = "literature"  # a published study or guidance page
    DATASET_PAPER = "dataset_paper"  # a dataset paper stating what its raters were paid
    SELF_TIMED = "self_timed"  # the owner's own timed labeling of public items


# Provisional keyword rules, checked in order; first match wins. Replaced by LLM extraction in Sprint 4.
_TITLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("medicine", ("medical", "medicine", "physician", "doctor", "clinical", "nurse", "health")),
    ("law", ("legal", "law", "lawyer", "attorney", "paralegal")),
    ("finance", ("finance", "financial", "accounting", "accountant", "investment", "banking")),
    ("math", ("math", "mathematics", "mathematician", "statistician", "statistics")),
    ("stem_science", ("physics", "chemistry", "biology", "cbrne", "scientist", "science")),
    ("languages", ("translator", "translation", "interpreter", "linguist", "bilingual")),
    ("writing_humanities", ("writer", "writing", "editor", "humanities", "history", "philosophy")),
    ("coding", ("software", "engineer", "developer", "coding", "programmer", "cybersecurity", "security")),
)


def domain_from_title(title: str | None) -> str:
    """Map a job title to a domain with explicit keywords; `none` when nothing matches."""
    words = set(re.findall(r"[a-z]+", (title or "").lower()))
    for domain, keywords in _TITLE_KEYWORDS:
        if words & set(keywords):
            return domain
    return "none"
