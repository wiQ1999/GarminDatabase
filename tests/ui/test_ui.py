import threading

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QMessageBox, QPushButton

from garmin_database.adapters.inbound.desktop.chart import Chart
from garmin_database.adapters.inbound.desktop.workers import Worker
from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.adapters.outbound.postgres.queries import Queries, bounds
from garmin_database.bootstrap.desktop import Window
from tests.support.fixtures import archive, fit_bytes

pytestmark = pytest.mark.ui


@pytest.mark.parametrize("span", [1000, 60000, 30 * 86400000])
def test_time_axis_adds_readable_ticks_and_adapts_to_width(qtbot, span):
    chart = Chart()
    qtbot.addWidget(chart)
    begin = 1_800_000_000_000
    original = [(begin, 1, "synthetic"), (begin + span, 3, "synthetic")]
    chart.set_series(original)
    chart.resize(850, 400)
    chart.show()
    chart.grab()
    wide_count = len(chart.time_labels)
    assert (2 if span < 60000 else 3) <= wide_count <= 8
    assert len({label for _, label, _, _ in chart.time_labels}) == wide_count
    chart.resize(400, 400)
    chart.grab()
    assert 2 <= len(chart.time_labels) <= wide_count
    if span >= 60000:
        assert len(chart.time_labels) < wide_count
    assert all(
        a[3].right() + 12 <= b[3].left()
        for a, b in zip(chart.time_labels, chart.time_labels[1:])
    )
    assert chart.points == original and len(chart.positions) == len(original)


def window(qtbot, tmp_path, summaries=False):
    db = Database(tmp_path / "data")
    db.initialize()
    Importer(db).archive(archive(db.root))
    if summaries:
        Importer(db).archive(
            archive(
                db.root,
                "2024-11-07",
                fit_bytes(55, [(253, 4, 134), (2, 4, 134)], [(1100000000, 100)]),
            )
        )
        for day, value in [("2024-11-08", 70), ("2024-11-09", 72)]:
            Importer(db).archive(
                archive(db.root, day, fit_bytes(346, [(6, 1, 2)], [(value,)]))
            )
    w = Window(
        Settings(data_dir=str(db.root), export_dir=str(tmp_path / "exports")),
        tmp_path / "settings.json",
    )
    qtbot.addWidget(w)
    w.show()
    ready(qtbot, w)
    return w


def ready(qtbot, w):
    qtbot.waitUntil(
        lambda: (
            w.overview.initialized
            and not w.overview.busy
            and w.aux_worker is None
            and w.query_worker is None
            and not w.query_pending
        ),
        timeout=5000,
    )


def test_sharing_policy_is_independent_and_survives_restart(qtbot, tmp_path):
    w = window(qtbot, tmp_path, summaries=True)
    w.navigation.setCurrentRow(3)
    heart = next(
        i for i, p in enumerate(w.parameters) if p["key"] == "monitoring.heart_rate"
    )
    other = next(
        i for i, p in enumerate(w.parameters) if p["key"] == "monitoring.distance"
    )
    w.select_sharing(2, False)
    w.sharing_table.item(heart, 3).setCheckState(Qt.CheckState.Checked)
    w.mcp_enabled.setChecked(True)
    assert not w.sharing_table.item(other, 3).flags() & Qt.ItemFlag.ItemIsEnabled
    w.save_settings()
    ready(qtbot, w)
    saved = Settings.load(tmp_path / "settings.json")
    assert saved.export_parameters == []
    assert saved.mcp_parameters == ["monitoring.heart_rate"] and saved.mcp_enabled
    assert w.export_list.count() == 0
    w.refresh()
    ready(qtbot, w)
    assert w.sharing_keys(2) == [] and w.sharing_keys(3) == ["monitoring.heart_rate"]
    w.copy_sharing(3, 2)
    w.save_settings()
    ready(qtbot, w)
    assert w.export_list.count() == 1
    w.copy_mcp_config()
    ready(qtbot, w)
    from PySide6.QtWidgets import QApplication

    assert "mcpServers" in QApplication.clipboard().text()


def test_sharing_group_actions_respect_filter(qtbot, tmp_path):
    w = window(qtbot, tmp_path, summaries=True)
    w.sharing_group.setCurrentIndex(w.sharing_group.findData("Serce i HRV"))
    w.select_sharing(2, False)
    assert "monitoring.heart_rate" not in w.sharing_keys(2)
    assert "monitoring.distance" in w.sharing_keys(2)
    w.select_sharing(3, True)
    assert w.sharing_keys(3) == ["monitoring.heart_rate"]


