import json

import pytest
from psycopg import OperationalError

from garmin_database.adapters.outbound.diagnostics.startup import (
    startup_code,
    startup_failure,
)
from garmin_database.adapters.outbound.filesystem.settings_json import Settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "text,code",
    [
        ("no password supplied", "PASSWORD_MISSING"),
        ("password authentication failed", "PASSWORD_REJECTED"),
        ("could not create socket", "LOCAL_NETWORK"),
        ("Permission denied", "ACCESS_DENIED"),
        ("Connection refused", "SERVER_UNAVAILABLE"),
        ("timeout expired", "TIMEOUT"),
        ("could not translate host name", "HOST_NOT_FOUND"),
        ("unknown reason", "CONNECTION"),
    ],
)
def test_startup_connection_categories(text, code):
    assert startup_code(OperationalError(text + " private-secret")) == code


def test_startup_log_never_contains_raw_error_or_connection_options(tmp_path):
    settings = Settings(
        database_dsn="host=private-host dbname=private-database user=private-user "
        + f"passfile='{tmp_path.as_posix()}/missing'"
    )
    message = startup_failure(OperationalError("private-secret"), settings)
    path = tmp_path / "appdata/GarminDatabase/logs/startup-failure.json"
    payload = path.read_text(encoding="utf-8")
    assert not any(
        value in message + payload
        for value in (
            "private-secret",
            "private-host",
            "private-database",
            "private-user",
        )
    )
    access = json.loads(payload)["password_file_access"]
    assert access["readable"] is False
    assert access["error_type"] == "FileNotFoundError"


def test_startup_error_survives_unwritable_diagnostics(tmp_path, monkeypatch):
    from garmin_database.adapters.outbound.diagnostics import startup as startup

    def fail(*args):
        raise PermissionError("private-secret")

    monkeypatch.setattr(startup, "atomic_json", fail)
    message = startup_failure(ValueError("private-secret"))
    assert "STARTUP/APPLICATION" in message and "private-secret" not in message


@pytest.mark.parametrize(
    "status,code", [("28P01", "PASSWORD_REJECTED"), ("3D000", "DATABASE_MISSING")]
)
def test_startup_structured_status(status, code):
    from psycopg import errors

    error = errors.lookup(status)("private-secret")
    assert startup_code(error) == code


def test_startup_password_file_access_does_not_read_secret(tmp_path):
    from garmin_database.adapters.outbound.diagnostics.startup import (
        password_file_access,
    )

    path = tmp_path / "pgpass.conf"
    path.write_text("private-secret", encoding="utf-8")
    result = password_file_access(
        Settings(database_dsn=f"passfile='{path.as_posix()}'")
    )
    assert result == {"readable": True, "standard_location": False}


def test_startup_password_access_reports_only_error_codes(tmp_path, monkeypatch):
    from pathlib import Path

    from garmin_database.adapters.outbound.diagnostics.startup import (
        password_file_access,
    )

    def denied(*args, **kwargs):
        raise PermissionError(13, "private-secret")

    monkeypatch.setattr(Path, "open", denied)
    result = password_file_access(Settings())
    assert result["error_type"] == "PermissionError" and result["errno"] == 13
    assert "private-secret" not in json.dumps(result)
