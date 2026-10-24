from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def yesterday():
    return datetime.now(ZoneInfo("Europe/Warsaw")).date() - timedelta(days=1)


def dates(start, end):
    if start > end or end > yesterday():
        raise ValueError(
            "Zakres musi być uporządkowany i kończyć się najpóźniej wczoraj"
        )
    for n in range((end - start).days + 1):
        yield start + timedelta(days=n)
