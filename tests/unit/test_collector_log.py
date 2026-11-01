"""Actionable messages with explicit historical limits and no private text."""

from dataclasses import asdict

import pytest

from garmin_database.application.collector_log import (
    EVENT_MESSAGES,
    event_text,
    readable_log,
)
from garmin_database.application.collector_models import OUTCOMES
from garmin_database.application.dto import SyncSummary

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("outcome", sorted(OUTCOMES | {"skipped_busy"}))
def test_every_outcome_has_a_readable_legacy_message(outcome):
    assert outcome in EVENT_MESSAGES
    for timestamp in ("2026-11-01T11:00:00Z", "2026-11-01 12:00:00 +01:00"):
        original = timestamp + " " + outcome + "\r\n"
        result = readable_log(original)
        assert result == "2026-11-01 12:00:00 +01:00 " + event_text(outcome) + "\r\n"
        assert readable_log(result) == result


def test_actual_cause_counts_and_retry_instruction_are_separate_from_errors():
    summary = asdict(
        SyncSummary(
            "2024-01-01",
            "2026-11-01",
            10,
            processed_days=10,
            successful_days=7,
            unresolved_days=3,
        )
    )
    message = event_text("issues", summary=summary)
    assert "Dni z poprawnym importem: 7" in message
    assert "Nierozstrzygnięte dni (HTTP 404): 3" in message
    assert "Błędy pobierania (dni): 0" in message
    assert "Błędy importu FIT (pliki): 0" in message
    assert "nie potwierdza braku danych" in message and "24 godzin" in message
    assert "nie zawiera" not in message
    summary.update(download_errors=1, import_errors=2, archive_errors=4)
    message = event_text("issues", summary=summary)
    assert "Błędy pobierania (dni): 1" in message
    assert "Błędy importu FIT (pliki): 2" in message
    assert "Błędy archiwów (dni): 4" in message


def test_config_and_rate_limit_explain_next_action_in_warsaw():
    assert "Zainstaluj / zaktualizuj kolektor" in event_text("config_error")
    message = event_text("rate_limited", not_before="2026-07-15T12:00:00Z")
    assert "HTTP 429" in message and "2026-07-15 14:00:00 +02:00" in message


def test_only_safe_numeric_counters_reach_log_and_legacy_details_are_not_invented():
    summary = {
        "last_day_result": "private upstream secret",
        "token": "private token",
        "download_errors": "private response",
        "unresolved_days": -1,
        "import_errors": True,
        "archive_errors": float("inf"),
        "successful_days": 4,
    }
    message = event_text("issues", summary=summary)
    assert "Dni z poprawnym importem: 4" in message
    assert "private" not in message and "inf" not in message
    assert "Błędy" not in message and "HTTP 404):" not in message
    legacy = readable_log("2026-11-01 12:00:00 +01:00 issues\n")
    assert "Ten wpis nie zawiera szczegółowego podsumowania przyczyny" in legacy
    assert "Dni z poprawnym importem:" not in legacy
    assert (
        readable_log("partial\n2026-11-01 issues\nunknown event\n")
        == "partial\n2026-11-01 issues\nunknown event\n"
    )
