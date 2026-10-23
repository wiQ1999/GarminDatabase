"""Podsumowania dzienne i miesięczne: docs/05-export.md, docs/10-postgresql-schema.md."""

import json
import math
from collections import Counter
from contextlib import ExitStack
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg

from .fit import dumps
from .util import check_stop, utc_now

ALGORITHM_VERSION = 1
ZONE = ZoneInfo("Europe/Warsaw")
MEAN_PARAMETERS = frozenset(
    {
        "hrv_value.value",
        "monitoring.heart_rate",
        "respiration_rate.respiration_rate",
        "spo2_data.reading_spo2",
        "stress_level.stress_level_value",
    }
)


def summary_method(parameter):
    if parameter["representation"] == "source_summary":
        return "garmin"
    if parameter["key"] in MEAN_PARAMETERS:
        return "sample_mean"
    if parameter.get("enum"):
        return "value_counts"
    return "last_observed"


def has_chart_summary(parameter):
    return summary_method(parameter) in {"garmin", "sample_mean"}


def numeric_sample(value, parameter):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and not (parameter["key"] == "stress_level.stress_level_value" and value < 0)
    )


def empty_day(day):
    return dict(
        day=day,
        mean=None,
        minimum=None,
        maximum=None,
        last_value=None,
        value_counts=[],
        valid_count=0,
        invalid_count=0,
        excluded_count=0,
        untimed_count=0,
        first_time=None,
        last_time=None,
        day_basis="measurement_time",
    )


def aggregate_days(rows, parameter, stop=None):
    """One observation has one vote; never infer duration or a missing timestamp."""
    method = summary_method(parameter)
    buckets = {}
    counts = {}
    times = {}
    for row in rows:
        check_stop(stop)
        instant = datetime.fromisoformat(row["time"]) if row["time"] else None
        day = (
            instant.astimezone(ZONE).date().isoformat()
            if instant
            else row["requested_day"]
        )
        if day not in buckets:
            buckets[day] = empty_day(day)
            counts[day] = Counter()
            times[day] = [None, None]
        bucket = buckets[day]
        if instant is None:
            bucket["untimed_count"] += 1
            bucket["day_basis"] = "mixed" if bucket["first_time"] else "requested_day"
            continue
        if bucket["untimed_count"]:
            bucket["day_basis"] = "mixed"
        value = row["value"]
        if row["validity"] != "valid" or value is None:
            bucket["invalid_count"] += 1
            continue
        if method == "sample_mean" and not numeric_sample(value, parameter):
            bucket["excluded_count"] += 1
            continue
        bucket["valid_count"] += 1
        if times[day][0] is None or instant < times[day][0]:
            bucket["first_time"] = row["time"]
            times[day][0] = instant
        # In a tie preserve the deterministic FIT ordering used by Queries.rows.
        if times[day][1] is None or instant >= times[day][1]:
            bucket["last_time"] = row["time"]
            bucket["last_value"] = value
            times[day][1] = instant
        if method == "sample_mean":
            previous = bucket["mean"]
            bucket["mean"] = (
                value
                if previous is None
                else previous + (value - previous) / bucket["valid_count"]
            )
            bucket["minimum"] = (
                value if bucket["minimum"] is None else min(value, bucket["minimum"])
            )
            bucket["maximum"] = (
                value if bucket["maximum"] is None else max(value, bucket["maximum"])
            )
        elif method == "value_counts":
            counts[day][dumps(value)] += 1
    for day, bucket in buckets.items():
        bucket["value_counts"] = [
            [json.loads(key), n] for key, n in sorted(counts[day].items())
        ]
    return [buckets[day] for day in sorted(buckets)]


