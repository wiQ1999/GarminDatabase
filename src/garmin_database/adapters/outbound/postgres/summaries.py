import json
from contextlib import ExitStack

import psycopg

from garmin_database.domain.aggregation import (
    ALGORITHM_VERSION,
    aggregate_days,
    summary_method,
)
from garmin_database.domain.cancellation import check_stop
from garmin_database.domain.time import utc_now
from garmin_database.domain.values import dumps


class Summaries:
    """Read a consistent snapshot, then publish a reproducible cache if still current."""

    def __init__(self, db):
        self.db = db

    def daily(self, parameter, start, end, conn, stop=None, *, publish_cache=True):
        from garmin_database.adapters.outbound.postgres.queries import Queries

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
        if publish_cache:
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
