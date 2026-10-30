"""Observable scheduling, retries and persistence without private Garmin data."""

from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
from unittest.mock import Mock

import pytest

from garmin_database.application.collector_models import CollectorConfig, CollectorState
from garmin_database.application.dto import SyncSummary
from garmin_database.application.errors import BusyError
from garmin_database.application.use_cases.run_collector import RunCollector
from garmin_database.domain.cancellation import Cancelled
from garmin_database.domain.schedule import Schedule, instant

pytestmark = pytest.mark.unit
NOW = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)


@pytest.fixture
def config(tmp_path):
    return CollectorConfig(
        str(tmp_path / "data"),
        str(tmp_path / "state"),
        str(tmp_path / "auth/session.bin"),
        enabled=True,
    )


class Runtime:
    def __init__(self, config):
        self.time = NOW
        self.boot = NOW - timedelta(days=1)
        self.state = CollectorState(applied_revision=config.revision)
        self.generation = None
        self.events = []
        self.synchronize = Mock(return_value=SyncSummary("2024-01-01", "2026-10-30", 1))

    def now(self):
        return self.time

    def boot_at(self):
        return self.boot

    def lock(self):
        return nullcontext()

    def load(self):
        return deepcopy(self.state)

    def save(self, state):
        self.state = deepcopy(state)

    def log(self, outcome):
        self.events.append(outcome)

    def session_generation(self):
        return self.generation

    def classify(self, error):
        return "database_error"


@pytest.mark.parametrize("interval", [15, 17, 90, 120, 1441])
def test_fixed_slots_do_not_drift_at_midnight_or_dst(interval):
    schedule = Schedule(interval)
    for date in (
        "2026-03-29T01:00:00Z",
        "2026-10-25T01:00:00Z",
        "2026-10-30T23:59:59Z",
    ):
        now = instant(date)
        slot = schedule.slot(now)
        next_run = schedule.next_after(now)
        assert slot <= now < next_run
        assert next_run - slot == timedelta(minutes=interval)
        assert schedule.next_after(slot) == next_run


@pytest.mark.parametrize("interval", [0, 14, -15, True, 15.5, "120"])
def test_invalid_intervals(interval):
    with pytest.raises(ValueError):
        Schedule(interval)


@pytest.mark.parametrize(
    "anchor", ["2026-01-01T00:00:00", "2026-01-01T00:00:01Z", "invalid"]
)
def test_invalid_anchor(anchor):
    with pytest.raises(ValueError):
        Schedule(120, anchor)


def test_future_anchor_and_restart_never_catch_up():
    schedule = Schedule(120, "2026-11-01T00:00:00Z")
    assert schedule.slot(NOW) is None
    assert schedule.next_after(NOW) == instant(schedule.anchor_at)
    assert schedule.due(NOW, NOW - timedelta(days=1)) is None
    schedule = Schedule()
    assert schedule.due(NOW, NOW) is None
    assert schedule.due(NOW + timedelta(minutes=1), NOW - timedelta(days=1)) is None


def test_one_slot_is_claimed_once_and_restart_does_not_repeat(config):
    runtime = Runtime(config)
    runner = RunCollector(runtime)
    assert runner.run(config, Event()) == "success"
    assert RunCollector(runtime).run(config, Event()) == "already_claimed"
    assert runtime.synchronize.call_count == 1
    assert runtime.state.next_run == (NOW + timedelta(hours=2)).isoformat()
    assert runtime.state.last_success == NOW.isoformat()


@pytest.mark.parametrize("mode", ["disabled", "not_due", "restart"])
def test_no_sql_or_session_access_outside_slot(config, mode):
    runtime = Runtime(config)
    if mode == "disabled":
        config.enabled = False
    elif mode == "not_due":
        runtime.time += timedelta(minutes=30)
    else:
        runtime.boot = NOW
    runtime.session_generation = Mock(side_effect=AssertionError("secret accessed"))
    runtime.load = Mock(side_effect=AssertionError("state accessed"))
    assert RunCollector(runtime).run(config, Event()) in {"disabled", "not_due"}
    runtime.synchronize.assert_not_called()
    assert runtime.events == []


