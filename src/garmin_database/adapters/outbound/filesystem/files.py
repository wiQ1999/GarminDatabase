import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


def open_location(location):
    """Hand a user-selected directory or HTTPS link to the desktop shell."""
    if os.name == "nt":
        os.startfile(str(location))
    else:
        subprocess.Popen(
            ["open" if sys.platform == "darwin" else "xdg-open", str(location)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def open_directory(path):
    path = Path(path).resolve()
    if not path.is_dir():
        raise FileNotFoundError("Folder nie istnieje")
    open_location(path)


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
    atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode(
            "utf-8"
        ),
    )


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
