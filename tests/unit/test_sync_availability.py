from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.outbound.filesystem.archives import Archives
from garmin_database.application.use_cases.synchronize import Sync
from tests.support.fixtures import zip_bytes
from tests.unit.test_sync_pipeline import START, Repository

pytestmark = pytest.mark.unit
NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "hours,skipped", [(0, True), (23, True), (24, False), (48, False), (-1, True)]
)
def test_unresolved_404_has_a_bounded_recheck_delay(hours, skipped):
    sync = Sync(None, None, None)
    sync.clock = lambda: NOW
    old = dict(
        download_status="not_found_unverified",
        checked_at=(NOW - timedelta(hours=hours)).isoformat(),
    )
    assert sync.already_checked(old, "2026-10-31") is skipped


@pytest.mark.parametrize("checked", [None, "", "invalid", "2026-10-01T00:00:00"])
def test_legacy_or_invalid_check_time_does_not_trigger_unbounded_retries(checked):
    sync = Sync(None, None, None)
    sync.clock = lambda: NOW
    assert sync.already_checked(
        dict(download_status="not_found_unverified", checked_at=checked), "2026-10-31"
    )
    sync.refresh_all = True
    assert not sync.already_checked(
        dict(download_status="not_found_unverified", checked_at=checked), "2026-10-31"
    )


def test_confirmed_absence_stays_confirmed():
    sync = Sync(None, None, None)
    sync.clock = lambda: NOW
    assert sync.already_checked(
        dict(
            download_status="no_data_confirmed",
            checked_at=(NOW - timedelta(days=2)).isoformat(),
        ),
        "2026-10-31",
    )


@pytest.mark.parametrize("status", ["not_found_unverified", "no_data_confirmed"])
@pytest.mark.parametrize(
    "checked",
    [None, "invalid", NOW.isoformat(), (NOW + timedelta(hours=1)).isoformat()],
)
def test_current_day_is_never_skipped_because_of_previous_absence(status, checked):
    sync = Sync(None, None, None, clock=lambda: NOW)
    assert not sync.already_checked(
        dict(download_status=status, checked_at=checked), "2026-11-01"
    )


@pytest.mark.parametrize(
    ("clock", "current", "previous"),
    [
        ("2026-11-01T23:00:00+00:00", "2026-11-02", "2026-11-01"),
        ("2026-07-01T22:30:00+00:00", "2026-07-02", "2026-07-01"),
        ("2026-10-25T00:30:00+00:00", "2026-10-25", "2026-10-24"),
        ("2026-10-25T01:30:00+00:00", "2026-10-25", "2026-10-24"),
    ],
)
def test_current_day_uses_warsaw_calendar_including_dst(clock, current, previous):
    now = datetime.fromisoformat(clock)
    sync = Sync(None, None, None, clock=lambda: now)
    old = dict(download_status="not_found_unverified", checked_at=now.isoformat())
    assert not sync.already_checked(old, current)
    assert sync.already_checked(old, previous)


@pytest.mark.parametrize("status", ["not_found_unverified", "no_data_confirmed"])
def test_current_day_returns_to_historical_rules_at_warsaw_midnight(status):
    now = datetime(2026, 11, 1, 22, 59, 59, tzinfo=timezone.utc)
    sync = Sync(None, None, None, clock=lambda: now)
    old = dict(download_status=status, checked_at=now.isoformat())
    assert not sync.already_checked(old, "2026-11-01")
    now += timedelta(seconds=1)
    assert sync.already_checked(old, "2026-11-01")
    assert not sync.already_checked(old, "2026-11-02")


def test_late_available_archive_is_downloaded_instead_of_skipped(tmp_path):
    repository = Repository()
    repository.rows[START.isoformat()] = dict(
        download_status="not_found_unverified",
        checked_at=(NOW - timedelta(days=2)).isoformat(),
    )
    download = Mock(return_value=zip_bytes())
    sync = Sync(
        repository,
        Archives(tmp_path),
        SimpleNamespace(archive=lambda *a, **kw: 0),
        SimpleNamespace(download_health_snapshot=download),
        delay=0,
    )
    sync.clock = lambda: NOW
    summary = sync.run_summary(START, START, Event())
    assert summary.successful_days == 1
    assert summary.unresolved_days == 0
    download.assert_called_once_with(START.isoformat())
