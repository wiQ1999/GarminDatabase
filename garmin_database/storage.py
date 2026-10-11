import sqlite3
from hashlib import sha256
from pathlib import Path

from .util import utc_now


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class Database:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.path = self.root / "garmin.sqlite3"

    def connect(self, readonly=False):
        if readonly:
            conn = sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=ro",
                uri=True,
                timeout=30,
                factory=Connection,
            )
        else:
            self.root.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=30, factory=Connection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def initialize(self):
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > 2:
                raise ValueError("Baza pochodzi z nowszej wersji aplikacji")
            if version == 0:
                sql = (Path(__file__).parent / "resources/001_initial.sql").read_text(
                    encoding="utf-8"
                )
                try:
                    conn.executescript("BEGIN IMMEDIATE;\n" + sql)
                    conn.execute(
                        "INSERT INTO schema_migrations VALUES(1,?,?)",
                        (utc_now(), sha256(sql.encode()).hexdigest()),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            if version < 2:
                sql = (
                    Path(__file__).parent / "resources/002_query_indexes.sql"
                ).read_text(encoding="utf-8")
                try:
                    conn.executescript("BEGIN IMMEDIATE;\n" + sql)
                    conn.execute(
                        "INSERT INTO schema_migrations VALUES(2,?,?)",
                        (utc_now(), sha256(sql.encode()).hexdigest()),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            # Called under the writer lock: any surviving running marker belongs
            # to a crashed process. SQLite already rolled back its transaction.
            conn.execute(
                "UPDATE decode_runs SET status='interrupted',finished_at=? WHERE status='running'",
                (utc_now(),),
            )

    def status(self):
        with self.connect(readonly=True) as conn:
            days = dict(
                conn.execute(
                    "SELECT download_status,count(*) FROM import_days GROUP BY download_status"
                )
            )
            files = conn.execute(
                "SELECT count(*),coalesce(sum(message_count),0),coalesce(sum(stored_field_count),0) FROM file_decodes WHERE is_active=1"
            ).fetchone()
            period = conn.execute(
                "SELECT min(day),max(day),count(*),coalesce(sum(size_bytes),0) FROM archives"
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
        sizes = sum(p.stat().st_size for p in self.root.glob("garmin.sqlite3*"))
        return dict(
            days=days,
            first_day=period[0],
            last_day=period[1],
            last_downloaded=download_period[1],
            archives=period[2],
            archive_bytes=period[3],
            database_bytes=sizes,
            files=files[0],
            messages=files[1],
            fields=files[2],
            unknown_variants=unknown,
            pending_files=pending,
            pending_days=pending_days,
        )
