"""Collector configuration and durable results, independent of operating system."""

import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from json import dumps
from pathlib import Path

from garmin_database.domain.schedule import Schedule


@dataclass
class CollectorConfig:
    data_dir: str
    state_dir: str
    session_path: str
    database_dsn: str | None = ""
    instance: str = "default"
    enabled: bool = False
    interval_minutes: int = 120
    anchor_at: str = "2024-01-01T00:00:00Z"
    run_as: str = ""
    credential_path: str = ""
    status_reader: str = ""
    schema_version: int = 2
    settings_path: str = ""
    download_from: str | None = "2024-01-01"
    windows_logon: str = "password"

    @property
    def schedule(self):
        return Schedule(self.interval_minutes, self.anchor_at)

    def validate(self):
        if type(self.schema_version) is not int or self.schema_version not in (1, 2):
            raise ValueError("Nieobsługiwana wersja konfiguracji kolektora")
        if type(self.enabled) is not bool:
            raise ValueError("Nieprawidłowe włączenie kolektora")
        if not isinstance(self.instance, str) or not re.fullmatch(
            r"[a-z][a-z0-9_-]{0,39}", self.instance
        ):
            raise ValueError("Nieprawidłowy identyfikator kolektora")
        if self.windows_logon not in ("interactive", "password"):
            raise ValueError("Nieprawidłowy tryb konta Windows")
        self._validate_paths()
        self._validate_shared_settings()
        self._validate_accounts()
        self.schedule

    def _validate_paths(self):
        for path in (self.data_dir, self.state_dir, self.session_path):
            _validate_absolute_path(path)
        if not isinstance(self.credential_path, str) or (
            self.credential_path and not Path(self.credential_path).is_absolute()
        ):
            raise ValueError("Ścieżka poświadczenia musi być bezwzględna")

    def _validate_shared_settings(self):
        if self.database_dsn is not None and not isinstance(self.database_dsn, str):
            raise ValueError("Nieprawidłowe połączenie PostgreSQL")
        if self.settings_path and not Path(self.settings_path).is_absolute():
            raise ValueError("Ścieżka ustawień aplikacji musi być bezwzględna")
        if self.database_dsn is None or self.download_from is None:
            if not self.settings_path:
                raise ValueError("Wskaż ustawienia aplikacji dla wspólnej konfiguracji")
        if self.download_from is not None:
            from datetime import date

            date.fromisoformat(self.download_from)

    def _validate_accounts(self):
        for value in (self.run_as, self.status_reader):
            if not isinstance(value, str) or any(c in value for c in '\r\n\x00"'):
                raise ValueError("Nieprawidłowe konto kolektora")

    @property
    def revision(self):
        return sha256(dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def _validate_absolute_path(path):
    if (
        not isinstance(path, str)
        or not Path(path).is_absolute()
        or Path(path).parent == Path(path)
        or any(c in path for c in "\r\n\x00")
    ):
        raise ValueError("Ścieżki kolektora muszą być bezwzględne")


@dataclass
class CollectorState:
    claimed_slot: str | None = None
    claimed_revision: str | None = None
    outcome: str = "never_run"
    started_at: str | None = None
    finished_at: str | None = None
    last_success: str | None = None
    next_run: str | None = None
    not_before: str | None = None
    auth_generation: str | None = None
    auth_required: bool = False
    summary: dict | None = None
    applied_revision: str | None = None


OUTCOMES = frozenset(
    {
        "never_run",
        "running",
        "success",
        "issues",
        "auth_required",
        "access_denied",
        "rate_limited",
        "database_error",
        "network_error",
        "cancelled",
        "config_error",
        "session_error",
        "interrupted",
    }
)
