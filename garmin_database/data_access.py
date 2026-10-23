"""Wspólne reguły eksportu i MCP: docs/03-architecture.md, docs/05-export.md."""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Event, Thread

import psycopg

from .query import Queries
from .summaries import ALGORITHM_VERSION, MEAN_PARAMETERS, Summaries, summary_method

QUALITY_COLUMNS = [
    "valid_count",
    "invalid_count",
    "excluded_count",
    "untimed_count",
    "first_time",
    "last_time",
    "day_basis",
]
DAILY_COLUMNS = ["day", "mean", "minimum", "maximum", *QUALITY_COLUMNS]
PERIOD_COLUMNS = [
    "period_from",
    "period_to",
    "mean",
    "minimum",
    "maximum",
    *QUALITY_COLUMNS[:4],
    "valid_days",
    "requested_days",
    *QUALITY_COLUMNS[4:],
]
PRECISION = {
    "monitoring.heart_rate": 0,
    "hrv_value.value": 0,
    "respiration_rate.respiration_rate": 1,
    "spo2_data.reading_spo2": 1,
    "stress_level.stress_level_value": 1,
}


def aggregation(parameter, period):
    method = summary_method(parameter)
    return dict(
        method=method,
        period=period,
        algorithm_version=ALGORITHM_VERSION,
        weighting="valid_sample_count" if method == "sample_mean" else None,
        negative_stress_values_excluded=parameter["key"]
        == "stress_level.stress_level_value",
    )


def summary_columns(parameter, period):
    values = {
        "sample_mean": ["mean", "minimum", "maximum"],
        "value_counts": ["value_counts"],
        "last_observed": ["last_value"],
    }
    columns = ["day", *values[summary_method(parameter)], *QUALITY_COLUMNS]
    if period == "month":
        columns[0] = "month"
        columns += ["valid_days", "period_from", "period_to"]
    return columns


def select_parameters(catalog, allowed, requested):
    """Resolve canonical metadata; callers cannot inject catalog ids or scaling."""
    keys = list(requested)
    if not keys or len(set(keys)) != len(keys):
        raise ValueError("Wybierz co najmniej jeden niepowtarzający się parametr")
    available = {p["key"]: p for p in catalog if p["key"] in allowed}
    if any(key not in available for key in keys):
        raise ValueError(
            "Parametr nieznany lub wyłączony. Sprawdź katalog i Ustawienia."
        )
    return [available[key] for key in keys]


def read_daily(db, parameter, start, end, conn, stop=None, *, publish_cache=False):
    return Summaries(db).daily(
        parameter, start, end, conn, stop, publish_cache=publish_cache
    )


@dataclass
class DataSnapshot:
    db: object
    conn: object
    catalog: list
    revision: int
    policy_revision: str | None = None

    def select(self, settings, channel, requested):
        allowed = getattr(settings, channel + "_parameters") or []
        if channel == "mcp":
            allowed = set(allowed) & MEAN_PARAMETERS
        return select_parameters(self.catalog, allowed, requested)

    def daily(self, parameter, start, end, stop=None, *, publish_cache=False):
        return read_daily(
            self.db, parameter, start, end, self.conn, stop, publish_cache=publish_cache
        )


class DataAccess:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def snapshot(self, stop=None):
        with self.db.connect(readonly=True) as conn:
            finished = Event()

            def cancel_on_stop():
                while not finished.wait(0.05):
                    if stop.is_set():
                        try:
                            conn.cancel_safe(timeout=1)
                        except psycopg.Error:
                            pass
                        return

            watcher = None
            if stop is not None:
                deadline = getattr(stop, "deadline", None)
                if deadline is not None:
                    timeout_ms = max(1, int((deadline - time.monotonic()) * 1000))
                    conn.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (str(timeout_ms),),
                    )
                watcher = Thread(target=cancel_on_stop, daemon=True)
                watcher.start()
            try:
                version = conn.execute(
                    "SELECT max(version) FROM schema_migrations"
                ).fetchone()[0]
                if version != 3:
                    raise ValueError(
                        "Przygotuj obsługiwaną bazę w aplikacji GarminDatabase."
                    )
                revision = conn.execute(
                    "SELECT revision FROM dataset_state WHERE id=1"
                ).fetchone()[0]
                yield DataSnapshot(
                    self.db, conn, Queries(self.db).parameters(conn), revision
                )
            finally:
                finished.set()
                if watcher is not None:
                    watcher.join()
