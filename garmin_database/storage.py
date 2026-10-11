from hashlib import sha256
from pathlib import Path
import sqlite3
from .util import utc_now


class Database:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.path = self.root / "garmin.sqlite3"

    def connect(self, readonly=False):
        if readonly:
            conn = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
        else:
            self.root.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def initialize(self):
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("Baza pochodzi z nowszej wersji aplikacji")
            if version == 0:
                sql = (Path(__file__).parent / "resources/001_initial.sql").read_text(encoding="utf-8")
                try:
                    conn.executescript("BEGIN IMMEDIATE;\n" + sql)
                    conn.execute("INSERT INTO schema_migrations VALUES(1,?,?)", (utc_now(), sha256(sql.encode()).hexdigest()))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            conn.execute("CREATE INDEX IF NOT EXISTS catalog_representation ON field_catalog(representation,id)")

    def status(self):
        with self.connect(readonly=True) as conn:
            days = dict(conn.execute("SELECT download_status,count(*) FROM import_days GROUP BY download_status"))
            files = conn.execute("SELECT count(*),coalesce(sum(message_count),0),coalesce(sum(stored_field_count),0) FROM file_decodes WHERE is_active=1").fetchone()
            period = conn.execute("SELECT min(day),max(day),count(*),coalesce(sum(size_bytes),0) FROM archives").fetchone()
            unknown = conn.execute("SELECT count(*) FROM field_catalog WHERE semantics_status='unknown'").fetchone()[0]
            pending = conn.execute("SELECT count(*) FROM fit_files f WHERE NOT EXISTS(SELECT 1 FROM file_decodes x WHERE x.fit_file_id=f.id AND x.is_active=1 AND x.status='complete')").fetchone()[0]
        sizes = sum(p.stat().st_size for p in self.root.glob("garmin.sqlite3*"))
        return dict(days=days, first_day=period[0], last_day=period[1], archives=period[2], archive_bytes=period[3], database_bytes=sizes, files=files[0], messages=files[1], fields=files[2], unknown_variants=unknown, pending_files=pending)
