"""Automation settings stay responsive and do not silently register tasks."""

import os
import threading
from dataclasses import replace
from datetime import datetime

import pytest
from PySide6.QtCore import QTimer

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from tests.ui.test_ui import ready, window

pytestmark = pytest.mark.ui


@pytest.mark.parametrize(
    ("anchor", "display"),
    [
        ("2024-01-01T00:00:00+00:00", "2024-01-01 01:00:00 +01:00"),
        ("2026-07-15T00:00:00+00:00", "2026-07-15 02:00:00 +02:00"),
        ("2026-10-25T00:30:00+00:00", "2026-10-25 02:30:00 +02:00"),
        ("2026-10-25T01:30:00+00:00", "2026-10-25 02:30:00 +01:00"),
    ],
)
def test_schedule_anchor_displays_warsaw_and_survives_save(
    qtbot, tmp_path, anchor, display
):
    w = window(qtbot, tmp_path)
    files = CollectorFiles(tmp_path / "settings.json")
    config = replace(files.defaults(tmp_path), anchor_at=anchor)
    files.save_config(config)
    panel = w.collector_panel
    panel._loaded(config)
    assert panel.anchor.text() == display
    panel.buttons["save"].click()
    ready(qtbot, w)
    assert datetime.fromisoformat(
        files.load_config().anchor_at
    ) == datetime.fromisoformat(anchor)


def test_save_collector_config_is_separate_from_apply_and_gui_preferences(
    qtbot, tmp_path
):
    w = window(qtbot, tmp_path)
    panel = w.collector_panel
    path = tmp_path / "settings.json"
    assert panel.interval.minimum() == 15 and panel.interval.value() == 120
    panel.enabled.setChecked(True)
    panel.windows_logon.setCurrentIndex(panel.windows_logon.findData("password"))
    panel.account.setText("garmin")
    panel.buttons["save"].click()
    ready(qtbot, w)
    config = CollectorFiles(path).load_config()
    assert config.enabled and config.run_as == "garmin"
    assert config.data_dir == w.settings.data_dir
    assert config.database_dsn is None and config.download_from is None
    assert config.settings_path == str(tmp_path / "settings.json")
    assert "Zainstaluj" in panel.message.text()
    w.save_settings()
    ready(qtbot, w)
    assert w.settings.refresh_seconds == 15
    panel.interval.setValue(30)
    panel.buttons["load"].click()
    ready(qtbot, w)
    assert panel.interval.value() == 120


