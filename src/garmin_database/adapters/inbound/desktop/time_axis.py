"""Time labels for chart geometry, independent of source measurement values."""

from datetime import datetime

from garmin_database.application.time_presentation import WARSAW


def time_axis_labels(begin, end, count):
    """Evenly spaced ticks with unambiguous Warsaw dates and clock precision."""
    zone = WARSAW
    first = datetime.fromtimestamp(begin / 1000, zone)
    last = datetime.fromtimestamp(end / 1000, zone)
    if end <= begin or count <= 1:
        stamp = (begin + end) // 2
        fmt = "%H:%M:%S" if first.date() == last.date() else "%Y-%m-%d %H:%M"
        return [(stamp, datetime.fromtimestamp(stamp / 1000, zone).strftime(fmt))]
    step = (end - begin) / (count - 1)
    clock = "%H:%M:%S" if step < 60000 else "%H:%M"
    fmt = (
        clock
        if first.date() == last.date()
        else "%Y-%m-%d " + clock
        if step < 86400000
        else "%Y-%m-%d"
    )
    show_offset = "%H" in fmt and first.utcoffset() != last.utcoffset()
    return [
        (
            stamp := begin + round((end - begin) * i / (count - 1)),
            (local := datetime.fromtimestamp(stamp / 1000, zone)).strftime(fmt)
            + (" " + local.isoformat()[-6:] if show_offset else ""),
        )
        for i in range(count)
    ]
