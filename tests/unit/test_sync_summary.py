import json
from datetime import date, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.inbound.cli.commands import run_command
from garmin_database.adapters.outbound.filesystem.archives import Archives
from garmin_database.application.dto import SyncSummary
from garmin_database.application.sync_messages import sync_heading, sync_summary_text
from garmin_database.application.use_cases.synchronize import Sync
from tests.support.fixtures import zip_bytes
from tests.unit.test_sync_pipeline import END, START, Repository

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("unresolved", [0, 1])
def test_cli_prints_explicit_summary_and_preserves_exit_code_and_final_status_json(
    capsys, unresolved
):
    result = SyncSummary(
        START.isoformat(),
        END.isoformat(),
        3,
        processed_days=3,
        successful_days=3 - unresolved,
        unresolved_days=unresolved,
        first_unresolved=START.isoformat(),
        last_unresolved=START.isoformat(),
    )
    services = SimpleNamespace(
        sync=Mock(return_value=result), status=lambda: {"fields": 0}
    )
    code = run_command(
        SimpleNamespace(command="sync", start=START, end=END), services, None, Event()
    )
    output = capsys.readouterr().out
    assert code == (2 if unresolved else 0)
    assert "Podsumowanie całej operacji" in output
    assert json.loads(output.splitlines()[-1]) == {"fields": 0}
    assert services.sync.call_args.kwargs["detailed"] is True


def test_historical_404s_do_not_mark_successful_last_day_as_failed():
    begin, end = date(2024, 1, 1), date(2026, 10, 24)
    unresolved = {(begin + timedelta(days=n)).isoformat() for n in range(170)} - {
        "2024-02-17"
    }
    repository = Repository()
    repository.rows = {
        day: {"download_status": "not_found_unverified"} for day in unresolved
    }
    archives = SimpleNamespace(
        restore_manifest=lambda: {},
        exists=lambda day: day not in unresolved,
        path=lambda day: Path(day + ".zip"),
    )
    events = []
    sync = Sync(repository, archives, SimpleNamespace(archive=lambda *a, **kw: 0))
    result = sync.run_summary(begin, end, Event(), lambda *args: events.append(args))
    assert result.requested_days == result.processed_days == 1028
    assert result.successful_days == 859 and result.unresolved_days == 169
    assert result.error_count == 0 and result.issue_count == 169
    assert (
        result.first_unresolved == "2024-01-01"
        and result.last_unresolved == "2024-06-18"
    )
    assert (
        result.last_day == "2026-10-24"
        and result.last_day_result == "import zakończony bez błędów"
    )
    assert events[-1] == (
        "2026-10-24",
        "Wynik dnia: import zakończony bez błędów",
        1028,
        1028,
    )
    text = sync_summary_text(result)
    assert "Zakres całej operacji: 2024-01-01 — 2026-10-24" in text
    assert "Dni nierozstrzygnięte (HTTP 404): 169" in text
    assert "Błędy importu FIT (pliki): 0" in text
    assert "HTTP 404 nie potwierdza braku danych" in text
    assert "z błędami" not in sync_heading(result)
    assert (
        sync.run(begin, end, Event()) == 169
    )  # legacy numerical result remains compatible


def test_new_and_previously_unresolved_404s_have_same_summary_without_redownload(
    tmp_path,
):
    repository, archives = Repository(), Archives(tmp_path)
    calls = []

    def download(day):
        calls.append(day)
        if day == START.isoformat():
            error = RuntimeError("private response")
            error.response = SimpleNamespace(status_code=404)
            raise error
        return zip_bytes()

    service = Sync(
        repository,
        archives,
        SimpleNamespace(archive=lambda *a, **kw: 0),
        SimpleNamespace(download_health_snapshot=download),
        delay=0,
    )
    for _ in range(2):
        result = service.run_summary(START, END, Event())
        assert result.unresolved_days == 1 and result.successful_days == 2
        assert (
            result.download_errors == result.import_errors == result.archive_errors == 0
        )
        assert "private" not in sync_summary_text(result)
    assert len(calls) == 3 and calls.count(START.isoformat()) == 1


def test_fit_errors_are_counted_as_files_and_do_not_poison_next_day(tmp_path):
    archives = SimpleNamespace(
        restore_manifest=lambda: {},
        exists=lambda day: True,
        path=lambda day: Path(day + ".zip"),
    )

    def import_zip(path, *args):
        return 2 if path.stem == START.isoformat() else 0

    result = Sync(
        Repository(), archives, SimpleNamespace(archive=import_zip)
    ).run_summary(START, END, Event())
    assert (
        result.import_errors == 2
        and result.download_errors
        == result.unresolved_days
        == result.archive_errors
        == 0
    )
    assert (
        result.successful_days == 2
        and result.last_day_result == "import zakończony bez błędów"
    )
    assert "zakończono z błędami" in sync_heading(result)


@pytest.mark.parametrize("status", [401, 403, 429])
def test_fatal_network_error_reports_incomplete_operation(tmp_path, status):
    def download(day):
        error = RuntimeError("private response")
        error.response = SimpleNamespace(status_code=status)
        raise error

    result = Sync(
        Repository(),
        Archives(tmp_path),
        SimpleNamespace(archive=lambda *a, **kw: 0),
        SimpleNamespace(download_health_snapshot=download),
        delay=0,
    ).run_summary(START, END, Event())
    assert result.processed_days == 1 and result.requested_days == 3
    assert (
        result.download_errors == 1
        and result.import_errors == result.unresolved_days == 0
    )
    assert result.halted and "przerwano przed końcem zakresu" in sync_heading(result)
    assert "Obsłużono dni: 1/3" in sync_summary_text(result)


def test_local_archive_failure_is_separate_from_fit_failure():
    archives = SimpleNamespace(
        restore_manifest=lambda: {},
        exists=lambda day: True,
        path=lambda day: Path(day + ".zip"),
    )

    def fail(*args):
        raise ValueError("private location")

    result = Sync(Repository(), archives, SimpleNamespace(archive=fail)).run_summary(
        START, END, Event(), local_only=True
    )
    assert (
        result.archive_errors == 1
        and result.import_errors == result.download_errors == 0
    )
    assert result.halted and result.processed_days == 1


def test_local_missing_archives_are_skipped_without_claiming_import_success(tmp_path):
    result = Sync(
        Repository(), Archives(tmp_path), SimpleNamespace(archive=lambda *a: 0)
    ).run_summary(START, END, Event(), local_only=True)
    assert (
        result.skipped_days == 3
        and result.successful_days == 0
        and result.issue_count == 0
    )
    assert "Pominięte dni bez lokalnego ZIP: 3" in sync_summary_text(result)


def test_confirmed_absence_is_not_a_404_or_successful_import(tmp_path):
    repository = Repository()
    repository.rows = {
        (START + timedelta(days=i)).isoformat(): {
            "download_status": "no_data_confirmed"
        }
        for i in range(3)
    }
    result = Sync(
        repository, Archives(tmp_path), SimpleNamespace(archive=lambda *a: 0)
    ).run_summary(START, END, Event())
    assert (
        result.confirmed_no_data_days == 3
        and result.successful_days == result.unresolved_days == result.issue_count == 0
    )
