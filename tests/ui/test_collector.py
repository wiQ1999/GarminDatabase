"""Automation settings stay responsive and do not silently register tasks."""

import threading

import pytest
from PySide6.QtCore import QTimer

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from tests.ui.test_ui import ready, window

pytestmark = pytest.mark.ui


def test_save_collector_config_is_separate_from_apply_and_gui_preferences(
    qtbot, tmp_path
):
    w = window(qtbot, tmp_path)
    panel = w.collector_panel
    path = tmp_path / "collector.json"
    panel.path.setText(str(path))
    assert panel.interval.minimum() == 15 and panel.interval.value() == 120
    panel.enabled.setChecked(True)
    panel.account.setText("garmin")
    panel.buttons["save"].click()
    ready(qtbot, w)
    config = CollectorFiles(path).load_config()
    assert config.enabled and config.run_as == "garmin"
    assert config.data_dir == w.settings.data_dir
    assert config.database_dsn is None and config.download_from is None
    assert config.settings_path == str(tmp_path / "settings.json")
    assert "Zastosuj" in panel.message.text()
    w.save_settings()
    ready(qtbot, w)
    assert w.settings.collector_config_path == str(path)
    panel.interval.setValue(30)
    panel.buttons["load"].click()
    ready(qtbot, w)
    assert panel.interval.value() == 120


def test_defaults_share_configuration_directory_and_current_account(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    panel = w.collector_panel
    assert panel.path.text() == str(tmp_path / "collector.json")
    assert panel.path.isReadOnly() and w.config_directory.isReadOnly()
    assert w.config_directory.text() == str(tmp_path)
    assert panel.account.text() == w.services.current_account()
    assert not hasattr(panel, "dsn")
    assert not hasattr(panel, "data_dir")


def test_missing_config_shows_actionable_message(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    for action in ("load", "status", "logs", "apply"):
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
    panel._status(
        {
            "schedule": {"installed": True, "enabled": True, "revision_matches": False},
            "state": {"outcome": "auth_required", "auth_required": True},
            "next_run": "2026-10-30T12:00:00+00:00",
        }
    )
    assert "zmiany niezastosowane" in panel.message.text()
    assert "logowanie Garmin" in panel.message.text()
    assert w.details.toPlainText() == before
