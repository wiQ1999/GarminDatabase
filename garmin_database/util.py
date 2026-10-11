from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo


class Cancelled(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def yesterday():
    return datetime.now(ZoneInfo("Europe/Warsaw")).date() - timedelta(days=1)


def dates(start, end):
    if start > end or end > yesterday():
        raise ValueError("Zakres musi być uporządkowany i kończyć się najpóźniej wczoraj")
    for n in range((end - start).days + 1):
        yield start + timedelta(days=n)


def check_stop(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()


def atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8"))


@contextmanager
def writer_lock(data_dir):
    """An OS lock is released even when the process crashes; the file is metadata."""
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "writer.lock").open("a+b") as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Inny proces zapisuje dane") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
