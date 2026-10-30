"""Real encryption, atomic local records and process locks with synthetic tokens."""

import json
import os
from dataclasses import replace
from unittest.mock import Mock

import pytest
from cryptography.exceptions import InvalidTag

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.security import linux_session
from garmin_database.application.collector_models import CollectorState
from garmin_database.application.errors import BusyError

pytestmark = pytest.mark.unit


@pytest.fixture
def files(tmp_path):
    return CollectorFiles(tmp_path / "config.json")


def test_config_and_state_roundtrip_without_touching_database(files, tmp_path):
    config = files.defaults(tmp_path / "data", "host=db.example.invalid dbname=garmin")
    config = replace(config, state_dir=str(tmp_path / "state"))
    files.save_config(config)
    assert files.load_config() == config
    assert files.load_state(config).outcome == "never_run"
    state = CollectorState(
        outcome="auth_required", auth_required=True, applied_revision=config.revision
    )
    files.save_state(config, state)
    assert files.load_state(config) == state
    assert config.revision == files.load_config().revision
    assert not list(tmp_path.rglob("*.sqlite*"))
    with files.lock(config):
        with pytest.raises(BusyError):
            with files.lock(config):
                pass
    with files.lock(config):
        pass


def test_configuration_rejects_dsn_password_and_does_not_write(files, tmp_path):
    config = files.defaults(tmp_path, "postgresql://user:private-secret@localhost/db")
    with pytest.raises(ValueError) as error:
        files.save_config(config)
    assert "private-secret" not in str(error.value)
    assert not files.config_path.exists()


def test_corrupt_state_fails_closed_and_log_is_allowlisted(files, tmp_path):
    config = replace(files.defaults(tmp_path), state_dir=str(tmp_path / "state"))
    assert files.logs(config) == "Brak logów kolektora"
    files.log(config, "skipped_busy")
    assert "skipped_busy" in files.logs(config)
    with pytest.raises(ValueError):
        files.log(config, "private-secret")
    path = tmp_path / "state/status.json"
    path.write_text(json.dumps({"outcome": "private-error"}))
    with pytest.raises(ValueError):
        files.load_state(config)


@pytest.mark.skipif(os.name == "nt", reason="Linux credential file permissions")
def test_session_ciphertext_is_authenticated_and_key_is_not_saved(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(b"x" * 32)
    key.chmod(0o600)
    store = linux_session.SessionStore(tmp_path / "auth/session.bin", key_path=key)
    with store.lock():
        store.save("synthetic-token-data")
    assert store.load() == "synthetic-token-data"
    assert b"synthetic-token-data" not in store.path.read_bytes()
    assert b"x" * 32 not in store.path.read_bytes()
    original = store.path.read_bytes()
    store.path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(InvalidTag):
        store.load()
    store.path.write_bytes(original)
    key.write_bytes(b"y" * 32)
    with pytest.raises(InvalidTag):
        store.load()
    store.clear()
    assert not store.path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Linux credential file permissions")
def test_missing_key_and_invalid_formats_do_not_fallback_to_plaintext(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    store = linux_session.SessionStore(tmp_path / "session.bin")
    with pytest.raises(RuntimeError):
        store.save("synthetic-token")
    assert not store.path.exists()
    store.path.write_bytes(b"plaintext-token")
    with pytest.raises(ValueError):
        store.load()
    key = tmp_path / "key"
    key.write_bytes(b"short")
    key.chmod(0o600)
    store.key_path = key
    with pytest.raises(ValueError):
        store.save("synthetic-token")
    key.write_bytes(b"z" * 32)
    key.chmod(0o604)
    with pytest.raises(PermissionError):
        store.save("synthetic-token")


def test_systemd_key_is_passed_over_pipe_and_never_overwrites(tmp_path, monkeypatch):
    path = tmp_path / "secret.cred"

    def encrypt(command, **kwargs):
        assert len(kwargs["input"]) == 32
        assert not any(isinstance(item, bytes) for item in command)
        path.write_bytes(b"synthetic-sealed-credential")
        return Mock(returncode=0)

    monkeypatch.setattr(linux_session.subprocess, "run", encrypt)
    linux_session.prepare_key(path)
    assert path.read_bytes() == b"synthetic-sealed-credential"
    with pytest.raises(FileExistsError):
        linux_session.prepare_key(path)
    path.unlink()
    monkeypatch.setattr(
        linux_session.subprocess, "run", lambda *a, **k: Mock(returncode=1)
    )
    with pytest.raises(RuntimeError):
        linux_session.prepare_key(path)


def test_corrupt_session_never_reaches_network_or_exposes_exception():
    from garmin_database.adapters.outbound.garmin.client import GarminSource
    from garmin_database.application.errors import SessionStorageError

    store, api = Mock(), Mock()
    store.load.side_effect = ValueError("synthetic-private-token HTTP 403")
    source = GarminSource(store, factory=lambda **_: api)
    with pytest.raises(SessionStorageError) as error:
        source.download_health_snapshot("2026-10-30")
    assert "synthetic-private" not in str(error.value)
    api.login.assert_not_called()
    api.download_health_snapshot.assert_not_called()
