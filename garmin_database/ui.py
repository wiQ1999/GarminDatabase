import argparse
import os
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .auth import GarminSource, SessionRequired, SessionStore
from .chart import Chart
from .exporter import Exporter
from .icons import icon, symbol
from .query import Queries
from .settings import Settings, application_dir
from .storage import Database
from .sync import Sync
from .util import Cancelled, check_stop, writer_lock, yesterday

STYLE = """
QWidget { background:#10141c; color:#e9eef5; font-family:'Segoe UI'; font-size:14px; }
QMainWindow { background:#10141c; }
QPushButton { background:#252d3a; border:1px solid #354154; border-radius:6px; padding:10px 16px; }
QPushButton:hover { background:#34445a; }
QPushButton:disabled { color:#778393; }
QPushButton[primary=true] { background:#1678c9; border-color:#268ddf; }
QLineEdit,QDateEdit,QSpinBox,QComboBox { background:#1c2330; border:1px solid #354154; border-radius:5px; padding:7px; }
QListWidget,QTextEdit { background:#191e27; border:1px solid #303947; border-radius:6px; }
QListWidget::item { padding:10px; }
QListWidget::item:selected { background:#164e7c; }
QProgressBar { border:1px solid #303947; border-radius:5px; text-align:center; min-height:22px; }
QProgressBar::chunk { background:#268ddf; }
QToolTip { background:#252d3a; color:white; border:1px solid #4fa4f3; }
"""


class Worker(QThread):
    success = Signal(object)
    failure = Signal(str)
    progress = Signal(str, str, int, int)
    mfa_requested = Signal()

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.stop = threading.Event()
        self.mfa_ready = threading.Event()
        self.code = None

    def ask_mfa(self):
        self.mfa_requested.emit()
        while not self.mfa_ready.wait(0.2):
            check_stop(self.stop)
        check_stop(self.stop)
        value = self.code
        self.code = None
        if not value:
            raise Cancelled()
        return value

    def run(self):
        try:
            self.success.emit(self.operation(self))
        except Cancelled:
            self.failure.emit("Zatrzymano. Ukończone dane zostały zachowane.")
        except Exception as error:
            self.failure.emit(
                str(error)
                if isinstance(error, SessionRequired)
                else "Operacja nie powiodła się: "
                + type(error).__name__
                + ". Sprawdź połączenie, sesję i katalog docelowy."
            )


def button(text, slot, primary=False):
    result = QPushButton(text)
    result.setProperty("primary", primary)
    result.clicked.connect(slot)
    return result


def date_edit(value):
    result = QDateEdit(QDate(value.year, value.month, value.day))
    result.setCalendarPopup(True)
    result.setDisplayFormat("yyyy-MM-dd")
    result.setMaximumDate(QDate(yesterday().year, yesterday().month, yesterday().day))
    return result


def selected_date(widget):
    return widget.date().toPython()


