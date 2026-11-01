"""Desktop navigation, shared workers and orderly shutdown."""

import os
from collections import deque
from datetime import date
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.collector_status import (
    CollectorStatusPanel,
)
from garmin_database.adapters.inbound.desktop.icons import (
    application_icon,
)
from garmin_database.adapters.inbound.desktop.login_dialog import LoginDialog
from garmin_database.adapters.inbound.desktop.overview import OverviewPoller
from garmin_database.application.ports import DesktopServices
from garmin_database.domain.time import today

from .data_page import DataPage
from .export_page import ExportPage
from .settings_page import SettingsPage
from .start_page import StartPage
from .theme import STYLE
from .widgets import page_layout
from .workers import Worker


class Window(QMainWindow):
    def __init__(self, settings, settings_path=None, *, services: DesktopServices):
        super().__init__()
        self.services = services
        self.settings = settings
        self.settings_path = settings_path
        if os.name == "nt" and not QFontDatabase.families():
            # Offscreen/sandboxed Windows can lack DirectWrite font enumeration.
            # Use the installed Windows font; do not distribute a copied font.
            QFontDatabase.addApplicationFont(
                str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf")
            )
        self.worker = None
        self.login_dialog = None
        self.aux_worker = None
        self.aux_button = None
        self.operation_button = None
        self.folder_dialog = None
        self.closing = False
        self.parameters = []
        self.status_info = {}
        self.state_error = ""
        self.catalog_error = ""
        self.catalog_loaded = False
        self.session_cached = None
        self.progress_pending = None
        self.progress_details = deque(maxlen=500)
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(100)
        self.setWindowTitle("GarminDatabase")
        self.setWindowIcon(application_icon())
        self.resize(1180, 800)
        self.setMinimumSize(900, 650)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(18, 18, 18, 18)
        row.setSpacing(24)
        nav = QVBoxLayout()
        heading = QHBoxLayout()
        heading.setSpacing(8)
        brand_icon = QLabel()
        brand_icon.setPixmap(self.windowIcon().pixmap(28, 28))
        brand_icon.setAccessibleName("Ikona GarminDatabase")
        heading.addWidget(brand_icon)
        brand = QLabel("GarminDatabase")
        brand.setStyleSheet("font-size:18px;font-weight:600;padding:14px 0;")
        heading.addWidget(brand)
        nav.addLayout(heading)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.addItems(["Start", "Dane", "Eksport", "Ustawienia", "Kolektor"])
        self.navigation.setFixedWidth(185)
        nav.addWidget(self.navigation)
        nav.addWidget(QLabel("Archiwum dobrostanu\nDane z Garmin Connect"))
        row.addLayout(nav)
        self.pages = QStackedWidget()
        row.addWidget(self.pages, 1)
        self.navigation.currentRowChanged.connect(self.page_changed)
        self.start_page = StartPage(self)
        self.progress_timer.timeout.connect(self.start_page.flush_progress)
        self.pages.addWidget(self.start_page)
        self.data_page = DataPage(self)
        self.pages.addWidget(self.data_page)
        self.export_page = ExportPage(self)
        self.pages.addWidget(self.export_page)
        self.settings_page = SettingsPage(self)
        self.pages.addWidget(self.settings_page)
        collector_page = QWidget()
        self.pages.addWidget(collector_page)
        collector_layout = page_layout(
            collector_page,
            "Kolektor",
            "Automatyczne pobieranie • stan i dziennik aktualizowane razem ze stanem bazy.",
        )
        self.collector_status = CollectorStatusPanel(
            self, self.settings_page.collector_panel
        )
        collector_layout.addWidget(self.collector_status)
        self.collector_status.idle.connect(self.close_if_idle)
        self.navigation.setCurrentRow(0)
        self.overview = OverviewPoller(
            services,
            settings,
            settings_path,
            lambda: self.isVisible() and not self.isMinimized(),
            self,
        )
        self.overview.ready.connect(self.show_overview)
        self.overview.failed.connect(self.overview_error)
        self.overview.catalog_failed.connect(self.overview_catalog_error)
        self.overview.busy_changed.connect(self.start_page.status_indicator.set_loading)
        self.overview.busy_changed.connect(self.update_action_states)
        self.overview.idle.connect(self.close_if_idle)
        self.overview.timer.timeout.connect(self.collector_status.poll)
        QTimer.singleShot(0, self.collector_status.poll)
        QTimer.singleShot(0, self.refresh)

    def page_changed(self, index):
        self.pages.setCurrentIndex(index)
        if index == 1 and self.data_page.chart_dirty:
            self.data_page.load_chart()

    def open_link(self, url):
        services = self.services
        self.start_aux(
            self.settings_page.login_button, lambda w: services.open_url(url)
        )

    def pick_folder(self, field, trigger=None):
        if self.folder_dialog is not None:
            self.folder_dialog.raise_()
            return
        dialog = QFileDialog(self, "Wybierz folder", field.text())
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly)
        self.folder_dialog = dialog
        if trigger:
            trigger.set_loading(True)
        dialog.fileSelected.connect(field.setText)

        def release():
            self.folder_dialog = None
            if trigger:
                trigger.set_loading(False)
            dialog.deleteLater()

        dialog.finished.connect(release)
        dialog.open()

    def refresh(self):
        self.overview.request()

    def show_overview(self, result):
        self.status_info = result["status"]
        self.state_error = ""
        if "catalog_revision" in result:
            self.catalog_error = ""
            self.catalog_loaded = True
        self.start_page.show_overview_errors()
        if "settings" in result:
            self.settings = result["settings"]
        parameters = result["parameters"]
        if parameters is not None and parameters != self.parameters:
            self.parameters = parameters
            self.settings_page.refresh_sharing()
            self.data_page.populate_parameters()
        self.start_page.update_status(self.status_info)
        available = result["session_available"]
        if available != self.session_cached and self.login_dialog is None:
            self.session_cached = available
            self.settings_page.session_status.setText(
                (
                    "Zapisana sesja Garmin jest dostępna. Jej ważność zostanie sprawdzona przy pobraniu. "
                    if available
                    else "Brak zapisanej sesji Garmin. Zaloguj się, aby pobierać nowe dni. Lokalne archiwa można importować bez logowania. "
                )
                + "Sesja jest szyfrowana przez Windows DPAPI. Hasło i kod MFA nie są zapisywane."
            )

    def overview_error(self, message):
        if not self.closing:
            self.state_error = (
                "Nie udało się odświeżyć stanu. Kolejna próba nastąpi automatycznie.\n"
                + message
            )
            if not self.status_info:
                self.start_page.status.setText(
                    "Stan archiwum jest chwilowo niedostępny."
                )
            self.start_page.show_overview_errors()

    def overview_catalog_error(self, message):
        if not self.closing:
            self.catalog_error = (
                "Nie udało się odczytać listy parametrów. Kolejna próba nastąpi automatycznie.\n"
                + message
            )
            self.start_page.show_overview_errors()
            if self.status_info:
                self.start_page.update_status(self.status_info)

    def update_action_states(self, *args):
        busy = self.work_is_running() or self.aux_worker is not None or self.closing
        for b in (
            self.start_page.download_button,
            self.start_page.download_all_button,
            self.export_page.export_button,
            self.settings_page.login_button,
            self.settings_page.save_button,
        ):
            b.setEnabled(not busy)
        if hasattr(self, "overview") and (
            not self.overview.initialized
            or (self.overview.busy and self.settings.settings_version == 1)
        ):
            self.settings_page.save_button.setEnabled(False)
            self.export_page.export_button.setEnabled(False)
        self.start_page.stop_button.setEnabled(
            self.work_is_running() and not self.closing
        )

    def start_work(self, operation, trigger=None):
        if self.work_is_running() or self.aux_worker is not None or self.closing:
            return False
        if self.worker is not None:
            self.worker.deleteLater()
        worker = Worker(operation, self)
        self.worker = worker
        worker.progress.connect(self.start_page.on_progress)
        worker.failure.connect(self.start_page.on_failure)
        worker.success.connect(self.start_page.on_success)
        worker.finished.connect(self.work_finished)
        self.operation_button = trigger
        if trigger:
            trigger.set_loading(True)
        self.start_page.stage.setText("Rozpoczynanie…")
        self.start_page.details.clear()
        self.progress_pending = None
        self.progress_details.clear()
        self.start_page.progress.setRange(0, 0)
        self.start_page.stop_button.set_loading(False)
        self.progress_timer.start()
        worker.start()
        self.update_action_states()
        return True

    def work_is_running(self):
        return self.worker is not None and self.worker.isRunning()

    def stop_work(self):
        if self.worker:
            self.worker.stop.set()
            self.start_page.stop_button.set_loading(True)
            self.start_page.stage.setText("Zatrzymywanie w bezpiecznym punkcie…")

    def work_finished(self):
        self.progress_timer.stop()
        if self.operation_button:
            self.operation_button.set_loading(False)
        self.operation_button = None
        self.start_page.progress.setRange(0, max(1, self.start_page.progress.maximum()))
        self.start_page.stop_button.setEnabled(False)
        self.start_page.stop_button.set_loading(False)
        self.update_action_states()
        self.data_page.chart_dirty = True
        if self.worker:
            self.worker.operation = None
        self.close_if_idle()

    def sync(self, refresh_all=False):
        start = date.fromisoformat(self.settings.download_from)
        db = self.services
        delay = self.settings.delay
        trigger = (
            self.start_page.download_all_button
            if refresh_all
            else self.start_page.download_button
        )
        self.start_work(
            lambda w: db.sync(
                start,
                today(),
                w.stop,
                w.progress.emit,
                delay=delay,
                detailed=True,
                refresh_all=refresh_all,
            ),
            trigger,
        )

    def login(self):
        if self.login_dialog is not None:
            self.login_dialog.raise_()
            self.login_dialog.activateWindow()
            return
        if self.work_is_running() or self.aux_worker is not None or self.closing:
            return
        email = self.settings_page.email.text().strip()
        password = self.settings_page.password.text()
        self.settings_page.password.clear()
        if not email or not password:
            self.settings_page.session_status.setText("Podaj e-mail i hasło")
            return

        collector_login = self.settings_page.login_target.currentData() == "collector"
        services = self.services
        collector_path = self.settings_page.collector_panel.path.text()

        def operation(w):
            if collector_login:
                return services.login_collector(
                    collector_path,
                    email,
                    password,
                    w.ask_mfa,
                    w.stop,
                    w.login_stage.emit,
                )
            return services.login(
                email, password, w.ask_mfa, w.stop, w.login_stage.emit
            )

        dialog = LoginDialog(Worker(operation), self)
        self.login_dialog = dialog
        dialog.status_changed.connect(self.settings_page.session_status.setText)
        dialog.status_changed.connect(self.start_page.details.append)
        dialog.finished.connect(self.login_closed)
        self.settings_page.login_button.set_loading(True)
        dialog.open()
        dialog.start()

    def login_closed(self, result):
        dialog = self.login_dialog
        self.login_dialog = None
        self.settings_page.login_button.set_loading(False)
        dialog.deleteLater()
        if self.closing:
            QTimer.singleShot(0, self.close)
        elif not dialog.authenticated:
            self.settings_page.password.setFocus()

    def start_aux(
        self, trigger, operation, success=None, failure=None, *, exclusive=False
    ):
        if (
            self.aux_worker is not None
            or self.closing
            or (exclusive and self.work_is_running())
        ):
            return
        self.aux_success = success
        self.aux_failure = failure or self.settings_page.settings_status.setText
        self.aux_button = trigger
        self.start_page.details.append(trigger.text() + " — rozpoczęto")
        trigger.set_loading(True)
        trigger.setEnabled(False)
        worker = Worker(operation, self)
        self.aux_worker = worker
        worker.success.connect(self.aux_succeeded)
        worker.failure.connect(self.aux_failed)
        worker.finished.connect(self.aux_finished)
        worker.start()
        self.update_action_states()

    def aux_succeeded(self, result):
        self.start_page.details.append(self.aux_button.text() + " — ukończono")
        if not self.closing and self.aux_success:
            self.aux_success(result)

    def aux_failed(self, message):
        self.start_page.details.append(self.aux_button.text() + " — " + message)
        if not self.closing:
            self.aux_failure(message)

    def aux_finished(self):
        worker, self.aux_worker = self.aux_worker, None
        worker.operation = None
        worker.deleteLater()
        self.aux_button.set_loading(False)
        self.aux_button.setEnabled(True)
        self.aux_button = self.aux_success = self.aux_failure = None
        self.update_action_states()
        self.close_if_idle()

    def closeEvent(self, event):
        if self.cancel_active_login():
            event.ignore()
            return
        if self.work_is_running():
            self.confirm_stop_work()
            event.ignore()
            return
        self.closing = True
        self.overview.shutdown()
        self.collector_status.shutdown()
        self.progress_timer.stop()
        self.data_page.query_pending = False
        self.data_page.query_serial += 1
        for worker in (self.data_page.query_worker, self.aux_worker):
            if worker is not None:
                worker.stop.set()
        if (
            self.data_page.query_worker is not None
            or self.aux_worker is not None
            or self.overview.busy
            or self.collector_status.busy
        ):
            self.start_page.status.setText("Zamykanie: zatrzymywanie odczytów w tle…")
            self.update_action_states()
            event.ignore()
            return
        if self.folder_dialog:
            self.folder_dialog.reject()
        event.accept()

    def close_if_idle(self):
        if self.closing:
            QTimer.singleShot(0, self.close)

    def cancel_active_login(self):
        dialog = self.login_dialog
        if dialog is None or not dialog.worker.isRunning():
            return False
        self.closing = True
        dialog.reject()
        return True

    def confirm_stop_work(self):
        if (
            not self.closing
            and QMessageBox.question(
                self, "Trwa operacja", "Zatrzymać operację i zamknąć aplikację?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.closing = True
        self.stop_work()