def monthly_summaries(days, start, end):
    """Weight daily means by valid sample counts, including partially covered months."""
    buckets = {}
    counts = {}
    for row in days:
        month = row["day"][:7]
        if month not in buckets:
            buckets[month] = dict(
                empty_day(month),
                valid_days=0,
                period_from=row["day"],
                period_to=row["day"],
            )
            counts[month] = Counter()
        bucket = buckets[month]
        bucket["period_from"] = min(bucket["period_from"], row["day"])
        bucket["period_to"] = max(bucket["period_to"], row["day"])
        previous_count = bucket["valid_count"]
        for key in ("valid_count", "invalid_count", "excluded_count", "untimed_count"):
            bucket[key] += row[key]
        if row["valid_count"]:
            bucket["valid_days"] += 1
            if row["mean"] is not None:
                bucket["mean"] = (
                    row["mean"]
                    if bucket["mean"] is None
                    else bucket["mean"]
                    + (row["mean"] - bucket["mean"])
                    * row["valid_count"]
                    / (previous_count + row["valid_count"])
                )
                bucket["minimum"] = (
                    row["minimum"]
                    if bucket["minimum"] is None
                    else min(row["minimum"], bucket["minimum"])
                )
                bucket["maximum"] = (
                    row["maximum"]
                    if bucket["maximum"] is None
                    else max(row["maximum"], bucket["maximum"])
                )
            if bucket["first_time"] is None or row["first_time"] < bucket["first_time"]:
                bucket["first_time"] = row["first_time"]
            if bucket["last_time"] is None or row["last_time"] >= bucket["last_time"]:
                bucket["last_time"] = row["last_time"]
                bucket["last_value"] = row["last_value"]
        for value, n in row["value_counts"]:
            counts[month][dumps(value)] += n
        bucket["day_basis"] = (
            "mixed"
            if bucket["untimed_count"] and bucket["valid_count"]
            else "requested_day"
            if bucket["untimed_count"]
            else "measurement_time"
        )
    from calendar import monthrange

    for month, bucket in sorted(buckets.items()):
        year, number = map(int, month.split("-"))
        bucket["period_from"] = max(start.isoformat(), month + "-01")
        bucket["period_to"] = min(
            end.isoformat(), f"{month}-{monthrange(year, number)[1]:02d}"
        )
        bucket["value_counts"] = [
            [json.loads(key), n] for key, n in sorted(counts[month].items())
        ]
        yield bucket


class Summaries:
    """Read a consistent snapshot, then publish a reproducible cache if still current."""

    def __init__(self, db):
        self.db = db

    def daily(self, parameter, start, end, conn, stop=None):
        from .query import Queries

        check_stop(stop)
        method = summary_method(parameter)
        revision = conn.execute(
            "SELECT revision FROM dataset_state WHERE id=1"
        ).fetchone()[0]
        cache = conn.execute(
            "SELECT * FROM summary_cache WHERE parameter_key=%s", (parameter["key"],)
        ).fetchone()
        if (
            cache
            and cache["data_revision"] == revision
            and cache["algorithm_version"] == ALGORITHM_VERSION
            and cache["method"] == method
            and cache["from_day"] <= start.isoformat()
            and cache["to_day"] >= end.isoformat()
        ):
            result = []
            for row in conn.execute(
                "SELECT * FROM daily_summaries WHERE parameter_key=%s AND day BETWEEN %s AND %s ORDER BY day",
                (parameter["key"], start.isoformat(), end.isoformat()),
            ):
                check_stop(stop)
                item = dict(row)
                del item["parameter_key"]
                item["last_value"] = json.loads(item.pop("last_value_json"))
                item["value_counts"] = json.loads(item.pop("value_counts_json"))
                result.append(item)
            return result
        result = aggregate_days(
            Queries(self.db).rows(parameter, start, end, conn), parameter, stop
        )
        self.publish(parameter, start, end, revision, result, stop)
        return result

    def publish(self, parameter, start, end, revision, result, stop=None):
        # Readers/exporters remain available during an import. A busy writer or
        # newer revision only prevents caching, never changes the exported snapshot.
        with ExitStack() as stack:
            try:
                stack.enter_context(self.db.writer_lock(allow_nested=False))
            except RuntimeError:
                return
            try:
                with self.db.connect() as writer:
                    writer.execute(
                        "SELECT revision FROM dataset_state WHERE id=1 FOR UPDATE"
                    )
                    check_stop(stop)
                    if (
                        writer.execute(
                            "SELECT revision FROM dataset_state WHERE id=1"
                        ).fetchone()[0]
                        != revision
                    ):
                        return
                    writer.execute(
                        "DELETE FROM summary_cache WHERE parameter_key=%s",
                        (parameter["key"],),
                    )
                    writer.execute(
                        "INSERT INTO summary_cache VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (
                            parameter["key"],
                            summary_method(parameter),
                            ALGORITHM_VERSION,
                            revision,
                            start.isoformat(),
                            end.isoformat(),
                            utc_now(),
                        ),
                    )
                    for row in result:
                        check_stop(stop)
                        writer.execute(
                            "INSERT INTO daily_summaries VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                parameter["key"],
                                row["day"],
                                row["mean"],
                                row["minimum"],
                                row["maximum"],
                                dumps(row["last_value"]),
                                dumps(row["value_counts"]),
                                row["valid_count"],
                                row["invalid_count"],
                                row["excluded_count"],
                                row["untimed_count"],
                                row["first_time"],
                                row["last_time"],
                                row["day_basis"],
                            ),
                        )
            except (psycopg.errors.LockNotAvailable, psycopg.errors.DeadlockDetected):
                return
