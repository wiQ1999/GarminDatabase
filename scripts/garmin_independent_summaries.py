"""Independent source arithmetic; deliberately do not use the application's reducer/cache."""

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Warsaw")
FIELDS = (
    "mean",
    "minimum",
    "maximum",
    "valid_count",
    "invalid_count",
    "excluded_count",
    "untimed_count",
    "first_time",
    "last_time",
)


def sample_class(row, key):
    if row["time"] is None:
        return "untimed"
    value = row["value"]
    if row["validity"] != "valid" or value is None:
        return "invalid"
    if not numeric_sample(value, key):
        return "excluded"
    return "valid"


def numeric_sample(value, key):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and not (key == "stress_level.stress_level_value" and value < 0)
    )


def summarize_day(day, bucket):
    values, instants, counts = bucket
    return dict(
        day=day,
        mean=math.fsum(values) / len(values) if values else None,
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        valid_count=len(values),
        invalid_count=counts["invalid"],
        excluded_count=counts["excluded"],
        untimed_count=counts["untimed"],
        first_time=min(instants).isoformat() if instants else None,
        last_time=max(instants).isoformat() if instants else None,
    )


def independent_days(rows, key):
    buckets = defaultdict(lambda: ([], [], Counter()))
    for row in rows:
        instant = datetime.fromisoformat(row["time"]) if row["time"] else None
        day = (
            instant.astimezone(ZONE).date().isoformat()
            if instant
            else row["requested_day"]
        )
        values, instants, counts = buckets[day]
        kind = sample_class(row, key)
        counts[kind] += 1
        if kind == "valid":
            values.append(row["value"])
            instants.append(instant.astimezone(timezone.utc))
    return [summarize_day(day, buckets[day]) for day in sorted(buckets)]


def field_equal(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-10)
    return a == b


def differing_days(expected, published):
    different = [
        dict(
            day=day,
            fields=[
                f
                for f in FIELDS
                if not field_equal(expected[day][f], published[day][f])
            ],
        )
        for day in sorted(expected.keys() & published.keys())
    ]
    return [r for r in different if r["fields"]]


def daily_audit(rows, key, actual):
    expected = {r["day"]: r for r in independent_days(rows, key)}
    published = {r["day"]: r for r in actual}
    duplicates = len(actual) - len(published)
    different = differing_days(expected, published)
    missing, extra = (
        sorted(expected.keys() - published.keys()),
        sorted(published.keys() - expected.keys()),
    )
    return dict(
        expected=len(expected),
        actual=len(actual),
        missing=len(missing),
        extra=len(extra),
        different=len(different),
        duplicates=duplicates,
        equal=not (missing or extra or different or duplicates),
        missing_days=missing,
        extra_days=extra,
        differences=different,
        method="independent_fsum_of_source_samples",
    )
