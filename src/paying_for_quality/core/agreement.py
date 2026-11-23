"""Rater agreement and rater-group comparison: the first quality-side math (Sprint 4, FR-6).

Pure functions over plain numbers. A rating table is a list of units (items); each unit is a list
with one slot per rater, holding a score or None when that rater did not rate the unit.

Krippendorff's alpha follows Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability",
using the coincidence-matrix form, which handles any number of raters and missing ratings:
    alpha = 1 - D_o / D_e
where D_o is the disagreement observed within units and D_e the disagreement expected by chance
from all pairable values. Only units with at least two ratings are pairable.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Sequence

Score = float
RatingTable = Sequence[Sequence[Score | None]]

LEVELS = ("nominal", "interval")


def _delta(level: str) -> Callable[[Score, Score], float]:
    if level == "nominal":
        return lambda a, b: 0.0 if a == b else 1.0
    if level == "interval":
        return lambda a, b: float(a - b) ** 2
    raise ValueError(f"unknown measurement level {level!r}; use one of {', '.join(LEVELS)}")


def pairable_units(table: RatingTable) -> list[list[Score]]:
    """The units that have at least two ratings, with the missing slots dropped."""
    units = [[v for v in unit if v is not None] for unit in table]
    return [unit for unit in units if len(unit) >= 2]


def krippendorff_alpha(table: RatingTable, level: str = "interval") -> float | None:
    """Krippendorff's alpha, or None when it is undefined.

    Undefined means fewer than two pairable values, or no variation at all among them (D_e = 0):
    agreement cannot be told apart from chance, so no number is reported rather than a misleading 1.0.
    """
    delta = _delta(level)
    units = pairable_units(table)
    coincidence: Counter[tuple[Score, Score]] = Counter()
    for unit in units:
        weight = 1.0 / (len(unit) - 1)
        for i, a in enumerate(unit):
            for j, b in enumerate(unit):
                if i != j:
                    coincidence[(a, b)] += weight
    totals: Counter[Score] = Counter()
    for (a, _b), count in coincidence.items():
        totals[a] += count
    n = sum(totals.values())
    if n < 2:
        return None
    observed = sum(count * delta(a, b) for (a, b), count in coincidence.items()) / n
    values = list(totals)
    expected = sum(totals[a] * totals[b] * delta(a, b) for a in values for b in values) / (n * (n - 1))
    if expected == 0:
        return None
    return 1.0 - observed / expected


def unit_means(table: RatingTable) -> list[float | None]:
    """Mean score per unit (None for a unit nobody rated)."""
    means: list[float | None] = []
    for unit in table:
        present = [v for v in unit if v is not None]
        means.append(statistics.fmean(present) if present else None)
    return means


def group_correlation(first: RatingTable, second: RatingTable) -> float | None:
    """Pearson correlation between two rater groups' per-unit means over the same units.

    Units missing in either group are skipped. None when fewer than three shared units remain or
    either side has no variation (the correlation is undefined).
    """
    if len(first) != len(second):
        raise ValueError("both rater groups must rate the same units, in the same order")
    pairs = [(a, b) for a, b in zip(unit_means(first), unit_means(second)) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    return statistics.correlation(xs, ys)


def mean_gap(first: RatingTable, second: RatingTable) -> float | None:
    """Mean of (first-group unit mean - second-group unit mean): positive when the first group scores higher."""
    if len(first) != len(second):
        raise ValueError("both rater groups must rate the same units, in the same order")
    gaps = [a - b for a, b in zip(unit_means(first), unit_means(second)) if a is not None and b is not None]
    return statistics.fmean(gaps) if gaps else None


def score_in_scale(value: object, low: int, high: int) -> bool:
    """A rating is accepted only as a number (not a bool) inside the dataset's declared scale."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


@dataclass
class RatingData:
    """A loaded multi-rater dataset: rating tables keyed by (dimension, rater group).

    Every table has one row per item, in the same item order, and one slot per rater. Scores that
    failed validation are stored as None and counted in `rejected_scores`.
    """

    dataset: str
    dimensions: tuple[str, ...]
    groups: tuple[str, ...]
    tables: dict[tuple[str, str], list[list[Score | None]]] = field(default_factory=dict)
    units: int = 0
    rejected_scores: int = 0
