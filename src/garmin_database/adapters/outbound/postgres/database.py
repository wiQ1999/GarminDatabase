"""PostgreSQL storage shared by desktop and headless operations."""

import os
import threading
from contextlib import contextmanager, nullcontext
from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg import IsolationLevel

from garmin_database.adapters.outbound.filesystem.files import writer_lock
from garmin_database.application.errors import BusyError
from garmin_database.domain.time import utc_now

MIGRATIONS = ("001_initial.sql", "002_query_indexes.sql", "003_summaries.sql")


class Row(tuple):
    """A result row supports both column names and positional unpacking."""

    def __new__(cls, values, columns):
        row = super().__new__(cls, values)
        row.columns = columns
        return row

    def keys(self):
        return self.columns

    def __getitem__(self, key):
        if isinstance(key, str):
            key = self.columns.index(key)
        return super().__getitem__(key)


def result_rows(cursor):
    columns = tuple(column.name for column in cursor.description or ())
    return lambda values: Row(values, columns)


class Database:
    def __init__(self, data_dir, dsn=None):
        self.root = Path(data_dir)
        # Connection secrets belong in libpq's password file or environment,
        # never in logs, command-line arguments or settings.json.
        self.dsn = dsn or os.environ.get("GARMIN_DATABASE_DSN") or "dbname=garmin"
        self._writer = threading.local()

    def connect(self, readonly=False):
        conn = psycopg.connect(
            self.dsn,
            connect_timeout=10,
            application_name="GarminDatabase",
            row_factory=result_rows,
        )
        conn.isolation_level = (
            IsolationLevel.REPEATABLE_READ
            if readonly
            else IsolationLevel.READ_COMMITTED
        )
        conn.read_only = readonly
        return conn

    @contextmanager
    def writer_lock(self, *, allow_nested=True):
        """Serialize writers across hosts; also protect the local ZIP directory."""
        if getattr(self._writer, "active", False):
            if not allow_nested:
                raise BusyError()
            yield
            return
        with writer_lock(self.root), self.connect() as lock:
            lock.autocommit = True
            key = lock.execute(
                "SELECT hashtextextended(current_database() || ':' || current_schema() "
                "|| ':garmin_database.writer', 0)"
            ).fetchone()[0]
            if not lock.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()[
                0
            ]:
                raise BusyError()
            self._writer.active = True
            try:
                yield
            finally:
                self._writer.active = False
                lock.execute("SELECT pg_advisory_unlock(%s)", (key,))

    def schema_ready(self):
        with self.connect(readonly=True) as conn:
            return len(self._check_schema(conn)) == 3

    def _check_schema(self, conn):
        exists = conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0]
        migrations = (
            dict(conn.execute("SELECT version,sql_sha256 FROM schema_migrations"))
            if exists
            else {}
        )
        if any(version not in {1, 2, 3} for version in migrations):
            raise ValueError("Baza pochodzi z nowszej wersji aplikacji")
        for version, filename in enumerate(MIGRATIONS, 1):
            if version in migrations:
                source = (Path(__file__).parents[3] / "resources" / filename).read_text(
                    encoding="utf-8"
                )
                if sha256(source.encode()).hexdigest() != migrations[version]:
                    raise ValueError("Niezgodna suma kontrolna schematu PostgreSQL")
        return migrations

    def initialize(self):
        with self.writer_lock(), self.connect() as conn:
            migrations = self._check_schema(conn)
            for version, filename in enumerate(MIGRATIONS, 1):
                sql = (Path(__file__).parents[3] / "resources" / filename).read_text(
                    encoding="utf-8"
                )
                digest = sha256(sql.encode()).hexdigest()
                if version in migrations:
                    continue
                conn.execute(sql, prepare=False)
                conn.execute(
                    "INSERT INTO schema_migrations VALUES(%s,%s,%s)",
                    (version, utc_now(), digest),
                )
            # The database-wide writer lock proves no live importer owns these
            # markers. PostgreSQL rolled back any unfinished FIT transaction.
            conn.execute(
                "UPDATE decode_runs SET status='interrupted',finished_at=%s WHERE status='running'",
                (utc_now(),),
            )

    def status(self, conn=None):
        with (
            nullcontext(conn) if conn is not None else self.connect(readonly=True)
        ) as conn:
            days = dict(
                conn.execute(
                    "SELECT download_status,count(*) FROM import_days GROUP BY download_status"
                )
            )
            files = conn.execute(
                "SELECT count(*),coalesce(sum(message_count),0)::bigint,coalesce(sum(stored_field_count),0)::bigint FROM file_decodes WHERE is_active=1"
            ).fetchone()
            period = conn.execute(
                "SELECT min(day),max(day),count(*),coalesce(sum(size_bytes),0)::bigint FROM archives"
            ).fetchone()
            unknown = conn.execute(
                "SELECT count(*) FROM field_catalog WHERE semantics_status='unknown'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT count(*) FROM fit_files f WHERE NOT EXISTS(SELECT 1 FROM file_decodes x WHERE x.fit_file_id=f.id AND x.is_active=1 AND x.status='complete')"
            ).fetchone()[0]
            download_period = conn.execute(
                "SELECT min(day),max(day) FROM import_days WHERE download_status='downloaded'"
            ).fetchone()
            pending_days = conn.execute(
                "SELECT count(*) FROM import_days d WHERE download_status='downloaded' AND NOT EXISTS(SELECT 1 FROM archives a WHERE a.day=d.day)"
            ).fetchone()[0]
            size = conn.execute(
                "SELECT pg_database_size(current_database())"
            ).fetchone()[0]
        return dict(
            days=days,
            first_day=period[0],
            last_day=period[1],
            last_downloaded=download_period[1],
            archives=period[2],
            archive_bytes=period[3],
            database_bytes=size,
            files=files[0],
            messages=files[1],
            fields=files[2],
            unknown_variants=unknown,
            pending_files=pending,
            pending_days=pending_days,
        )
