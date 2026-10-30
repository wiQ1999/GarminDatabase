from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.application.ports import ReadFailure
from garmin_database.application.settings import Settings
from garmin_database.application.use_cases.read_health import AccessError, MCPData
from garmin_database.domain import cancellation


def test_deadline_includes_external_cancellation_and_monotonic_budget(monkeypatch):
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 100)
    event = Event()
    stop = cancellation.DeadlineStop(event, 10)
    assert not stop.is_set()
    event.set()
    assert stop.is_set()
    event.clear()
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 110)
    assert stop.is_set()


def test_deadline_supports_reads_without_external_event(monkeypatch):
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 100)
    stop = cancellation.DeadlineStop(None, 10)
    assert not stop.is_set()
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 111)
    assert stop.is_set()


def test_server_timeout_before_client_deadline_remains_a_timeout(tmp_path):
    @contextmanager
    def snapshot(budget):
        assert not budget.is_set()
        raise ReadFailure("safe", reason="timeout")
        yield

    store = Mock()
    store.load.return_value = Settings(
        data_dir=str(tmp_path),
        settings_version=2,
        export_parameters=[],
        mcp_enabled=True,
    )
    service = MCPData(
        settings_store=store,
        readings_factory=lambda _: SimpleNamespace(snapshot=snapshot),
    )
    with pytest.raises(AccessError, match="Przekroczono"):
        service.catalog()
