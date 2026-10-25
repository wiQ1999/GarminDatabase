"""Hold real background paths open and check that Qt continues processing input."""

import threading
import time

import pytest
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from garmin_database.adapters.inbound.desktop import window as desktop
from garmin_database.adapters.outbound.filesystem.settings_json import SettingsStore
from garmin_database.adapters.outbound.postgres.queries import Queries
from garmin_database.application.ports import ReadFailure
from tests.ui.test_ui import ready, select_parameter, window

pytestmark = pytest.mark.ui


def hold(started, release):
    started.set()
    assert release.wait(5), "Test did not release the background operation"


def heartbeat(qtbot, w, trigger):
    ticks = []
    timer = QTimer(w)
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    angle = trigger.angle
    try:
        qtbot.waitUntil(
            lambda: len(ticks) >= 5 and trigger.angle != angle, timeout=1000
        )
        assert max(b - a for a, b in zip(ticks, ticks[1:])) < 0.3
        assert trigger.loading and trigger.timer.isActive()
        w.navigation.setCurrentRow(1)
        assert w.pages.currentIndex() == 1
        w.navigation.setCurrentRow(0)
        assert w.pages.currentIndex() == 0
    finally:
        timer.stop()


def test_refresh_during_download_never_blocks_or_duplicates_reads(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    downloading, download_done = threading.Event(), threading.Event()
    reading, read_done = threading.Event(), threading.Event()
    overview = w.services.overview
    calls = []

    def sync(*args, **kwargs):
        hold(downloading, download_done)
        return 0

    def read(*args):
        calls.append(threading.get_ident())
        hold(reading, read_done)
        return overview(*args)

    monkeypatch.setattr(w.services, "sync", sync)
    monkeypatch.setattr(w.services, "overview", read)
    try:
        w.download_button.click()
        qtbot.waitUntil(downloading.is_set)
        before = time.monotonic()
        w.overview.poll()
        assert time.monotonic() - before < 0.3
        qtbot.waitUntil(reading.is_set)
        for _ in range(20):
            w.overview.poll()
            w.overview.poll()
        heartbeat(qtbot, w, w.status_indicator)
        assert calls == [calls[0]] and calls[0] != threading.get_ident()
        assert w.download_button.loading and w.work_is_running()
    finally:
        read_done.set()
        download_done.set()
    ready(qtbot, w)
    qtbot.waitUntil(lambda: not w.stop_button.isEnabled())
    assert not w.status_indicator.loading and not w.download_button.loading


@pytest.mark.parametrize(
    "action", ["connection", "settings", "export", "config", "folder", "browser"]
)
def test_slow_main_actions_have_live_spinners(qtbot, tmp_path, monkeypatch, action):
    w = window(qtbot, tmp_path)
    started, release = threading.Event(), threading.Event()
    background_threads = []

    def slow(original):
        def wrapped(*args, **kwargs):
            background_threads.append(threading.get_ident())
            hold(started, release)
            return original(*args, **kwargs)

        return wrapped

    if action == "connection":
        monkeypatch.setattr(w.services, "reconfigure", slow(w.services.reconfigure))
        trigger, launch, page = w.save_button, w.save_settings, 3
    elif action in {"settings", "export"}:
        monkeypatch.setattr(SettingsStore, "save", slow(SettingsStore.save))
        trigger, launch, page = (
            (w.export_button, w.export, 2)
            if action == "export"
            else (w.save_button, w.save_settings, 3)
        )
    elif action == "config":
        monkeypatch.setattr(
            desktop, "client_config", slow(lambda path: {"mcpServers": {}})
        )
        trigger, launch, page = w.copy_config_button, w.copy_mcp_config, 3
    elif action == "folder":
        monkeypatch.setattr(w.services, "open_folder", slow(lambda path: None))
        trigger, launch, page = w.open_export_button, w.open_export_folder, 2
    else:
        monkeypatch.setattr(w.services, "open_url", slow(lambda url: None))
        trigger, launch, page = (
            w.login_button,
            lambda: w.open_link("https://connect.garmin.com/"),
            3,
        )
    w.navigation.setCurrentRow(page)
    try:
        before = time.monotonic()
        launch()
        assert time.monotonic() - before < 0.3
        qtbot.waitUntil(started.is_set)
        heartbeat(qtbot, w, trigger)
        assert background_threads == [background_threads[0]]
        assert background_threads[0] != threading.get_ident()
        if action != "export":
            assert trigger.text() + " — rozpoczęto" in w.details.toPlainText()
    finally:
        release.set()
    ready(qtbot, w)
    qtbot.waitUntil(lambda: not trigger.loading)
    if action == "config":
        assert "mcpServers" in QApplication.clipboard().text()
    if action == "export":
        assert w.last_export_dir.is_dir()
    else:
        assert trigger.text() + " — ukończono" in w.details.toPlainText()


def test_periodic_refresh_preserves_edits_and_never_reloads_unchanged_catalog(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    w.export_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    w.sharing_table.item(0, 2).setCheckState(Qt.CheckState.Unchecked)
    w.mcp_enabled.setChecked(True)
    w.sharing_group.setCurrentIndex(1)
    old_group = w.sharing_group.currentData()
    original = w.services.overview
    calls = []

    def read(stop, revision, include_catalog):
        calls.append(include_catalog)
        return original(stop, revision, include_catalog)

    def unexpected(*args, **kwargs):
        raise AssertionError("Unchanged overview must not query catalog or chart")

    monkeypatch.setattr(w.services, "overview", read)
    monkeypatch.setattr(Queries, "parameters", unexpected)
    monkeypatch.setattr(Queries, "chart", unexpected)
    w.overview.timer.setInterval(40)
    qtbot.waitUntil(lambda: len(calls) >= 3)
    w.overview.timer.stop()
    ready(qtbot, w)
    assert not any(calls)
    w.refresh()
    ready(qtbot, w)
    assert calls[-1] is False
    assert w.export_list.item(0).checkState() == Qt.CheckState.Unchecked
    assert w.sharing_table.item(0, 2).checkState() == Qt.CheckState.Unchecked
    assert w.mcp_enabled.isChecked() and w.sharing_group.currentData() == old_group
    assert not w.status_error.text()


def test_all_history_uses_cached_first_day(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    select_parameter(w, "monitoring.heart_rate")
    ready(qtbot, w)
    monkeypatch.setattr(w.services, "status", lambda: pytest.fail("SQL on GUI thread"))
    w.range.setCurrentText("Cała historia")
    ready(qtbot, w)
    assert w.chart_from.date() == QDate.fromString(
        w.status_info["first_day"], "yyyy-MM-dd"
    )


def test_folder_dialog_is_nonblocking_and_spinner_stops_on_cancel(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.navigation.setCurrentRow(2)
    w.browse_export_button.click()
    assert w.folder_dialog is not None and w.folder_dialog.isVisible()
    angle = w.browse_export_button.angle
    qtbot.waitUntil(lambda: w.browse_export_button.angle != angle)
    w.folder_dialog.reject()
    assert w.folder_dialog is None and not w.browse_export_button.loading


@pytest.mark.parametrize("operation", ["overview", "chart", "settings"])
def test_closing_does_not_wait_on_gui_thread(qtbot, tmp_path, monkeypatch, operation):
    w = window(qtbot, tmp_path)
    started, release = threading.Event(), threading.Event()

    def delayed(*args):
        hold(started, release)
        return {}

    if operation == "overview":
        monkeypatch.setattr(w.services, "overview", delayed)
        w.refresh()
    elif operation == "chart":
        monkeypatch.setattr(w.services, "chart", delayed)
        w.load_chart()
    else:
        monkeypatch.setattr(w.services, "reconfigure", delayed)
        w.save_settings()
    try:
        qtbot.waitUntil(started.is_set)
        before = time.monotonic()
        w.close()
        assert time.monotonic() - before < 0.3
        assert w.isVisible() and w.closing
        assert not w.overview.timer.isActive()
        ticks = []
        QTimer.singleShot(20, lambda: ticks.append(True))
        qtbot.waitUntil(lambda: bool(ticks))
    finally:
        release.set()
    qtbot.waitUntil(lambda: not w.isVisible())
    assert w.query_worker is None and w.aux_worker is None and not w.overview.busy


def test_overview_error_is_safe_and_next_cycle_recovers(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    original = w.services.overview

    def failed(*args):
        raise RuntimeError("private data must never reach UI")

    monkeypatch.setattr(w.services, "overview", failed)
    w.refresh()
    ready(qtbot, w)
    assert (
        "RuntimeError" in w.status_error.text()
        and "private data" not in w.status_error.text()
    )
    assert not w.status_indicator.loading
    monkeypatch.setattr(w.services, "overview", original)
    w.overview.poll()
    ready(qtbot, w)
    assert not w.status_error.text()


def test_reconfigured_services_discard_old_inflight_overview(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    started, release = threading.Event(), threading.Event()
    original = w.services.overview

    def stale(*args):
        result = original(*args)
        result["status"]["archives"] = 999
        hold(started, release)
        return result

    monkeypatch.setattr(w.services, "overview", stale)
    try:
        w.refresh()
        qtbot.waitUntil(started.is_set)
        w.save_settings()
        qtbot.waitUntil(lambda: w.aux_worker is None)
        assert w.overview.pending and w.overview.worker.stop.is_set()
    finally:
        release.set()
    ready(qtbot, w)
    assert w.status_info["archives"] == 1 and "999" not in w.status.text()


def test_chart_preparation_runs_off_gui_thread(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    prepare = desktop.prepare_series
    threads = []

    def prepared(*args):
        threads.append(threading.get_ident())
        return prepare(*args)

    monkeypatch.setattr(desktop, "prepare_series", prepared)
    w.load_chart()
    ready(qtbot, w)
    assert len(threads) == 1 and threads[0] != threading.get_ident()


def test_hidden_window_skips_automatic_refresh(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    assert w.overview.timer.interval() == 15_000
    assert w.overview.catalog_interval == 60
    calls = []
    original = w.services.overview

    def read(*args):
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(w.services, "overview", read)
    w.hide()
    w.overview.poll()
    assert not calls and not w.overview.busy
    w.show()
    w.overview.poll()
    ready(qtbot, w)
    assert calls == [True]


def test_legacy_settings_migration_blocks_competing_saves(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    started, release = threading.Event(), threading.Event()
    original = SettingsStore.save

    def save(*args):
        hold(started, release)
        return original(*args)

    monkeypatch.setattr(SettingsStore, "save", save)
    w.settings.settings_version = 1
    w.overview.catalog_revision = None
    try:
        w.refresh()
        qtbot.waitUntil(started.is_set)
        assert not w.save_button.isEnabled() and not w.export_button.isEnabled()
        heartbeat(qtbot, w, w.status_indicator)
    finally:
        release.set()
    ready(qtbot, w)
    assert w.settings.settings_version == 2 and w.save_button.isEnabled()


def test_stop_button_animates_until_background_operation_returns(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    started, release = threading.Event(), threading.Event()

    def sync(*args, **kwargs):
        hold(started, release)

    monkeypatch.setattr(w.services, "sync", sync)
    try:
        w.download_button.click()
        qtbot.waitUntil(started.is_set)
        w.stop_button.click()
        heartbeat(qtbot, w, w.stop_button)
        assert w.worker.stop.is_set()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not w.stop_button.loading)
    assert not w.stop_button.isEnabled() and not w.download_button.loading


def test_start_has_passive_activity_indicator_and_no_refresh_button(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    assert not any(b.text() == "Odśwież stan" for b in w.findChildren(QPushButton))
    assert not hasattr(w, "refresh_button")
    assert not isinstance(w.status_indicator, QPushButton)
    assert w.details.isVisible() and w.details.isReadOnly()
    assert not any(b.text() == "Pokaż szczegóły" for b in w.findChildren(QPushButton))


def test_operation_log_is_visible_during_work_and_keeps_only_recent_lines(
    qtbot, tmp_path
):
    w = window(qtbot, tmp_path)
    started, release = threading.Event(), threading.Event()

    def operation(worker):
        worker.progress.emit("2024-06-19", "Pobieranie", 1, 2)
        hold(started, release)
        return 0

    try:
        w.start_work(operation, w.download_button)
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: "Pobieranie" in w.details.toPlainText())
        assert w.details.isVisible()
        heartbeat(qtbot, w, w.download_button)
    finally:
        release.set()
    qtbot.waitUntil(lambda: not w.stop_button.isEnabled())
    assert w.details.isVisible() and "Ukończono" in w.details.toPlainText()
    w.details.append("\n".join(f"Wiersz {i}" for i in range(600)))
    assert w.details.document().blockCount() == 500
    assert (
        "Wiersz 599" in w.details.toPlainText()
        and "Wiersz 0\n" not in w.details.toPlainText()
    )


@pytest.mark.parametrize("initial", [False, True])
def test_repeated_state_errors_replace_one_notice(
    qtbot, tmp_path, monkeypatch, initial
):
    w = window(qtbot, tmp_path)
    if initial:
        w.status_info = {}
        w.status.setText("Odczytywanie stanu archiwum…")
    previous = w.status.text()

    def failed(*args):
        raise ReadFailure("private details", reason="connection")

    monkeypatch.setattr(w.services, "overview", failed)
    notices = []
    for _ in range(4):
        w.overview.poll()
        ready(qtbot, w)
        notices.append(w.status_error.text())
    assert len(set(notices)) == 1
    assert notices[0].count("Nie udało się odświeżyć stanu") == 1
    assert "private details" not in notices[0] and "ReadFailure" not in notices[0]
    assert w.status.text() == (
        "Stan archiwum jest chwilowo niedostępny." if initial else previous
    )


def test_slow_catalog_publishes_counters_before_catalog_finishes(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    original = w.services.catalog
    started, release = threading.Event(), threading.Event()

    def delayed(*args):
        hold(started, release)
        return original(*args)

    monkeypatch.setattr(w.services, "catalog", delayed)
    w.status_info = {}
    w.status.setText("Odczytywanie stanu archiwum…")
    try:
        w.refresh()
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: bool(w.status_info))
        assert "Archiwa w bazie: 1" in w.status.text()
        heartbeat(qtbot, w, w.status_indicator)
    finally:
        release.set()
    ready(qtbot, w)


def test_catalog_timeout_keeps_status_and_obeys_retry_interval(
    qtbot, tmp_path, monkeypatch
):
    w = window(qtbot, tmp_path)
    calls = []

    def failed(*args):
        calls.append(True)
        raise ReadFailure("private details", reason="timeout")

    original = w.services.catalog
    monkeypatch.setattr(w.services, "catalog", failed)
    w.refresh()
    ready(qtbot, w)
    assert "Archiwa w bazie: 1" in w.status.text()
    assert (
        "listy parametrów" in w.status_error.text()
        and "czas odczytu" in w.status_error.text()
    )
    assert (
        "połączyć" not in w.status_error.text()
        and "private" not in w.status_error.text()
    )
    for _ in range(3):
        w.overview.poll()
        ready(qtbot, w)
    assert calls == [True]
    assert "Archiwa w bazie: 1" in w.status.text()
    assert w.status_error.text().count("listy parametrów") == 1
    monkeypatch.setattr(w.services, "catalog", original)
    w.overview.catalog_checked = float("-inf")
    w.overview.poll()
    ready(qtbot, w)
    assert not w.status_error.text()
