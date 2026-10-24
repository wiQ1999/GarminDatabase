import math

import pytest

from garmin_database.adapters.inbound.desktop.trend import linear_trend

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "points",
    [[], [(0, 5, "a")], [(0, 5, "a"), (0, 8, "b")], [(0, None, "a")]],
)
def test_no_fit_without_two_observations_at_distinct_times(points):
    assert linear_trend(points) == []


@pytest.mark.parametrize("offset", [0, 1_800_000_000_000])
def test_regression_uses_actual_time_and_is_stable_for_epoch_timestamps(offset):
    # Irregular sampling must fit elapsed time, rather than point index.
    points = [(offset + x, 3 * x + 7, "") for x in (0, 1, 9, 12)]
    trend = linear_trend(points)
    assert trend[0][0] == offset and trend[-1][0] == offset + 12
    assert [v for _, v in trend] == pytest.approx([7, 43])
    assert points == [(offset + x, 3 * x + 7, "") for x in (0, 1, 9, 12)]


def test_gaps_and_non_numeric_or_nonfinite_values_are_excluded():
    points = [(0, 10, ""), (10, 20, "")]
    invalid = [None, "text", [], True, math.nan, math.inf, -math.inf]
    points += [(5, value, "") for value in invalid]
    points += [(math.nan, 300, ""), (math.inf, 300, "")]
    assert linear_trend(points) == [(0, 10), (10, 20)]


def test_horizontal_trend_for_constant_values():
    assert linear_trend([(0, 4, ""), (10, 4, ""), (20, 4, "")]) == [
        (0, 4),
        (20, 4),
    ]


def test_least_squares_fit_for_noisy_values():
    assert linear_trend([(0, 2, ""), (1, 8, ""), (2, 5, "")]) == [
        (0, 3.5),
        (2, 6.5),
    ]
