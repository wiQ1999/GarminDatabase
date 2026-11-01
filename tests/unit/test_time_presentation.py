"""One presentation timezone regardless of host timezone or historical offset."""

from datetime import datetime

import pytest

from garmin_database.application.time_presentation import (
    collector_log_text,
    collector_status_times,
    display_time,
    warsaw_iso,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "utc,local",
    [
        ("2026-01-15T23:30:00+00:00", "2026-01-16T00:30:00+01:00"),
        ("2026-07-15T23:30:00Z", "2026-07-16T01:30:00+02:00"),
        ("2026-03-29T00:30:00+00:00", "2026-03-29T01:30:00+01:00"),
        ("2026-03-29T01:30:00+00:00", "2026-03-29T03:30:00+02:00"),
        ("2026-10-25T00:30:00+00:00", "2026-10-25T02:30:00+02:00"),
        ("2026-10-25T01:30:00+00:00", "2026-10-25T02:30:00+01:00"),
        ("2026-07-15T15:30:00-07:00", "2026-07-16T00:30:00+02:00"),
    ],
)
def test_same_instant_in_status_log_and_json(utc, local, monkeypatch):
    monkeypatch.setenv("TZ", "Pacific/Honolulu")
    expected = local[:10] + " " + local[11:19] + " " + local[19:]
    assert warsaw_iso(utc) == local
    assert datetime.fromisoformat(utc) == datetime.fromisoformat(local)
    assert display_time(utc) == expected
    assert collector_log_text(utc + " success\n") == expected + " success\n"
    assert (
        collector_log_text(collector_log_text(utc + " success\n"))
        == expected + " success\n"
    )


def test_precision_nulls_and_unknown_zone_are_not_guessed():
    assert (
        warsaw_iso("2026-07-15T00:00:00.123456Z") == "2026-07-15T02:00:00.123456+02:00"
    )
    assert warsaw_iso(None) is None
    assert display_time(None) == "brak"
    for value in ("broken", "2026-07-15T12:00:00", "2026-07-15"):
        with pytest.raises(ValueError):
            warsaw_iso(value)
        assert display_time(value) == "nieprawidłowy czas"
    assert (
        collector_log_text("incomplete\n2026-07-15 success\n")
        == "incomplete\n2026-07-15 success\n"
    )


def test_cli_projection_does_not_modify_runtime_state():
    original = {
        "next_run": "2026-07-15T00:00:00Z",
        "state": {
            "started_at": "2026-01-15T00:00:00Z",
            "last_success": None,
            "summary": {"retry_not_before": "2026-07-15T00:00:00Z"},
        },
        "config_revision": "unchanged",
        "session_present": True,
    }
    result = collector_status_times(original)
    assert result["next_run"] == "2026-07-15T02:00:00+02:00"
    assert result["state"]["started_at"] == "2026-01-15T01:00:00+01:00"
    assert result["state"]["summary"]["retry_not_before"].endswith("+02:00")
    assert result["state"]["last_success"] is None
    assert original["state"]["started_at"].endswith("Z")
