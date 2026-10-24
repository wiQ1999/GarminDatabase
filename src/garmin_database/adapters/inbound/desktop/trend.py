"""Display-only linear regression; never persisted or exported as Garmin data."""

from math import fsum, isfinite


def linear_trend(points):
    """Fit value against actual time, using finite numeric observations only."""
    values = [
        (stamp, value)
        for stamp, value, _ in points
        if isinstance(stamp, (int, float))
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(stamp)
        and isfinite(value)
    ]
    if len(values) < 2:
        return []
    begin = min(stamp for stamp, _ in values)
    end = max(stamp for stamp, _ in values)
    if begin == end:
        return []
    # Relative time avoids loss of precision from large epoch timestamps.
    xs = [(stamp - begin) / (end - begin) for stamp, _ in values]
    mean_x = fsum(xs) / len(xs)
    mean_y = fsum(value for _, value in values) / len(values)
    variance = fsum((x - mean_x) ** 2 for x in xs)
    slope = (
        fsum((x - mean_x) * (value - mean_y) for x, (_, value) in zip(xs, values))
        / variance
    )
    return [(begin, mean_y - slope * mean_x), (end, mean_y + slope * (1 - mean_x))]
