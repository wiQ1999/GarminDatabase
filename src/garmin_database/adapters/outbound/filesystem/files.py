import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from garmin_database.application.errors import BusyError


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
        replace_file(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def replace_file(source, target):
    """Keep explicit Windows ACLs when publishing updated configuration/state."""
    if os.name != "nt" or not Path(target).exists():
        os.replace(source, target)
        return
    import ctypes
    from ctypes import wintypes

    replace = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
    replace.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    replace.restype = wintypes.BOOL
    if not replace(
        str(Path(target).resolve()), str(Path(source).resolve()), None, 0, None, None
    ):
        raise OSError(
            ctypes.get_last_error(), "Nie można atomowo zapisać pliku Windows"
        )


def atomic_json(path, value):
    atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode(
            "utf-8"
        ),
    )


@contextmanager
def writer_lock(data_dir):
    with file_lock(Path(data_dir) / "writer.lock"):
        yield


@contextmanager
def file_lock(path):
    """An OS lock is released even when the process crashes; the file is metadata."""
    path = Path(path)
    root = path.parent
    root.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
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
            raise BusyError() from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
