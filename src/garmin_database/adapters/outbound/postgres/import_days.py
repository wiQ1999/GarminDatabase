"""Persistence of download progress, under the shared writer lock."""

from datetime import date

from garmin_database.domain.time import utc_now


class ImportDays:
    def __init__(self, db):
        self.db = db

    def writer_lock(self):
        return self.db.writer_lock()

    def initialize(self):
        self.db.initialize()

    def restore_days(self, days):
        with self.db.connect() as conn:
            for day, row in days.items():
                date.fromisoformat(day)
                status = row.get("status", "pending")
                if status not in {
                    "downloaded",
                    "empty_zip",
                    "not_found_unverified",
                    "failed",
                    "local_invalid",
                }:
                    continue
                conn.execute(
                    "INSERT INTO import_days(day,download_status,attempts,checked_at,http_status,error_type) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        day,
                        status,
                        row.get("attempts", 0),
                        row.get("checked_at"),
                        row.get("http_status"),
                        row.get("error_type"),
                    ),
                )

    def day(self, day):
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM import_days WHERE day=%s", (day,)
            ).fetchone()

    def local_invalid(self, day, error_type):
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO import_days(day,download_status,error_type) VALUES(%s,'local_invalid',%s) ON CONFLICT(day) DO UPDATE SET download_status='local_invalid',error_type=excluded.error_type",
                (day, error_type),
            )

    def attempt(self, day):
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO import_days(day,download_status,attempts) VALUES(%s,'pending',1) ON CONFLICT(day) DO UPDATE SET download_status='pending',attempts=import_days.attempts+1",
                (day,),
            )

    def failed(self, day, status, error_type):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE import_days SET download_status=%s,checked_at=%s,http_status=%s,error_type=%s WHERE day=%s",
                (
                    "not_found_unverified" if status == 404 else "failed",
                    utc_now(),
                    status,
                    error_type,
                    day,
                ),
            )

    def cancel_attempt(self, day):
        """Refund an attempt cancelled before the source was called."""
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE import_days SET attempts=greatest(attempts-1,0) WHERE day=%s",
                (day,),
            )

    def download_days(self, start, end, refresh_all=False):
        from garmin_database.domain.time import dates

        requested = list(dates(start, end))
        if refresh_all:
            return requested
        with self.db.connect(readonly=True) as conn:
            last = conn.execute(
                "SELECT max(day) FROM archives WHERE day BETWEEN %s AND %s",
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]
            pending = {
                r[0]
                for r in conn.execute(
                    """SELECT day FROM import_days d
                WHERE day BETWEEN %s AND %s AND (download_status IN ('pending','failed','local_invalid','not_found_unverified')
                OR download_status='downloaded' AND (NOT EXISTS(SELECT 1 FROM archives a WHERE a.day=d.day)
                OR EXISTS(SELECT 1 FROM archives a JOIN archive_entries e ON e.archive_id=a.id WHERE a.day=d.day
                AND NOT EXISTS(SELECT 1 FROM file_decodes f WHERE f.fit_file_id=e.fit_file_id AND f.is_active=1 AND f.status='complete'))))""",
                    (start.isoformat(), end.isoformat()),
                )
            }
        return [
            day
            for day in requested
            if last is None or day.isoformat() >= last or day.isoformat() in pending
        ]
