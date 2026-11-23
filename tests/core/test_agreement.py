"""Quality-side Core math (FR-11): Krippendorff's alpha and rater-group comparison."""

import pytest

from paying_for_quality.core.agreement import (
    group_correlation,
    krippendorff_alpha,
    mean_gap,
    pairable_units,
    score_in_scale,
    unit_means,
)

N = None
# Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability": 4 observers x 12 units, with
# missing values. One row per unit here (observers A-D as columns). Published results: nominal
# alpha = 0.743, interval alpha = 0.849.
KRIPPENDORFF_2011 = [
    [1, 1, N, 1], [2, 2, 3, 2], [3, 3, 3, 3], [3, 3, 3, 3], [2, 2, 2, 2], [1, 2, 3, 4],
    [4, 4, 4, 4], [1, 1, 2, 1], [2, 2, 2, 2], [N, 5, 5, 5], [N, N, 1, 1], [N, 3, N, N],
]


def test_alpha_matches_the_published_worked_example():  # AC-11.1
    assert krippendorff_alpha(KRIPPENDORFF_2011, "nominal") == pytest.approx(0.743, abs=5e-4)
    assert krippendorff_alpha(KRIPPENDORFF_2011, "interval") == pytest.approx(0.849, abs=5e-4)


def test_single_rated_unit_is_not_pairable():
    assert len(pairable_units(KRIPPENDORFF_2011)) == 11  # the last unit has one rating


def test_perfect_agreement_is_one_and_rater_order_does_not_matter():
    table = [[1, 1, 1], [3, 3, 3], [5, 5, N]]
    assert krippendorff_alpha(table) == pytest.approx(1.0)
    flipped = [list(reversed(unit)) for unit in KRIPPENDORFF_2011]
    assert krippendorff_alpha(flipped) == pytest.approx(krippendorff_alpha(KRIPPENDORFF_2011))


def test_systematic_disagreement_is_below_zero():
    assert krippendorff_alpha([[1, 5], [5, 1], [1, 5], [5, 1]]) < 0


def test_hand_computed_two_rater_case():
    # Units (1,2) and (3,3). Pairable values n=4: {1,2,3,3}. Coincidences: (1,2),(2,1) weight 1, (3,3) x2.
    # D_o = (1*1 + 1*1) / 4 = 0.5. D_e = sum over value pairs n_c n_k (c-k)^2 / (4*3):
    # pairs (1,2):1, (1,3):2*4=8, (2,3):2*1=2, each counted twice -> 2*(1+8+2)=22 -> 22/12.
    # alpha = 1 - 0.5 / (22/12) = 1 - 6/22.
    assert krippendorff_alpha([[1, 2], [3, 3]]) == pytest.approx(1 - 6 / 22)


@pytest.mark.parametrize("table", [[], [[1]], [[1, N], [N, 2]], [[2, 2], [2, 2]]])
def test_alpha_is_undefined_without_pairs_or_variation(table):  # AC-11.2
    assert krippendorff_alpha(table) is None


def test_unknown_level_is_refused():
    with pytest.raises(ValueError, match="measurement level"):
        krippendorff_alpha(KRIPPENDORFF_2011, "ordinalish")


def test_group_comparison():
    experts = [[1, 1], [3, 3], [5, 4], [2, N]]
    crowd = [[2, 2, 3], [3, 4, 4], [4, 4, 5], [N, N, N]]
    assert unit_means(crowd)[3] is None
    # Means over the 3 shared units: experts (1, 3, 4.5), crowd (7/3, 11/3, 13/3).
    # Hand Pearson: sum dx*dy = 32/9, sum dx^2 = 37/6, sum dy^2 = 56/27 -> r = 0.99419.
    assert group_correlation(experts, crowd) == pytest.approx((32 / 9) / ((37 / 6) * (56 / 27)) ** 0.5)
    assert group_correlation(experts, crowd) == pytest.approx(0.9942, abs=1e-4)
    assert mean_gap(experts, crowd) == pytest.approx(((1 - 7 / 3) + (3 - 11 / 3) + (4.5 - 13 / 3)) / 3)


def test_group_comparison_needs_matching_units_and_variation():
    with pytest.raises(ValueError):
        group_correlation([[1, 2]], [[1, 2], [3, 3]])
    assert group_correlation([[1], [2]], [[1], [2]]) is None  # fewer than 3 shared units
    assert group_correlation([[3], [3], [3]], [[1], [2], [3]]) is None  # no variation


@pytest.mark.parametrize("value, ok", [(1, True), (5, True), (4.5, True), (0, False), (6, False),
                                       (True, False), ("3", False), (None, False)])
def test_scores_must_be_numbers_inside_the_scale(value, ok):  # AC-11.3
    assert score_in_scale(value, 1, 5) is ok