def test_configuration_must_be_applied_before_scheduled_work(config):
    runtime = Runtime(config)
    runtime.state.applied_revision = None
    assert RunCollector(runtime).run(config, Event()) == "config_error"
    runtime.synchronize.assert_not_called()


@pytest.mark.parametrize("where", ["instance", "writer"])
def test_busy_only_logs_and_keeps_last_real_result(config, where):
    runtime = Runtime(config)
    runtime.state.outcome = "success"
    runtime.state.last_success = "2026-10-29T00:00:00Z"
    if where == "writer":
        runtime.synchronize.side_effect = BusyError()
    else:

        @contextmanager
        def busy():
            raise BusyError()
            yield

        runtime.lock = busy
    assert RunCollector(runtime).run(config, Event()) == "skipped_busy"
    assert runtime.events == ["skipped_busy"]
    assert runtime.state.outcome == "success"
    assert runtime.state.last_success == "2026-10-29T00:00:00Z"


def test_auth_pause_survives_recreation_and_resumes_only_after_new_session(config):
    runtime = Runtime(config)
    runtime.synchronize.return_value.halt_reason = "auth_required"
    assert RunCollector(runtime).run(config, Event()) == "auth_required"
    runtime.time += timedelta(hours=2)
    assert RunCollector(runtime).run(config, Event()) == "auth_required"
    assert runtime.synchronize.call_count == 1
    runtime.time += timedelta(hours=2)
    runtime.generation = "new encrypted session"
    runtime.synchronize.return_value.halt_reason = None
    assert RunCollector(runtime).run(config, Event()) == "success"
    assert not runtime.state.auth_required


def test_retry_after_survives_runs_and_uses_first_normal_eligible_slot(config):
    runtime = Runtime(config)
    result = runtime.synchronize.return_value
    result.halt_reason = "rate_limited"
    result.retry_not_before = (NOW + timedelta(hours=3)).isoformat()
    assert RunCollector(runtime).run(config, Event()) == "rate_limited"
    runtime.time += timedelta(hours=2)
    assert RunCollector(runtime).run(config, Event()) == "rate_limited"
    assert runtime.synchronize.call_count == 1
    runtime.time += timedelta(hours=2)
    result.halt_reason = None
    result.retry_not_before = None
    assert RunCollector(runtime).run(config, Event()) == "success"


@pytest.mark.parametrize(
    "error,expected",
    [(Cancelled(), "cancelled"), (RuntimeError("private"), "database_error")],
)
def test_errors_have_safe_durable_outcomes(config, error, expected):
    runtime = Runtime(config)
    runtime.synchronize.side_effect = error
    assert RunCollector(runtime).run(config, Event()) == expected
    assert runtime.state.finished_at == NOW.isoformat()
    assert "private" not in str(runtime.state)


def test_long_operation_skips_slots_instead_of_drifting(config):
    runtime = Runtime(config)

    def sync(*args):
        runtime.time += timedelta(hours=5, minutes=3)
        return SyncSummary("2024-01-01", "2026-10-30", 1, unresolved_days=1)

    runtime.synchronize.side_effect = sync
    assert RunCollector(runtime).run(config, Event()) == "issues"
    assert runtime.state.next_run == (NOW + timedelta(hours=6)).isoformat()
    assert RunCollector(runtime).run(config, Event()) == "not_due"


def test_manual_execution_does_not_require_registered_schedule(config):
    runtime = Runtime(config)
    config.enabled = False
    runtime.state.applied_revision = None
    assert RunCollector(runtime).run(config, Event(), scheduled=False) == "success"
    assert runtime.state.next_run is None


def test_session_access_error_has_durable_status(config):
    runtime = Runtime(config)
    runtime.session_generation = Mock(side_effect=PermissionError("private"))
    assert RunCollector(runtime).run(config, Event()) == "session_error"
    assert runtime.state.finished_at == NOW.isoformat()
    runtime.synchronize.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"instance": "../x"},
        {"data_dir": "relative"},
        {"schema_version": True},
        {"schema_version": 2},
        {"enabled": 1},
        {"run_as": "bad\nuser"},
        {"credential_path": "relative"},
        {"database_dsn": None},
    ],
)
def test_config_rejects_ambiguous_or_unsafe_values(config, changes):
    with pytest.raises(ValueError):
        replace(config, **changes).validate()