class Window(QMainWindow):
    def __init__(self, settings=None, settings_path=None):
        super().__init__()
        self.settings = settings or Settings.load()
        self.settings_path = settings_path
        if os.name == "nt" and not QFontDatabase.families():
            # Offscreen/sandboxed Windows can lack DirectWrite font enumeration.
            # Use the installed Windows font; do not distribute a copied font.
            QFontDatabase.addApplicationFont(
                str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf")
            )
        self.db = Database(self.settings.data_dir)
        with writer_lock(self.db.root):
            self.db.initialize()
        self.worker = None
        self.query_worker = None
        self.closing = False
        self.parameters = []
        self.query_pending = False
        self.query_serial = 0
        self.setWindowTitle("GarminDatabase")
        self.resize(1180, 800)
        self.setMinimumSize(900, 650)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(18, 18, 18, 18)
        nav = QVBoxLayout()
        brand = QLabel("GarminDatabase")
        brand.setStyleSheet("font-size:21px;font-weight:600;padding:14px 4px;")
        nav.addWidget(brand)
        self.navigation = QListWidget()
        self.navigation.addItems(["Start", "Dane", "Eksport", "Ustawienia"])
        self.navigation.setFixedWidth(185)
        nav.addWidget(self.navigation)
        nav.addWidget(QLabel("Archiwum dobrostanu\nDane z Garmin Connect"))
        row.addLayout(nav)
        self.pages = QStackedWidget()
        row.addWidget(self.pages, 1)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.build_start()
        self.build_data()
        self.build_export()
        self.build_settings()
        self.navigation.setCurrentRow(0)
        self.refresh()

    def page(self, title, description):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 8, 8, 8)
        label = QLabel(title)
        label.setStyleSheet("font-size:28px;font-weight:600;")
        layout.addWidget(label)
        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#a3afbf;padding-bottom:12px;")
        layout.addWidget(desc)
        self.pages.addWidget(widget)
        return layout

    def build_start(self):
        layout = self.page(
            "Twoje archiwum Garmin",
            "Pobieraj zakończone dni, sprawdzaj dostępność danych i stan importu.",
        )
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            "background:#191e27;padding:22px;border-radius:8px;font-size:16px;"
        )
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.download_button = button("Pobierz dane", self.sync, True)
        actions.addWidget(self.download_button)
        self.import_button = button(
            "Importuj lokalne archiwa", lambda: self.sync(local_only=True)
        )
        actions.addWidget(self.import_button)
        self.reprocess_button = button(
            "Przetwórz ponownie", lambda: self.sync(local_only=True, force=True)
        )
        actions.addWidget(self.reprocess_button)
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.stage = QLabel("Gotowe do pracy")
        layout.addWidget(self.stage)
        self.stop_button = button("Zatrzymaj", self.stop_work)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        self.details_button = button("Pokaż szczegóły", self.toggle_details)
        layout.addWidget(self.details_button)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.document().setMaximumBlockCount(500)
        self.details.hide()
        layout.addWidget(self.details)
        layout.addWidget(button("Odśwież stan", self.refresh))
        layout.addStretch()

    def build_data(self):
        layout = self.page(
            "Dane",
            "Wybierz parametr i okres. Podsumowania pochodzą wyłącznie z Garmin.",
        )
        row = QHBoxLayout()
        self.parameter_list = QListWidget()
        self.parameter_list.setMinimumWidth(240)
        self.parameter_list.setMaximumWidth(340)
        row.addWidget(self.parameter_list)
        right = QVBoxLayout()
        controls = QHBoxLayout()
        self.range = QComboBox()
        self.range.addItems(
            ["Dzień", "7 dni", "30 dni", "90 dni", "Cała historia", "Własny zakres"]
        )
        self.range.setCurrentIndex(2)
        controls.addWidget(self.range)
        self.chart_from = date_edit(yesterday() - timedelta(days=29))
        self.chart_to = date_edit(yesterday())
        controls.addWidget(self.chart_from)
        controls.addWidget(self.chart_to)
        right.addLayout(controls)
        right.addWidget(button("Pokaż wykres", self.load_chart, True))
        self.chart_title = QLabel("Wybierz parametr")
        right.addWidget(self.chart_title)
        self.chart = Chart()
        right.addWidget(self.chart, 1)
        self.chart_message = QLabel()
        self.chart_message.setWordWrap(True)
        right.addWidget(self.chart_message)
        row.addLayout(right, 1)
        layout.addLayout(row, 1)
        self.parameter_list.currentItemChanged.connect(lambda *a: self.load_chart())
        self.range.currentIndexChanged.connect(self.update_range)

    def build_export(self):
        layout = self.page(
            "Eksport dla AI",
            "JSON z wartościami źródłowymi. Kolejne generowanie zastępuje wyniki aplikacji.",
        )
        self.export_list = QListWidget()
        layout.addWidget(self.export_list, 1)
        actions = QHBoxLayout()
        actions.addWidget(
            button("Zaznacz wszystkie", lambda: self.select_exports(True))
        )
        actions.addWidget(
            button("Odznacz wszystkie", lambda: self.select_exports(False))
        )
        layout.addLayout(actions)
        form = QFormLayout()
        self.export_from = date_edit(date.fromisoformat(self.settings.history_from))
        self.export_to = date_edit(
            date.fromisoformat(self.settings.history_to)
            if self.settings.history_to
            else yesterday()
        )
        form.addRow("Historia od", self.export_from)
        form.addRow("Historia do", self.export_to)
        self.recent = QSpinBox()
        self.recent.setRange(1, 10000)
        self.recent.setValue(self.settings.recent_days)
        form.addRow("Szczegółowe ostatnie dni", self.recent)
        self.output = QLineEdit(self.settings.export_dir)
        form.addRow("Folder eksportu", self.output)
        layout.addLayout(form)
        self.full_samples = QCheckBox(
            "Eksportuj także pełne szczegółowe serie wskazanego okresu"
        )
        self.full_samples.setChecked(self.settings.full_samples)
        layout.addWidget(self.full_samples)
        buttons = QHBoxLayout()
        buttons.addWidget(
            button("Wybierz folder", lambda: self.pick_folder(self.output))
        )
        self.export_button = button("Generuj pliki JSON", self.export, True)
        buttons.addWidget(self.export_button)
        buttons.addWidget(
            button(
                "Otwórz folder eksportu",
                lambda: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(self.output.text())
                ),
            )
        )
        layout.addLayout(buttons)
        self.export_result = QLabel()
        self.export_result.setWordWrap(True)
        layout.addWidget(self.export_result)

    def build_settings(self):
        layout = self.page("Ustawienia", "Dane lokalne i połączenie z kontem Garmin.")
        form = QFormLayout()
        self.data_path = QLineEdit(self.settings.data_dir)
        form.addRow("Folder danych", self.data_path)
        self.email = QLineEdit()
        form.addRow("E-mail Garmin", self.email)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Hasło Garmin", self.password)
        layout.addLayout(form)
        layout.addWidget(
            button("Wybierz folder danych", lambda: self.pick_folder(self.data_path))
        )
        self.save_button = button("Zapisz ustawienia", self.save_settings, True)
        layout.addWidget(self.save_button)
        self.login_button = button("Zaloguj do Garmin", self.login)
        layout.addWidget(self.login_button)
        self.session_status = QLabel(
            (
                "Zapisana sesja Garmin jest dostępna. Jej ważność zostanie sprawdzona przy pobraniu. "
                if SessionStore().path.is_file()
                else "Brak zapisanej sesji Garmin. Zaloguj się, aby pobierać nowe dni. Lokalne archiwa można importować bez logowania. "
            )
            + "Sesja jest szyfrowana przez Windows DPAPI. Hasło i kod MFA nie są zapisywane."
        )
        self.session_status.setWordWrap(True)
        layout.addWidget(self.session_status)
        label = QLabel(
            "Ustawienia: "
            + str(self.settings_path or application_dir() / "settings.json")
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(QLabel("Strefa zakresu importu i wykresów: Europe/Warsaw"))
        layout.addStretch()

    def toggle_details(self):
        self.details.setVisible(not self.details.isVisible())

    def pick_folder(self, field):
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder", field.text())
        if folder:
            field.setText(folder)

    def select_exports(self, selected):
        for i in range(self.export_list.count()):
            self.export_list.item(i).setCheckState(
                Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked
            )

    def refresh(self):
        info = self.db.status()
        self.parameters = Queries(self.db).parameters()
        unresolved = sum(
            v
            for k, v in info["days"].items()
            if k not in {"downloaded", "empty_zip", "no_data_confirmed"}
        )
        self.status.setText(
            f"Ostatni pobrany dzień: {info['last_downloaded'] or 'brak'}\nZakres zarejestrowany w bazie: {info['first_day'] or 'brak'} — {info['last_day'] or 'brak'}\nArchiwa w bazie: {info['archives']}   •   Zaimportowane FIT: {info['files']}\nWiadomości: {info['messages']:,}   •   Fizyczne pola: {info['fields']:,}\nDni czekające na rejestrację: {info['pending_days']}   •   Oczekujące FIT: {info['pending_files']}\nDni brakujące / nierozstrzygnięte: {unresolved}   •   Nieznane warianty pól: {info['unknown_variants']}\nZIP w bazie: {info['archive_bytes'] / 1024**2:.1f} MB   •   SQLite: {info['database_bytes'] / 1024**2:.1f} MB"
        )
        self.status.setText(
            self.status.text()
            + f"\nRozpoznane serie / właściwości: {len(self.parameters)}"
        )
        selected = set(self.settings.parameters)
        self.parameter_list.blockSignals(True)
        self.parameter_list.clear()
        self.export_list.clear()
        previous_group = None
        for param in self.parameters:
            if param["group"] != previous_group:
                header = QListWidgetItem(param["group"])
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.parameter_list.addItem(header)
                previous_group = param["group"]
            item = QListWidgetItem(icon(symbol(param)), param["label"])
            item.setData(Qt.ItemDataRole.UserRole, param)
            item.setToolTip(param["original"])
            self.parameter_list.addItem(item)
            ex = QListWidgetItem(
                icon(symbol(param)), param["label"] + " — " + param["group"]
            )
            ex.setData(Qt.ItemDataRole.UserRole, param)
            ex.setFlags(ex.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            ex.setCheckState(
                Qt.CheckState.Checked
                if not selected or param["key"] in selected
                else Qt.CheckState.Unchecked
            )
            self.export_list.addItem(ex)
        self.parameter_list.blockSignals(False)

    def update_range(self):
        option = self.range.currentText()
        if option in ["Dzień", "7 dni", "30 dni", "90 dni"]:
            days = {"Dzień": 1, "7 dni": 7, "30 dni": 30, "90 dni": 90}[option]
            self.chart_from.setDate(self.chart_to.date().addDays(-(days - 1)))
        elif option == "Cała historia":
            first = self.db.status()["first_day"]
            if first:
                d = date.fromisoformat(first)
                self.chart_from.setDate(QDate(d.year, d.month, d.day))
        self.load_chart()

    def load_chart(self):
        item = self.parameter_list.currentItem()
        param = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not param:
            return
        self.query_serial += 1
        if self.query_worker and self.query_worker.isRunning():
            self.query_pending = True
            return
        serial = self.query_serial
        if self.range.currentText() != "Własny zakres":
            end = selected_date(self.chart_to)
            name = self.range.currentText()
            if name in ["Dzień", "7 dni", "30 dni", "90 dni"]:
                days = {"Dzień": 1, "7 dni": 7, "30 dni": 30, "90 dni": 90}[name]
                self.chart_from.setDate(self.chart_to.date().addDays(1 - days))
        start = selected_date(self.chart_from)
        end = selected_date(self.chart_to)
        if start > end:
            self.chart_message.setText("Data początkowa jest późniejsza niż końcowa")
            return
        self.chart_title.setText(param["label"] + " • " + param["original"])
        self.chart_message.setText("Odczytywanie wybranego parametru…")
        db = self.db
        worker = Worker(lambda w: Queries(db).chart(param, start, end), self)
        self.query_worker = worker
        worker.success.connect(
            lambda result: (
                self.show_chart(result, param) if serial == self.query_serial else None
            )
        )
        worker.failure.connect(self.chart_message.setText)

        def release_query():
            if self.query_worker is worker:
                self.query_worker = None
            worker.deleteLater()
            if self.query_pending:
                self.query_pending = False
                QTimer.singleShot(0, self.load_chart)

        worker.finished.connect(release_query)
        worker.start()

    def show_chart(self, result, param):
        self.chart.set_series(result[0], param["unit"], param["enum"])
        self.chart_message.setText(result[1])

    def start_work(self, operation):
        if self.worker and self.worker.isRunning():
            return
        worker = Worker(operation, self)
        self.worker = worker
        worker.progress.connect(self.on_progress)
        worker.failure.connect(self.on_failure)
        worker.success.connect(self.on_success)
        worker.finished.connect(self.work_finished)
        worker.mfa_requested.connect(self.mfa)
        for b in [
            self.download_button,
            self.import_button,
            self.reprocess_button,
            self.export_button,
            self.login_button,
            self.save_button,
        ]:
            b.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.stage.setText("Rozpoczynanie…")
        worker.start()

    def on_progress(self, day, stage, index, total):
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(index)
        self.stage.setText(f"{day} — {stage} ({index}/{total})")
        self.details.append(self.stage.text())

    def stop_work(self):
        if self.worker:
            self.worker.stop.set()
            self.stage.setText("Zatrzymywanie w bezpiecznym punkcie…")

    def on_failure(self, message):
        self.stage.setText(message)
        self.details.append(message)
        self.details.show()

    def on_success(self, result):
        self.stage.setText(
            "Ukończono"
            if not isinstance(result, int) or result == 0
            else f"Ukończono z błędami: {result}"
        )
        if isinstance(result, dict):
            self.export_result.setText(
                "Wygenerowano: "
                + ", ".join(f"{k} ({v / 1024:.1f} KB)" for k, v in result.items())
            )
        if result == "login":
            self.session_status.setText(
                "Zalogowano. Sesja została zaszyfrowana i zapisana."
            )

    def work_finished(self):
        for b in [
            self.download_button,
            self.import_button,
            self.reprocess_button,
            self.export_button,
            self.login_button,
            self.save_button,
        ]:
            b.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.refresh()
        if self.worker:
            self.worker.operation = (
                None  # release closures that may contain credentials
            )
        if self.closing:
            QTimer.singleShot(0, self.close)

    def sync(self, local_only=False, force=False):
        db = self.db
        self.start_work(
            lambda w: Sync(
                db, None if local_only else GarminSource(), self.settings.delay
            ).run(
                date(2024, 1, 1),
                yesterday(),
                w.stop,
                w.progress.emit,
                local_only,
                force,
            )
        )

    def login(self):
        email = self.email.text().strip()
        password = self.password.text()
        self.password.clear()
        if not email or not password:
            self.session_status.setText("Podaj e-mail i hasło")
            return

        def operation(w):
            source = GarminSource()
            source.login(email, password, w.ask_mfa)
            return "login"

        self.start_work(operation)

    def mfa(self):
        value, ok = QInputDialog.getText(
            self,
            "Garmin — uwierzytelnienie",
            "Podaj kod MFA",
            QLineEdit.EchoMode.Password,
        )
        self.worker.code = value if ok else None
        self.worker.mfa_ready.set()

    def export(self):
        params = [
            self.export_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.export_list.count())
            if self.export_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not params:
            self.export_result.setText("Wybierz co najmniej jeden parametr")
            return
        start = selected_date(self.export_from)
        end = selected_date(self.export_to)
        output = self.output.text()
        recent = self.recent.value()
        full = self.full_samples.isChecked()
        db = self.db
        self.settings.parameters = [p["key"] for p in params]
        self.settings.history_from = start.isoformat()
        self.settings.history_to = end.isoformat()
        self.settings.export_dir = output
        self.settings.recent_days = recent
        self.settings.full_samples = full
        try:
            self.settings.save(self.settings_path)
        except Exception as e:
            self.export_result.setText(
                "Nie można zapisać ustawień: " + type(e).__name__
            )
            return
        self.start_work(
            lambda w: Exporter(db).generate(
                output, params, start, end, recent, w.stop, full, w.progress.emit
            )
        )

    def save_settings(self):
        old = self.settings.data_dir
        try:
            db = Database(self.data_path.text())
            with writer_lock(db.root):
                db.initialize()
            self.settings.data_dir = self.data_path.text()
            self.settings.export_dir = self.output.text()
            self.settings.save(self.settings_path)
            self.db = db
            self.refresh()
            self.session_status.setText("Ustawienia zapisane")
        except Exception as e:
            self.settings.data_dir = old
            self.session_status.setText(
                "Nie można zapisać ustawień: " + type(e).__name__
            )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            if (
                not self.closing
                and QMessageBox.question(
                    self, "Trwa operacja", "Zatrzymać operację i zamknąć aplikację?"
                )
                != QMessageBox.StandardButton.Yes
            ):
                event.ignore()
                return
            self.closing = True
            self.stop_work()
            event.ignore()
            return
        if self.query_worker and self.query_worker.isRunning():
            self.query_worker.wait()
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--settings-file")
    parser.add_argument("--smoke-screenshot")
    args = parser.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("GarminDatabase")
    try:
        settings = Settings.load(args.settings_file)
        if args.data_dir:
            settings.data_dir = args.data_dir
        window = Window(settings, args.settings_file)
        window.show()
        if args.smoke_screenshot:

            def snapshot():
                window.grab().save(args.smoke_screenshot)
                window.close()

            QTimer.singleShot(1000, snapshot)
        return app.exec()
    except Exception as error:
        if args.smoke_screenshot:
            from .util import atomic_json

            atomic_json(
                Path(args.smoke_screenshot).with_suffix(".error.json"),
                {"type": type(error).__name__, "module": getattr(error, "name", None)},
            )
            return 1
        QMessageBox.critical(
            None,
            "GarminDatabase",
            "Nie można uruchomić aplikacji: " + type(error).__name__,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
