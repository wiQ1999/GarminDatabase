"""Time labels for chart geometry, independent of source measurement values."""

from datetime import datetime
from zoneinfo import ZoneInfo


def time_axis_labels(begin, end, count):
    """Evenly spaced ticks with unambiguous Warsaw dates and clock precision."""
    zone = ZoneInfo("Europe/Warsaw")
    first = datetime.fromtimestamp(begin / 1000, zone)
    last = datetime.fromtimestamp(end / 1000, zone)
    if end <= begin or count <= 1:
        stamp = (begin + end) // 2
        fmt = "%H:%M:%S" if first.date() == last.date() else "%d.%m.%Y %H:%M"
        return [(stamp, datetime.fromtimestamp(stamp / 1000, zone).strftime(fmt))]
    step = (end - begin) / (count - 1)
    clock = "%H:%M:%S" if step < 60000 else "%H:%M"
    fmt = (
        clock
        if first.date() == last.date()
        else "%d.%m " + clock
        if step < 86400000
        else "%d.%m.%Y"
    )
    if "%H" in fmt and first.utcoffset() != last.utcoffset():
        fmt += " %z"
    return [
        (
            stamp := begin + round((end - begin) * i / (count - 1)),
            datetime.fromtimestamp(stamp / 1000, zone).strftime(fmt),
        )
        for i in range(count)
    ]
