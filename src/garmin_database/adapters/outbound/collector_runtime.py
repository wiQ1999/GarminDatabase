"""Runtime effects injected into the one-shot application use case."""

import ctypes
import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from garmin_database.application.errors import (
    LoginFailed,
    SessionRequired,
    SessionStorageError,
)


class CollectorRuntime:
    def __init__(self, files, config, synchronize):
        self.files, self.config, self.synchronize = files, config, synchronize

    def now(self):
        return datetime.now(timezone.utc)

    def boot_at(self):
        if os.name == "nt":
            tick = ctypes.windll.kernel32.GetTickCount64
            tick.restype = ctypes.c_ulonglong
            return self.now() - timedelta(milliseconds=tick())
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("btime "):
                return datetime.fromtimestamp(int(line.split()[1]), timezone.utc)
        raise RuntimeError("Nie można ustalić czasu startu systemu")

    def lock(self):
        return self.files.lock(self.config)

    def load(self):
        return self.files.load_state(self.config)

    def save(self, state):
        self.files.save_state(self.config, state)

    def log(self, outcome):
        self.files.log(self.config, outcome)

    def session_generation(self):
        path = Path(self.config.session_path)
        return sha256(path.read_bytes()).hexdigest() if path.exists() else None

    def classify(self, error):
        import psycopg

        if isinstance(error, psycopg.Error):
            return "database_error"
        if isinstance(error, SessionRequired):
            return "auth_required"
        if isinstance(error, (LoginFailed, SessionStorageError, OSError, ValueError)):
            return "session_error"
        return "interrupted"