def select_parameter(w, key):
    for i in range(w.parameter_list.count()):
        parameter = w.parameter_list.item(i).data(Qt.ItemDataRole.UserRole)
        if parameter and parameter["key"] == key:
            w.parameter_list.setCurrentRow(i)
            return
    raise AssertionError(f"Missing parameter: {key}")


def test_navigation_and_chart(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    assert f"Rozpoznane serie / właściwości: {len(w.parameters)}" in w.status.text()
    for index in range(4):
        w.navigation.setCurrentRow(index)
        assert w.pages.currentIndex() == index
    w.navigation.setCurrentRow(1)
    heart = next(
        i
        for i in range(w.parameter_list.count())
        if "Tętno" == w.parameter_list.item(i).text()
    )
    w.parameter_list.setCurrentRow(heart)
    qtbot.waitUntil(lambda: w.query_worker is None, timeout=5000)
    assert all(w.range.model().item(i).isEnabled() for i in range(6))
    w.range.setCurrentIndex(0)
    w.chart_to.setDate(QDate(2024, 11, 8))
    qtbot.waitUntil(lambda: w.query_worker is None, timeout=5000)
    assert w.chart.points and len(w.chart.points) == 2
    assert w.chart.grab().width() > 0


def test_ranges_follow_parameter_and_dates_refresh_automatically(qtbot, tmp_path):
    w = window(qtbot, tmp_path, summaries=True)
    select_parameter(w, "sleep_assessment.overall_sleep_score")
    w.chart_to.setDate(QDate(2024, 11, 9))
    w.range.setCurrentIndex(2)
    ready(qtbot, w)
    assert [point[1] for point in w.chart.points] == [70, 72]
    assert all(w.range.model().item(i).isEnabled() for i in range(6))

    select_parameter(w, "monitoring.distance")
    ready(qtbot, w)
    assert w.range.currentText() == "Dzień"
    assert w.chart_from.date() == w.chart_to.date()
    assert not w.chart_from.isEnabled()
    assert all(not w.range.model().item(i).isEnabled() for i in range(1, 6))
    # Even a programmatic attempt to use a disabled range remains single-day.
    w.range.setCurrentIndex(5)
    w.chart_to.setDate(QDate(2024, 11, 8))
    ready(qtbot, w)
    assert w.range.currentText() == "Dzień"
    assert [point[1] for point in w.chart.points] == [1]

    select_parameter(w, "monitoring.heart_rate")
    w.range.setCurrentIndex(2)
    ready(qtbot, w)
    assert [point[1] for point in w.chart.points] == [63]
    assert "obliczone" in w.chart_message.text()

    select_parameter(w, "sleep_assessment.overall_sleep_score")
    w.range.setCurrentIndex(5)
    w.chart_to.setDate(QDate(2024, 11, 9))
    ready(qtbot, w)
    assert w.chart_from.isEnabled()
    assert len(w.chart.points) == 2
    w.chart_from.setDate(QDate(2024, 11, 9))
    ready(qtbot, w)
    assert [point[1] for point in w.chart.points] == [72]
    w.chart_to.setDate(QDate(2024, 11, 8))
    ready(qtbot, w)
    assert "późniejsza" in w.chart_message.text()
    assert not w.chart.points and not w.chart_view.loading
    assert not any(b.text() == "Pokaż wykres" for b in w.findChildren(QPushButton))


@pytest.mark.parametrize("fail_first", [False, True])
def test_loading_animates_and_stale_results_do_not_replace_latest_selection(
    qtbot, tmp_path, monkeypatch, fail_first
):
    w = window(qtbot, tmp_path)
    w.navigation.setCurrentRow(1)
    select_parameter(w, "monitoring.heart_rate")
    w.range.setCurrentIndex(0)
    ready(qtbot, w)
    started = threading.Event()
    release = threading.Event()
    calls = []

    def query(self, parameter, start, end, conn=None, stop=None):
        calls.append((start, end))
        if len(calls) == 1:
            started.set()
            assert release.wait(5)
            if fail_first:
                raise RuntimeError("Synthetic failure")
        return [(bounds(start, end)[0], end.day, "synthetic")], "latest"

    monkeypatch.setattr(Queries, "chart", query)
    try:
        w.chart_to.setDate(QDate(2024, 11, 8))
        qtbot.waitUntil(started.is_set)
        assert w.chart_view.loading and w.chart_view.overlay.isVisible()
        assert w.chart_view.blur.isEnabled() and not w.chart.isEnabled()
        angle = w.chart_view.overlay.angle
        qtbot.waitUntil(lambda: w.chart_view.overlay.angle != angle)
        w.chart_to.setDate(QDate(2024, 11, 10))
        w.chart_to.setDate(QDate(2024, 11, 9))
        assert w.chart_view.loading
    finally:
        release.set()
    ready(qtbot, w)
    assert len(calls) == 2 and calls[-1][1].day == 9
    assert w.chart.points[0][1] == 9 and w.chart_message.text() == "latest"
    assert not w.chart_view.loading and not w.chart_view.overlay.isVisible()
    assert not w.chart_view.blur.isEnabled() and w.chart.isEnabled()
    assert not w.chart_view.overlay.timer.isActive()


def test_loading_ends_on_query_error(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)

    def query(*args):
        raise RuntimeError("Synthetic failure")

    monkeypatch.setattr(Queries, "chart", query)
    w.chart_to.setDate(QDate(2024, 11, 8))
    ready(qtbot, w)
    assert not w.chart_view.loading and not w.chart.points
    assert not w.trend.isEnabled()
    assert "RuntimeError" in w.chart_message.text()


def test_trend_toggle_draws_overlay_without_changing_source_points(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.navigation.setCurrentRow(1)
    select_parameter(w, "monitoring.heart_rate")
    w.range.setCurrentIndex(0)
    w.chart_to.setDate(QDate(2024, 11, 8))
    ready(qtbot, w)
    assert w.trend.isEnabled() and not w.trend.isChecked()
    original = list(w.chart.points)
    without = w.chart.grab().toImage()
    w.trend.setChecked(True)
    with_trend = w.chart.grab().toImage()
    assert w.chart.trend_visible and without != with_trend
    assert w.chart.points == original
    w.trend.setChecked(False)
    assert not w.chart.trend_visible
    # Categorical series cannot acquire a numerical regression.
    parameter = dict(w.selected_parameter(), enum={"1": "light", "2": "deep"})
    w.show_chart(([(0, 1, "a"), (10, 2, "b")], "categories"), parameter)
    assert not w.trend.isEnabled() and not w.chart.trend_points


def test_ui_export_and_settings(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.export_from.setDate(
        __import__("PySide6.QtCore", fromlist=["QDate"]).QDate(2024, 1, 1)
    )
    w.recent.setValue(1000)
    w.summary_period.setCurrentIndex(1)
    w.export()
    qtbot.waitUntil(
        lambda: w.worker is not None and not w.worker.isRunning(), timeout=5000
    )
    qtbot.waitUntil(lambda: not w.stop_button.isEnabled())
    assert w.last_export_dir.is_dir()
    assert list((w.last_export_dir / "details").glob("*.json"))
    assert list((w.last_export_dir / "history").glob("*.json"))
    assert not (w.last_export_dir / "recent.json").exists()
    assert Settings.load(tmp_path / "settings.json").recent_days == 1000
    assert Settings.load(tmp_path / "settings.json").summary_period == "month"
    first = w.last_export_dir
    w.export()
    qtbot.waitUntil(lambda: not w.stop_button.isEnabled())
    assert w.last_export_dir != first and first.is_dir()
    assert w.export_button.isEnabled()


def test_failed_days_show_details_and_summary_after_worker_finishes(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.details.append("Poprzednia operacja")

    def operation(worker):
        worker.progress.emit("2024-01-01", "Błąd pobierania — HTTP 404", 1, 2)
        worker.progress.emit("2024-01-02", "import", 2, 2)
        return 1

    w.start_work(operation)
    qtbot.waitUntil(lambda: not w.stop_button.isEnabled(), timeout=5000)
    assert w.details.isVisible()
    assert "HTTP 404" in w.details.toPlainText()
    assert "nierozstrzygnięte" in w.stage.text()
    assert w.stage.text() in w.details.toPlainText()
    assert "Poprzednia operacja" not in w.details.toPlainText()
    assert w.details_button.text() == "Ukryj szczegóły"
    w.toggle_details()
    assert not w.details.isVisible()
    assert w.details_button.text() == "Pokaż szczegóły"


def test_worker_cancel(qtbot):
    from garmin_database.domain.cancellation import Cancelled

    def operation(w):
        w.stop.wait()
        raise Cancelled()

    worker = Worker(operation)
    with qtbot.waitSignal(worker.failure, timeout=2000) as blocker:
        worker.start()
        worker.stop.set()
    worker.wait()
    assert "Zatrzymano" in blocker.args[0]


def test_close_stops_operation(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes
    )
    w.start_work(lambda worker: worker.stop.wait())
    w.close()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=5000)
    assert w.worker.stop.is_set()


def test_worker_waits_for_a_fresh_code_on_each_mfa_request(qtbot):
    captured = []
    requested = []
    worker = Worker(lambda w: captured.extend([w.ask_mfa(), w.ask_mfa()]))

    def answer():
        requested.append(True)
        worker.code = str(len(requested)) * 6
        worker.mfa_ready.set()

    worker.mfa_requested.connect(answer)
    with qtbot.waitSignal(worker.finished, timeout=3000):
        worker.start()
    worker.wait()
    assert captured == ["111111", "222222"]
    assert worker.code is None


def test_login_dialog_reports_phase_and_safe_diagnostic(qtbot):
    from garmin_database.adapters.inbound.desktop.login_dialog import LoginDialog
    from garmin_database.application.errors import LoginFailed

    release = threading.Event()

    def operation(worker):
        worker.login_stage.emit("mfa_verify")
        assert release.wait(3)
        raise LoginFailed("mfa_verify")

    worker = Worker(operation)
    dialog = LoginDialog(worker)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.start()
    try:
        qtbot.waitUntil(lambda: "dostępu aplikacji" in dialog.message.text())
        assert dialog.spinner.timer.isActive()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not dialog.spinner.timer.isActive())
    assert "MFA_VERIFY/CLIENT_ERROR" in dialog.message.text()
    assert "synthetic-private-response" not in dialog.message.text()
    assert not dialog.authenticated and worker.operation is None
    dialog.reject()


@pytest.mark.parametrize("error_kind", ["credentials", "network"])
def test_login_failure_allows_a_new_attempt_without_restarting(
    qtbot, tmp_path, monkeypatch, error_kind
):
    from garminconnect import GarminConnectAuthenticationError

    attempts = []
    release = threading.Event()

    class Source:
        def login(self, email, password, mfa, stop=None, progress=None):
            attempts.append((email, password))
            if len(attempts) == 1:
                error = (
                    GarminConnectAuthenticationError
                    if error_kind == "credentials"
                    else RuntimeError
                )
                raise error("synthetic-private-detail")
            assert release.wait(3)

    monkeypatch.setattr("garmin_database.bootstrap.dependencies.create_source", Source)
    w = window(qtbot, tmp_path)
    w.email.setText("synthetic@example.invalid")
    w.password.setText("wrong-synthetic-password")
    w.login()
    first = w.login_dialog
    qtbot.waitUntil(lambda: not first.spinner.timer.isActive())
    assert not first.authenticated and first.worker.operation is None
    assert "synthetic-private-detail" not in first.message.text()
    assert w.worker is None and w.password.text() == ""
    first.reject()
    assert w.login_dialog is None and w.login_button.isEnabled()
    w.password.setText("new-synthetic-password")
    w.login()
    second = w.login_dialog
    try:
        assert second is not first and second.worker is not first.worker
        assert second.isVisible() and second.spinner.timer.isActive()
        angle = second.spinner.angle
        qtbot.waitUntil(lambda: second.spinner.angle != angle)
    finally:
        release.set()
    qtbot.waitUntil(lambda: not second.spinner.timer.isActive())
    assert second.authenticated and second.worker.operation is None
    assert "Zalogowano" in w.session_status.text()
    second.reject()
    assert len(attempts) == 2 and w.login_dialog is None
    assert "synthetic-password" not in (tmp_path / "settings.json").read_text()


def test_login_cancellation_waits_for_worker_and_allows_retry(
    qtbot, tmp_path, monkeypatch
):
    started = threading.Event()
    calls = []

    class Source:
        def login(self, email, password, mfa, stop=None, progress=None):
            calls.append(True)
            started.set()
            if len(calls) == 1:
                assert stop.wait(3)

    monkeypatch.setattr("garmin_database.bootstrap.dependencies.create_source", Source)
    w = window(qtbot, tmp_path)
    w.email.setText("synthetic@example.invalid")
    w.password.setText("synthetic-password")
    w.login()
    first = w.login_dialog
    qtbot.waitUntil(started.is_set)
    first.close()
    qtbot.waitUntil(lambda: w.login_dialog is None)
    assert "anulowane" in w.session_status.text()
    assert w.login_button.isEnabled()
    w.password.setText("synthetic-password")
    w.login()
    second = w.login_dialog
    qtbot.waitUntil(lambda: not second.spinner.timer.isActive())
    assert second.authenticated and len(calls) == 2
    second.reject()


def test_login_mfa_cancel_then_fresh_codes_on_retry(qtbot, tmp_path, monkeypatch):
    codes = []

    class Source:
        def login(self, email, password, mfa, stop=None, progress=None):
            codes.extend([mfa(), mfa()])

    monkeypatch.setattr("garmin_database.bootstrap.dependencies.create_source", Source)
    w = window(qtbot, tmp_path)
    w.email.setText("synthetic@example.invalid")
    w.password.setText("synthetic-password")
    w.login()
    first = w.login_dialog
    qtbot.waitUntil(lambda: first.mfa_dialog is not None)
    first.mfa_dialog.reject()
    qtbot.waitUntil(lambda: w.login_dialog is None)
    assert "anulowane" in w.session_status.text()
    w.password.setText("synthetic-password")
    w.login()
    second = w.login_dialog
    for code in ("123456", "654321"):
        qtbot.waitUntil(lambda: second.mfa_dialog is not None)
        second.mfa_dialog.setTextValue(code)
        second.mfa_dialog.accept()
    qtbot.waitUntil(lambda: not second.spinner.timer.isActive())
    assert codes == ["123456", "654321"]
    assert second.authenticated and second.worker.code is None
    second.reject()


def test_closing_window_cancels_login_before_destroying_the_worker(
    qtbot, tmp_path, monkeypatch
):
    started = threading.Event()

    class Source:
        def login(self, email, password, mfa, stop=None, progress=None):
            started.set()
            assert stop.wait(3)

    monkeypatch.setattr("garmin_database.bootstrap.dependencies.create_source", Source)
    w = window(qtbot, tmp_path)
    w.email.setText("synthetic@example.invalid")
    w.password.setText("synthetic-password")
    w.login()
    qtbot.waitUntil(started.is_set)
    w.close()
    qtbot.waitUntil(lambda: not w.isVisible())
    assert w.login_dialog is None


def test_missing_session_is_explained_in_settings_and_worker(
    qtbot, tmp_path, monkeypatch
):
    from garmin_database.adapters.outbound.security.dpapi_session import SessionStore
    from garmin_database.application.errors import SessionRequired

    monkeypatch.setattr(
        "garmin_database.bootstrap.dependencies.SessionStore",
        lambda: SessionStore(tmp_path / "missing"),
    )
    w = window(qtbot, tmp_path)
    assert "Brak zapisanej sesji" in w.session_status.text()

    def operation(worker):
        raise SessionRequired()

    worker = Worker(operation)
    with qtbot.waitSignal(worker.failure, timeout=2000) as result:
        worker.start()
    worker.wait()
    assert "Ustawienia" in result.args[0] and "RuntimeError" not in result.args[0]


def test_postgresql_connection_change_persists_and_reads_new_database(
    qtbot, tmp_path, monkeypatch
):
    import os
    from uuid import uuid4

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    w = window(qtbot, tmp_path)
    original_db = w.services
    schema = "garmin_ui_" + uuid4().hex
    with psycopg.connect(
        os.environ["GARMIN_TEST_DATABASE_DSN"], autocommit=True
    ) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            options = conninfo_to_dict(os.environ["GARMIN_DATABASE_DSN"])
            password = options.pop("password", None)
            if password is not None:
                monkeypatch.setenv("PGPASSWORD", password)
            options["options"] = f"-c search_path={schema}"
            dsn = make_conninfo(**options)
            w.database_dsn.setText(dsn)
            w.save_settings()
            ready(qtbot, w)
            assert Settings.load(tmp_path / "settings.json").database_dsn == dsn
            assert w.services.status()["fields"] == 0
            assert original_db.status()["fields"] == 8
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def test_postgresql_password_is_not_persisted_from_ui(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    original_db = w.services
    previous = (tmp_path / "settings.json").read_bytes()
    w.database_dsn.setText("host=localhost dbname=garmin password=private-secret")
    w.save_settings()
    ready(qtbot, w)
    assert w.services is original_db
    assert "ValueError" in w.settings_status.text()
    assert "private-secret" not in w.settings_status.text()
    assert (tmp_path / "settings.json").read_bytes() == previous


def test_startup_database_error_explains_password_failure(
    qtbot, qapp, tmp_path, monkeypatch
):
    from psycopg import OperationalError

    from garmin_database.bootstrap import desktop as ui

    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    settings_path = tmp_path / "settings.json"
    Settings(data_dir=str(tmp_path / "data")).save(settings_path)
    monkeypatch.setattr(ui, "QApplication", lambda argv: qapp)

    def fail(*args):
        raise OperationalError("no password supplied private-secret")

    messages = []
    monkeypatch.setattr(ui, "Window", fail)
    monkeypatch.setattr(
        ui.QMessageBox,
        "critical",
        lambda parent, title, message: messages.append(message),
    )
    assert ui.main(["--settings-file", str(settings_path)]) == 1
    assert "STARTUP/PASSWORD_MISSING" in messages[0]
    assert "pgpass" in messages[0] and "private-secret" not in messages[0]
