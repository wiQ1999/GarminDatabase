import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
from zipfile import ZipFile

from .auth import SessionRequired
from .importer import Importer
from .util import Cancelled, atomic_write, check_stop, dates, utc_now


def error_status(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status is not None:
            return int(status)
        match = re.search(
            r"(?:API Error|HTTP|status[=: ]+)\s*(\d{3})", str(error), re.I
        )
        if match:
            return int(match.group(1))
        name = type(error).__name__
        if "Authentication" in name:
            return 401
        if "TooManyRequests" in name:
            return 429
        error = error.__cause__ or error.__context__
    return None


def validate_zip(payload):
    with ZipFile(BytesIO(payload)) as z:
        if z.testzip() is not None:
            raise ValueError("Nieprawidłowy CRC ZIP")
        return bool([x for x in z.infolist() if not x.is_dir()])


def retry_after(error, fallback, now=None):
    """Respect the server delay without persisting response headers or bodies."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        headers = getattr(getattr(error, "response", None), "headers", {}) or {}
        value = headers.get("Retry-After")
        if value is not None:
            try:
                delay = (
                    int(value)
                    if str(value).isdigit()
                    else (
                        parsedate_to_datetime(str(value))
                        - (now or datetime.now(timezone.utc))
                    ).total_seconds()
                )
                return max(fallback, delay)
            except (TypeError, ValueError, OverflowError):
                pass
        error = error.__cause__ or error.__context__
    return fallback


class Sync:
    def __init__(self, db, source=None, delay=3.0):
        self.db = db
        self.source = source
        self.delay = delay

    def restore_manifest(self):
        """Import only prior metadata, not a second permanent measurement copy."""
        path = self.db.root / "collection.json"
        if not path.exists():
            return
        manifest = json.loads(path.read_text(encoding="utf-8"))
        with self.db.connect() as c:
            for day, row in manifest.get("days", {}).items():
                from datetime import date

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
                c.execute(
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

    def run(
        self, start, end, stop, progress=lambda *a: None, local_only=False, force=False
    ):
        requested = list(dates(start, end))
        with self.db.writer_lock():
            self.db.initialize()
            self.restore_manifest()
            raw = self.db.root / "raw"
            raw.mkdir(exist_ok=True)
            importer = Importer(self.db)
            errors = 0
            consecutive = 0
            for index, day in enumerate(requested, 1):
                check_stop(stop)
                text = day.isoformat()
                path = raw / f"{text}.zip"
                progress(text, "dzień", index, len(requested))
                with self.db.connect() as c:
                    old = c.execute(
                        "SELECT * FROM import_days WHERE day=%s", (text,)
                    ).fetchone()
                if path.exists():
                    try:
                        errors += importer.archive(path, stop, progress, force)
                    except Cancelled:
                        raise
                    except Exception as error:
                        with self.db.connect() as c:
                            c.execute(
                                "INSERT INTO import_days(day,download_status,error_type) VALUES(%s,'local_invalid',%s) ON CONFLICT(day) DO UPDATE SET download_status='local_invalid',error_type=excluded.error_type",
                                (text, type(error).__name__),
                            )
                        progress(
                            text,
                            "Nieprawidłowe archiwum lokalne",
                            index,
                            len(requested),
                        )
                        errors += 1
                        break
                    continue
                if local_only:
                    continue
                if old and old["download_status"] in {
                    "not_found_unverified",
                    "no_data_confirmed",
                }:
                    continue
                next_wait = self.delay
                for attempt in range(3):
                    if stop.wait(next_wait):
                        raise Cancelled()
                    with self.db.connect() as c:
                        c.execute(
                            "INSERT INTO import_days(day,download_status,attempts) VALUES(%s,'pending',1) ON CONFLICT(day) DO UPDATE SET attempts=import_days.attempts+1",
                            (text,),
                        )
                    try:
                        payload = self.source.download_health_snapshot(text)
                        validate_zip(payload)
                    except Cancelled:
                        raise
                    except Exception as error:
                        status = error_status(error)
                        with self.db.connect() as c:
                            c.execute(
                                "UPDATE import_days SET download_status=%s,checked_at=%s,http_status=%s,error_type=%s WHERE day=%s",
                                (
                                    "not_found_unverified"
                                    if status == 404
                                    else "failed",
                                    utc_now(),
                                    status,
                                    type(error).__name__,
                                    text,
                                ),
                            )
                        progress(
                            text,
                            str(error)
                            if isinstance(error, SessionRequired)
                            else f"Błąd {status or type(error).__name__}",
                            index,
                            len(requested),
                        )
                        if isinstance(error, SessionRequired) or status in {
                            401,
                            403,
                            429,
                        }:
                            return errors + 1
                        if status == 404 or status is not None and status < 500:
                            break
                        if attempt == 2:
                            break
                        next_wait = retry_after(
                            error, max(self.delay, 2 ** (attempt + 1))
                        )
                    else:
                        # Disk errors must never trigger another API request.
                        if path.exists():
                            raise FileExistsError("Archiwum już istnieje")
                        atomic_write(path, payload)
                        errors += importer.archive(
                            path, stop, progress, origin="webapi"
                        )
                        consecutive = 0
                        break
                else:
                    continue
                if not path.exists():
                    errors += 1
                    consecutive = 0 if status == 404 else consecutive + 1
                    if consecutive >= 5:
                        break
            return errors
