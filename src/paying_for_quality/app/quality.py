"""Quality use case (FR-6): agreement within each rater group and expert vs. crowd, per dimension.

The first quality slice reads a dataset file and reports; storing ratings in the database (the
planned dataset / item / rater / label tables) comes with the LLM-judge comparison.
"""

from __future__ import annotations

from ..core.agreement import RatingData, group_correlation, krippendorff_alpha, mean_gap, pairable_units
from ..core.ports import QueryResult

COLUMNS = (
    "dimension", "expert_alpha", "crowd_alpha", "expert_crowd_r", "expert_minus_crowd", "units",
)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def agreement_report(data: RatingData, first: str = "expert", second: str = "crowd") -> QueryResult:
    """One row per dimension. Alpha is interval-level (Likert scores treated as equally spaced)."""
    rows = []
    for dimension in data.dimensions:
        experts = data.tables[(dimension, first)]
        crowd = data.tables[(dimension, second)]
        rows.append((
            dimension,
            _round(krippendorff_alpha(experts, "interval")),
            _round(krippendorff_alpha(crowd, "interval")),
            _round(group_correlation(experts, crowd)),
            _round(mean_gap(experts, crowd)),
            len(pairable_units(experts)),
        ))
    return QueryResult(COLUMNS, tuple(rows))
