"""Local, atomic collector records, available while PostgreSQL is offline."""

import getpass
import json
import logging
import os
from dataclasses import asdict, replace
from datetime import datetime, timezone
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
        return Path(settings_path).resolve().parent / "collector.json"
    if os.name == "nt":
        return application_dir() / "collector.json"
    return Path("/etc/garmin-database/collector.json")


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
        return CollectorConfig(
            data_dir=str(Path(data_dir).resolve()) if data_dir else str(state / "data"),
            state_dir=str(state),
            session_path=str(state / "auth/session.bin"),
            database_dsn=database_dsn,
            credential_path=str(base / "session-key.cred"),
            run_as=current_account(),
            settings_path=str(Path(settings_path).resolve()) if settings_path else "",
            download_from=None if settings_path else "2024-01-01",
        )

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
        config = CollectorConfig(
            **json.loads(self.config_path.read_text(encoding="utf-8"))
        )
        config.validate()
        Settings(database_dsn=config.database_dsn or "").validate()
        return config

    def save_config(self, config):
        config.validate()
        Settings(database_dsn=config.database_dsn or "").validate()
        atomic_json(self.config_path, asdict(config))

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