def test_defaults_share_configuration_directory_and_current_account(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    panel = w.collector_panel
    assert panel.path.text() == str(tmp_path / "settings.json")
    assert not hasattr(w, "config_directory")
    assert w.open_config_button.text() == "Otwórz folder konfiguracji"
    assert panel.account.text() == w.services.current_account()
    assert not hasattr(panel, "dsn")
    assert not hasattr(panel, "data_dir")


def test_missing_config_shows_actionable_message(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    for action in ("load",):
        w.collector_panel.buttons[action].click()
        ready(qtbot, w)
        assert "Zapisz konfigurację" in w.collector_panel.message.text()


def test_global_download_start_is_saved_and_used_by_manual_sync(
    qtbot, tmp_path, monkeypatch
):
    from datetime import date

    from PySide6.QtCore import QDate

    from garmin_database.adapters.outbound.filesystem.settings_json import Settings

    w = window(qtbot, tmp_path)
    w.download_from.setDate(QDate(2025, 2, 3))
    w.save_settings()
    ready(qtbot, w)
    assert Settings.load(w.settings_path).download_from == "2025-02-03"
    calls = []
    monkeypatch.setattr(w.services, "sync", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(
        w,
        "start_work",
        lambda operation, trigger: operation(
            type(
                "W",
                (),
                {
                    "stop": threading.Event(),
                    "progress": type("P", (), {"emit": lambda *a: None})(),
                },
            )()
        ),
    )
    w.sync()
    assert calls[0][0] == date(2025, 2, 3)


def test_slow_schedule_operation_keeps_qt_alive_and_discards_old_path(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    panel = w.collector_panel
    path = tmp_path / "collector.json"
    files = CollectorFiles(path)
    files.save_config(files.defaults(tmp_path))
    panel.path.setText(str(path))
    started, release = threading.Event(), threading.Event()
    manager = w.services.collector_manager(path)

    def apply(config):
        started.set()
        assert release.wait(5)

    monkeypatch.setattr(manager, "apply", apply)
    monkeypatch.setattr(w.services, "collector_manager", lambda _: manager)
    ticks = []
    timer = QTimer(w)
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    try:
        panel.buttons["apply"].click()
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: len(ticks) >= 5)
        assert panel.buttons["apply"].loading
        panel.path.setText(str(tmp_path / "other.json"))
        panel.message.setText("Inna konfiguracja")
    finally:
        release.set()
        timer.stop()
    ready(qtbot, w)
    assert panel.message.text() == "Inna konfiguracja"


def test_status_is_human_readable_and_busy_does_not_enter_gui_journal(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    panel = w.collector_panel
    before = w.details.toPlainText()
    panel = w.collector_status
    panel.render(
        (
            CollectorFiles(tmp_path / "settings.json").defaults(tmp_path),
            {
                "schedule": {
                    "installed": True,
                    "enabled": True,
                    "revision_matches": False,
                },
                "state": {"outcome": "auth_required", "auth_required": True},
                "next_run": "2026-10-30T12:00:00+00:00",
            },
            "2026-10-30T12:00:00+00:00 success\n",
        )
    )
    assert "zmiany niezastosowane" in panel.message.text()
    assert "logowanie Garmin" in panel.message.text()
    assert w.details.toPlainText() == before
    assert panel.values["next"].text() == "2026-10-30 13:00:00 +01:00"
    assert (
        panel.log_view.toPlainText()
        == "2026-10-30 13:00:00 +01:00 Synchronizacja zakończona bez błędów i nierozstrzygniętych dni.\n"
    )


def test_collector_has_separate_page_and_shares_poll_clock(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    assert w.navigation.item(4).text() == "Kolektor"
    assert set(w.collector_panel.buttons) == {"load", "save", "apply"}
    assert "nie jest skonfigurowany" in w.collector_status.message.text()
    w.refresh_seconds.setValue(45)
    w.save_settings()
    ready(qtbot, w)
    assert w.overview.timer.interval() == 45_000
    calls = []
    original = w.services.collector_manager
    monkeypatch.setattr(
        w.services,
        "collector_manager",
        lambda path: (calls.append(path), original(path))[1],
    )
    w.overview.timer.timeout.emit()
    ready(qtbot, w)
    assert len(calls) == 1
    w.hide()
    w.overview.timer.timeout.emit()
    assert len(calls) == 1


def test_denied_task_still_shows_local_outcome_and_log(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    panel = w.collector_status
    config = CollectorFiles(tmp_path / "settings.json").defaults(tmp_path)
    panel.render(
        (
            config,
            {
                "schedule": {
                    "installed": None,
                    "enabled": False,
                    "revision_matches": False,
                    "error": "access_denied",
                },
                "state": {"outcome": "auth_required"},
                "next_run": None,
            },
            "synthetic readable log",
        )
    )
    assert "brak dostępu" in panel.message.text()
    assert "niezarejestrowany" not in panel.message.text()
    assert "logowanie Garmin" in panel.message.text()
    assert panel.log_view.toPlainText() == "synthetic readable log"


@pytest.mark.skipif(os.name != "nt", reason="Windows interactive account")
def test_interactive_mode_selects_current_account_and_explains_locked_desktop(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    panel = w.collector_panel
    assert panel.windows_logon.currentData() == "interactive"
    assert panel.account.isReadOnly()
    assert "zablokowanym ekranie" in panel.note.text()
    panel.windows_logon.setCurrentIndex(panel.windows_logon.findData("password"))
    assert not panel.account.isReadOnly()
    panel.account.setText("SYNTHETIC\\other")
    panel.windows_logon.setCurrentIndex(panel.windows_logon.findData("interactive"))
    assert panel.account.text() == w.services.current_account()
    panel.buttons["save"].click()
    ready(qtbot, w)
    assert (
        CollectorFiles(tmp_path / "settings.json").load_config().windows_logon
        == "interactive"
    )
    manager = w.services.collector_manager(panel.path.text())
    monkeypatch.setattr(manager, "install", lambda config: None)
    monkeypatch.setattr(w.services, "collector_manager", lambda path: manager)
    panel.buttons["apply"].click()
    ready(qtbot, w)
    assert "następny termin" in panel.message.text()
    assert "Przygotuj jego sesję" not in panel.message.text()
