"""Local, atomic collector records, available while PostgreSQL is offline."""

import getpass
import json
import logging
import os
from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from pathlib import Path

from garmin_database.adapters.outbound.filesystem.files import atomic_json, file_lock
from garmin_database.adapters.outbound.filesystem.settings_json import (
    Settings,
    application_dir,
)
from garmin_database.application.collector_models import (
    OUTCOMES,
    CollectorConfig,
    CollectorState,
)


def current_account():
    user = getpass.getuser()
    return os.environ.get("USERDOMAIN", ".") + "\\" + user if os.name == "nt" else user


def default_config_path(settings_path=None):
    if settings_path is not None:
        return Path(settings_path).resolve()
    if os.name == "nt":
        return application_dir() / "settings.json"
    return Path("/etc/garmin-database/settings.json")


class CollectorFiles:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path or default_config_path()).resolve()

    def defaults(self, data_dir=None, database_dsn="", *, settings_path=None):
        base = self.config_path.parent
        state = (
            base / "state"
            if os.name == "nt"
            else Path("/var/lib/garmin-database/collector/default")
        )
        config = CollectorConfig(
            data_dir=str(Path(data_dir).resolve()) if data_dir else str(state / "data"),
            state_dir=str(state),
            session_path=str(state / "auth/session.bin"),
            database_dsn=database_dsn,
            credential_path=str(base / "session-key.cred"),
            run_as=current_account(),
            settings_path=str(Path(settings_path).resolve()) if settings_path else "",
            download_from=None if settings_path else "2024-01-01",
        )
        return (
            self.for_account(config, windows_logon="interactive")
            if os.name == "nt"
            else config
        )

    def for_account(self, config, account=None, windows_logon=None):
        if account is None:
            account = (
                current_account() if windows_logon == "interactive" else config.run_as
            )
        changed = account.casefold() != config.run_as.casefold()
        windows_logon = windows_logon or self._account_mode(config, account, changed)
        if windows_logon == "interactive" and (
            os.name != "nt" or account.casefold() != current_account().casefold()
        ):
            raise ValueError("Tryb bez hasła wymaga bieżącego konta Windows")
        updates = dict(run_as=account, windows_logon=windows_logon, schema_version=2)
        if os.name == "nt":
            updates.update(
                self._windows_profile(config, account, windows_logon, changed)
            )
        result = replace(config, **updates)
        result.validate()
        return result

    def _account_mode(self, config, account, changed):
        if changed and os.name == "nt":
            return (
                "interactive"
                if account.casefold() == current_account().casefold()
                else "password"
            )
        return config.windows_logon

    def _windows_profile(self, config, account, mode, changed):
        state = Path(config.state_dir)
        if changed or config.windows_logon != mode:
            key = sha256(f"{account.casefold()}:{mode}".encode()).hexdigest()[:16]
            state = self.config_path.parent / "collectors" / key / "state"
        session = Path(config.session_path)
        if mode == "interactive":
            session = application_dir() / "auth/session.bin"
        elif changed or config.windows_logon != mode:
            session = state / "auth/session.bin"
        return dict(state_dir=str(state), session_path=str(session))

    def resolve_settings(self, config):
        """Resolve shared values once per run; explicit standalone overrides win."""
        if config.database_dsn is not None and config.download_from is not None:
            return config
        path = Path(config.settings_path)
        if not path.is_file():
            raise FileNotFoundError("Brak wspólnych ustawień aplikacji")
        settings = Settings.load(path)
        return replace(
            config,
            database_dsn=settings.database_dsn
            if config.database_dsn is None
            else config.database_dsn,
            download_from=settings.download_from
            if config.download_from is None
            else config.download_from,
        )

    def load_config(self):
        value = json.loads(self.config_path.read_text(encoding="utf-8"))
        if "data_dir" in value and "state_dir" in value:
            config = CollectorConfig(**value)  # Legacy standalone CLI file.
        else:
            settings = Settings.load(self.config_path)
            if settings.collector is None:
                legacy = self.config_path.with_name("collector.json")
                if legacy == self.config_path or not legacy.is_file():
                    raise FileNotFoundError("Brak konfiguracji kolektora")
                config = replace(
                    CollectorFiles(legacy).load_config(),
                    data_dir=settings.data_dir,
                    database_dsn=None,
                    download_from=None,
                    settings_path=str(self.config_path),
                )
                config.validate()
                return config
            config = CollectorConfig(
                **{
                    **settings.collector,
                    "data_dir": settings.data_dir,
                    "database_dsn": None,
                    "download_from": None,
                    "settings_path": str(self.config_path),
                }
            )
        config.validate()
        Settings(database_dsn=config.database_dsn or "").validate()
        return config

    def _uses_shared_settings(self, config):
        if self.config_path.name == "settings.json" or config.settings_path == str(
            self.config_path
        ):
            return True
        if not self.config_path.exists():
            return False
        document = json.loads(self.config_path.read_text(encoding="utf-8"))
        return isinstance(document, dict) and "state_dir" not in document

    def save_config(self, config):
        config.validate()
        Settings(database_dsn=config.database_dsn or "").validate()
        if not self._uses_shared_settings(config):
            atomic_json(self.config_path, asdict(config))
            return
        with file_lock(self.config_path.with_suffix(".lock")):
            settings = Settings.load(self.config_path)
            if not self.config_path.exists():
                settings.data_dir = config.data_dir
                settings.database_dsn = config.database_dsn or ""
                settings.download_from = config.download_from or "2024-01-01"
            value = asdict(config)
            for key in ("data_dir", "database_dsn", "download_from", "settings_path"):
                value.pop(key)
            settings.collector = value
            settings.validate()
            atomic_json(self.config_path, asdict(settings))

    def lock(self, config):
        return file_lock(Path(config.state_dir) / "collector.lock")

    def load_state(self, config):
        path = Path(config.state_dir) / "status.json"
        if not path.exists():
            return CollectorState()
        state = CollectorState(**json.loads(path.read_text(encoding="utf-8")))
        if state.outcome not in OUTCOMES:
            raise ValueError("Nieprawidłowy status kolektora")
        return state

    def save_state(self, config, state):
        atomic_json(Path(config.state_dir) / "status.json", asdict(state))

    def log(self, config, outcome):
        if outcome not in OUTCOMES | {"skipped_busy"}:
            raise ValueError("Nieprawidłowe zdarzenie kolektora")
        directory = Path(config.state_dir) / "logs"
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / "collector.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        try:
            handler.emit(
                logging.LogRecord(
                    "collector",
                    logging.INFO,
                    "",
                    0,
                    "%s %s",
                    (datetime.now(timezone.utc).isoformat(), outcome),
                    None,
                )
            )
        finally:
            handler.close()

    def logs(self, config):
        path = Path(config.state_dir) / "logs/collector.log"
        if not path.exists():
            return "Brak logów kolektora"
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 65536))
            return stream.read().decode("utf-8", errors="replace")
