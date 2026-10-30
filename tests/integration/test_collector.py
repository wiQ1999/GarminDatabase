"""Shared synchronization and writer exclusion against disposable PostgreSQL."""

import threading
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.application.errors import BusyError
from garmin_database.bootstrap.dependencies import Services, create_sync
from tests.support.fixtures import fit_bytes

pytestmark = pytest.mark.integration


def test_gui_services_open_under_another_process_writer_without_recovery(tmp_path):
    db = Database(tmp_path / "writer")
    db.initialize()
    with db.connect() as conn:
        # Use an existing real row to avoid synthetic running states without owners.
        before = conn.execute("SELECT count(*) FROM decode_runs").fetchone()[0]
    with db.writer_lock():
        services = Services(Settings(data_dir=str(tmp_path / "reader")))
        assert services.status()["archives"] == 0
        with pytest.raises(BusyError):
            services.sync(
                date(2024, 1, 1),
                date(2024, 1, 1),
                threading.Event(),
                lambda *a: None,
                local_only=True,
            )
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM decode_runs").fetchone()[0] == before


def test_sync_exposes_persistent_cooldown_without_parsing_progress(tmp_path):
    error = RuntimeError("private upstream response")
    error.response = SimpleNamespace(status_code=429, headers={"Retry-After": "14400"})
    source = Mock()
    source.download_health_snapshot.side_effect = error
    sync = create_sync(Database(tmp_path), source, delay=0)
    result = sync.run_summary(date(2024, 1, 1), date(2024, 1, 1), threading.Event())
    assert result.halt_reason == "rate_limited"
    assert result.http_status == 429
    assert result.retry_not_before
    assert source.download_health_snapshot.call_count == 1
    assert "private" not in str(result)


def test_session_storage_failure_stops_without_retries(tmp_path):
    from garmin_database.application.errors import SessionStorageError

    source = Mock()
    source.download_health_snapshot.side_effect = SessionStorageError()
    sync = create_sync(Database(tmp_path), source, delay=0)
    result = sync.run_summary(date(2024, 1, 1), date(2024, 1, 3), threading.Event())
    assert source.download_health_snapshot.call_count == 1
    assert result.halt_reason == "session_error"
    assert result.http_status is None
    assert "zabezpieczenia sesji" in result.last_day_result


def test_collector_runs_the_real_incremental_import_and_busy_is_only_logged(
    tmp_path, monkeypatch
):
    from datetime import datetime, timedelta, timezone
    from io import BytesIO
    from zipfile import ZipFile

    from garmin_database.adapters.outbound import collector_runtime
    from garmin_database.adapters.outbound.garmin import client
    from garmin_database.application.use_cases.run_collector import RunCollector
    from garmin_database.bootstrap.collector import synchronize
    from garmin_database.domain import time

    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("synthetic.fit", fit_bytes())
    source = Mock()
    source.download_health_snapshot.return_value = buffer.getvalue()
    monkeypatch.setattr(client, "GarminSource", lambda store: source)
    monkeypatch.setattr(time, "today", lambda: date(2024, 1, 1))
    files = CollectorFiles(tmp_path / "collector.json")
    config = replace(
        files.defaults(tmp_path / "data"),
        state_dir=str(tmp_path / "state"),
        session_path=str(tmp_path / "auth/session.bin"),
        enabled=True,
    )
    state = files.load_state(config)
    state.applied_revision = config.revision
    files.save_state(config, state)
    runtime = collector_runtime.CollectorRuntime(files, config, synchronize)
    now = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)
    runtime.now = lambda: now
    runtime.boot_at = lambda: now - timedelta(days=1)
    runner = RunCollector(runtime)
    assert runner.run(config, threading.Event()) == "success"
    db = Database(config.data_dir)
    first = db.status()
    assert first["messages"] > 0
    now += timedelta(hours=2)
    assert runner.run(config, threading.Event()) == "success"
    assert db.status()["messages"] == first["messages"]
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM decode_runs").fetchone()[0] == 1
    now += timedelta(hours=2)
    with Database(tmp_path / "other-host").writer_lock():
        assert runner.run(config, threading.Event()) == "skipped_busy"
    assert files.load_state(config).outcome == "success"
    assert "skipped_busy" in files.logs(config)
    assert source.download_health_snapshot.call_count == 2
    assert not list(tmp_path.rglob("*.zip"))
