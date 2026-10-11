from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from garmin_database.time_axis import time_axis_labels

pytestmark = pytest.mark.unit


def stamp(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


@pytest.mark.parametrize(
    "span,count,kind",
    [
        (45000, 6, "seconds"),
        (3 * 3600000, 7, "clock"),
        (2 * 86400000, 6, "date_clock"),
        (30 * 86400000, 5, "date"),
    ],
)
def test_ticks_include_interior_times_and_suitable_precision(span, count, kind):
    begin = stamp("2026-10-09T06:00:00+00:00")
    ticks = time_axis_labels(begin, begin + span, count)
    assert len(ticks) == count
    assert ticks[0][0] == begin and ticks[-1][0] == begin + span
    assert all(a[0] < b[0] for a, b in zip(ticks, ticks[1:]))
    assert len({label for _, label in ticks}) == count
    for timestamp, label in ticks:
        local = datetime.fromtimestamp(timestamp / 1000, ZoneInfo("Europe/Warsaw"))
        fmt = {
            "seconds": "%H:%M:%S",
            "clock": "%H:%M",
            "date_clock": "%d.%m %H:%M",
            "date": "%d.%m.%Y",
        }[kind]
        assert label == local.strftime(fmt)


def test_dst_day_labels_include_offsets():
    begin = stamp("2026-10-25T00:00:00+02:00")
    end = stamp("2026-10-25T23:00:00+01:00")
    ticks = time_axis_labels(begin, end, 7)
    assert ticks[0][1] == "00:00 +0200"
    assert ticks[-1][1] == "23:00 +0100"
    assert len(ticks) == 7


def test_single_observation_and_narrow_axis_fallback():
    begin = stamp("2026-10-09T06:00:00+00:00")
    assert time_axis_labels(begin, begin, 8) == [(begin, "08:00:00")]
    ticks = time_axis_labels(begin, begin + 4 * 86400000, 1)
    assert ticks == [(begin + 2 * 86400000, "11.10.2026 08:00")]
