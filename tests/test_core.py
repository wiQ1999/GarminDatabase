import json
from datetime import timedelta

import pytest

from garmin_database.auth import SessionStore
from garmin_database.settings import Settings
from garmin_database.storage import Database
from garmin_database.util import atomic_json, dates, writer_lock, yesterday

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "field,value",
    [
        ("recent_days", 0),
        ("delay", -1),
        ("parameters", [1]),
        ("history_from", "bad"),
        ("data_dir", ""),
        ("summary_period", "year"),
    ],
)
def test_invalid_settings(field, value):
    settings = Settings()
    setattr(settings, field, value)
    with pytest.raises(ValueError):
        settings.validate()


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(recent_days=14, parameters=["heart_rate"])
    settings.save(path)
    assert Settings.load(path) == settings
    assert "password" not in path.read_text()


def test_settings_defaults(tmp_path):
    assert Settings.load(tmp_path / "absent").recent_days == 90


def test_legacy_export_settings_ignore_full_samples(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"full_samples": True, "export_dir": "exports/current"}))
    settings = Settings.load(path)
    assert settings.summary_period == "day" and settings.export_dir == "exports/current"
    settings.save(path)
    assert "full_samples" not in path.read_text()


@pytest.mark.parametrize(
    "start,end",
    [
        (yesterday() + timedelta(days=1), yesterday() + timedelta(days=1)),
        (yesterday(), yesterday() - timedelta(days=1)),
    ],
)
def test_invalid_ranges(start, end):
    with pytest.raises(ValueError):
        list(dates(start, end))


def test_ranges():
    assert len(list(dates(yesterday() - timedelta(days=2), yesterday()))) == 3


def test_lock_and_release(tmp_path):
    with writer_lock(tmp_path):
        with pytest.raises(RuntimeError):
            with writer_lock(tmp_path):
                pass
    with writer_lock(tmp_path):
        pass


def test_atomic_json_failure_keeps_previous(tmp_path):
    p = tmp_path / "value.json"
    atomic_json(p, {"ok": 1})
    with pytest.raises(ValueError):
        atomic_json(p, {"x": float("nan")})
    assert json.loads(p.read_text()) == {"ok": 1}


@pytest.mark.integration
def test_database_initialization_idempotent(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    db.initialize()
    assert db.status()["fields"] == 0
    with db.connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 3


@pytest.mark.integration
def test_encrypted_session(tmp_path):
    store = SessionStore(tmp_path / "session.bin")
    store.save('{"token":"secret"}')
    assert b"secret" not in store.path.read_bytes()
    assert store.load() == '{"token":"secret"}'
    store.clear()
    assert not store.path.exists()
