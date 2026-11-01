"""Warsaw presentation of instants; storage and scheduling remain in UTC."""

from datetime import datetime
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def warsaw_time(value):
    instant = datetime.fromisoformat(value) if isinstance(value, str) else value
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Czas wymaga jawnej strefy")
    return instant.astimezone(WARSAW)


def warsaw_iso(value):
    """Preserve precision and the instant, including both occurrences of DST folds."""
    return warsaw_time(value).isoformat() if value is not None else None


def display_time(value):
    if not value:
        return "brak"
    try:
        text = warsaw_time(value).isoformat(sep=" ", timespec="seconds")
        return text[:19] + " " + text[19:]
    except (ValueError, TypeError, AttributeError):
        return "nieprawidłowy czas"


def collector_log_text(text):
    """Render legacy ISO log records; current formatted records remain unchanged."""
    lines = []
    for line in text.splitlines(keepends=True):
        timestamp, separator, event = line.partition(" ")
        try:
            warsaw_time(timestamp)
        except (ValueError, TypeError):
            lines.append(line)  # Includes incomplete first lines in bounded log tails.
        else:
            lines.append(display_time(timestamp) + separator + event)
    return "".join(lines)


def collector_status_times(value):
    """Copy public CLI status, converting only known timestamp fields."""
    timestamp_keys = {
        "next_run",
        "started_at",
        "finished_at",
        "last_success",
        "not_before",
        "claimed_slot",
        "retry_not_before",
    }
    return {
        key: collector_status_times(item)
        if isinstance(item, dict)
        else warsaw_iso(item)
        if key in timestamp_keys
        else item
        for key, item in value.items()
    }
