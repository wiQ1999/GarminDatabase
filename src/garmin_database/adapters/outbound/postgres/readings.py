"""Wspólne reguły eksportu i MCP: docs/03-architecture.md, docs/05-export.md."""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from threading import Event, Thread

import psycopg

from garmin_database.adapters.outbound.postgres.queries import Queries
from garmin_database.adapters.outbound.postgres.summaries import Summaries
from garmin_database.application.ports import ReadFailure
from garmin_database.application.read_models import select_parameters
from garmin_database.domain.aggregation import (
    MEAN_PARAMETERS,
)
from garmin_database.domain.values import dumps


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

    @property
    def identity(self):
        return [
            sha256(dumps(self.conn.info.get_parameters()).encode()).hexdigest(),
            list(
                self.conn.execute(
                    "SELECT d.oid,n.oid FROM pg_database d,pg_namespace n WHERE d.datname=current_database() AND n.nspname=current_schema()"
                ).fetchone()
            ),
            self.revision,
        ]

    def coverage(self, start, end):
        return Queries(self.db).coverage(start, end, self.conn)

    def rows(self, parameter, start, end):
        return Queries(self.db).rows(parameter, start, end, self.conn)

    def availability(self, parameter):
        marks = ",".join("%s" for _ in parameter["ids"])
        return self.conn.execute(
            f"SELECT min(m.time_unix_ms),max(m.time_unix_ms) FROM fit_fields f JOIN fit_messages m ON m.id=f.message_id JOIN file_decodes d ON d.id=m.file_decode_id WHERE f.resolved_catalog_id IN ({marks}) AND d.is_active=1",
            parameter["ids"],
        ).fetchone()


class DataAccess:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def snapshot(self, stop=None, *, include_catalog=True):
        try:
            with self._snapshot(stop, include_catalog=include_catalog) as value:
                yield value
        except psycopg.Error:
            raise ReadFailure("Nie można odczytać bazy") from None

    @contextmanager
    def _snapshot(self, stop=None, *, include_catalog=True):
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
                    self.db,
                    conn,
                    Queries(self.db).parameters(conn) if include_catalog else [],
                    revision,
                )
            finally:
                finished.set()
                if watcher is not None:
                    watcher.join()
