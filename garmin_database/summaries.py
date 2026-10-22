"""Podsumowania dzienne i miesięczne: docs/05-export.md, docs/10-sqlite-schema.md."""

import json
import math
import sqlite3
from collections import Counter
from contextlib import ExitStack
from datetime import datetime
from zoneinfo import ZoneInfo

from .fit import dumps
from .util import check_stop, utc_now, writer_lock

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


def merge_numeric(bucket, row, previous_count):
    if row["mean"] is None:
        return
    if bucket["mean"] is None:
        bucket["mean"] = row["mean"]
    else:
        bucket["mean"] += (
            (row["mean"] - bucket["mean"])
            * row["valid_count"]
            / (previous_count + row["valid_count"])
        )
    for key, combine in (("minimum", min), ("maximum", max)):
        bucket[key] = (
            row[key] if bucket[key] is None else combine(bucket[key], row[key])
        )


def merge_day(bucket, row, counts):
    previous = bucket["valid_count"]
    for key in ("valid_count", "invalid_count", "excluded_count", "untimed_count"):
        bucket[key] += row[key]
    if row["valid_count"]:
        bucket["valid_days"] += 1
        merge_numeric(bucket, row, previous)
        if bucket["first_time"] is None or row["first_time"] < bucket["first_time"]:
            bucket["first_time"] = row["first_time"]
        if bucket["last_time"] is None or row["last_time"] >= bucket["last_time"]:
            bucket["last_time"] = row["last_time"]
            bucket["last_value"] = row["last_value"]
    for value, n in row["value_counts"]:
        counts[dumps(value)] += n
    bucket["day_basis"] = merged_day_basis(bucket)


def merged_day_basis(bucket):
    if not bucket["untimed_count"]:
        return "measurement_time"
    return "mixed" if bucket["valid_count"] else "requested_day"


def period_summary(days, start, end, stop=None):
    """Merge unrounded daily observations; never average days with equal weights."""
    bucket = dict(
        empty_day(""),
        valid_days=0,
        period_from=start.isoformat(),
        period_to=end.isoformat(),
        requested_days=(end - start).days + 1,
    )
    counts = Counter()
    for row in days:
        check_stop(stop)
        merge_day(bucket, row, counts)
    bucket["value_counts"] = [[json.loads(k), n] for k, n in sorted(counts.items())]
    return bucket


def monthly_summaries(days, start, end):
    """Use the same weighted reducer as arbitrary period reads."""
    from calendar import monthrange
    from datetime import date
    from itertools import groupby

    for month, rows in groupby(
        sorted(days, key=lambda r: r["day"]), key=lambda r: r["day"][:7]
    ):
        year, number = map(int, month.split("-"))
        begin = max(start, date(year, number, 1))
        finish = min(end, date(year, number, monthrange(year, number)[1]))
        yield dict(period_summary(rows, begin, finish), day=month)


class Summaries:
    """Read a consistent snapshot, then publish a reproducible cache if still current."""

    def __init__(self, db):
        self.db = db

    def daily(self, parameter, start, end, conn, stop=None, *, publish_cache=True):
        from .query import Queries

        check_stop(stop)
        method = summary_method(parameter)
        revision = conn.execute(
            "SELECT revision FROM dataset_state WHERE id=1"
        ).fetchone()[0]
        cache = conn.execute(
            "SELECT * FROM summary_cache WHERE parameter_key=?", (parameter["key"],)
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
                "SELECT * FROM daily_summaries WHERE parameter_key=? AND day BETWEEN ? AND ? ORDER BY day",
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
        if publish_cache:
            self.publish(parameter, start, end, revision, result, stop)
        return result

    def publish(self, parameter, start, end, revision, result, stop=None):
        # Readers/exporters remain available during an import. A busy writer or
        # newer revision only prevents caching, never changes the exported snapshot.
        with ExitStack() as stack:
            try:
                stack.enter_context(writer_lock(self.db.root))
            except RuntimeError:
                return
            try:
                with self.db.connect() as writer:
                    writer.execute("BEGIN IMMEDIATE")
                    check_stop(stop)
                    if (
                        writer.execute(
                            "SELECT revision FROM dataset_state WHERE id=1"
                        ).fetchone()[0]
                        != revision
                    ):
                        return
                    writer.execute(
                        "DELETE FROM summary_cache WHERE parameter_key=?",
                        (parameter["key"],),
                    )
                    writer.execute(
                        "INSERT INTO summary_cache VALUES(?,?,?,?,?,?,?)",
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
                            "INSERT INTO daily_summaries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
            except sqlite3.OperationalError as error:
                if error.sqlite_errorcode not in {
                    sqlite3.SQLITE_BUSY,
                    sqlite3.SQLITE_LOCKED,
                }:
                    raise
