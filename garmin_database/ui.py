import argparse
import json
import os
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QSignalBlocker, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .auth import GarminSource, SessionRequired, SessionStore
from .chart import Chart, ChartView
from .exporter import Exporter, ExportResult
from .icons import icon, symbol
from .login_dialog import LoginDialog
from .mcp_config import client_config
from .query import Queries
from .settings import Settings, application_dir
from .storage import Database
from .summaries import MEAN_PARAMETERS, has_chart_summary, summary_method
from .sync import Sync
from .util import Cancelled, check_stop, yesterday

STYLE = """
QWidget { background:#10141c; color:#e9eef5; font-family:'Segoe UI'; font-size:14px; }
QMainWindow { background:#10141c; }
QPushButton { background:#252d3a; border:1px solid #354154; border-radius:6px; padding:10px 16px; }
QPushButton:hover { background:#34445a; }
QPushButton:disabled { color:#778393; }
QPushButton[primary=true] { background:#1678c9; border-color:#268ddf; }
QLineEdit,QDateEdit,QSpinBox,QComboBox { background:#1c2330; border:1px solid #354154; border-radius:5px; padding:7px; }
QDateEdit:disabled { color:#778393; }
QCheckBox:disabled { color:#778393; }
QComboBox QAbstractItemView::item:disabled { color:#778393; }
QListWidget,QTextEdit { background:#191e27; border:1px solid #303947; border-radius:6px; }
QListWidget::item { padding:10px; }
QListWidget::item:selected { background:#164e7c; }
QProgressBar { border:1px solid #303947; border-radius:5px; text-align:center; min-height:22px; }
QProgressBar::chunk { background:#268ddf; }
QToolTip { background:#252d3a; color:white; border:1px solid #4fa4f3; }
QGroupBox { border:1px solid #303947; border-radius:8px; margin-top:12px; padding:16px; }
QGroupBox::title { subcontrol-origin:margin; left:14px; padding:0 6px; color:#e9eef5; font-weight:600; }
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
        self.code = None
        self.mfa_ready.clear()
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
            check_stop(self.stop)
            result = self.operation(self)
            check_stop(self.stop)
            self.success.emit(result)
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
        self.db = Database(self.settings.data_dir, self.settings.database_dsn)
        with self.db.writer_lock():
            self.db.initialize()
        self.worker = None
        self.login_dialog = None
        self.query_worker = None
        self.closing = False
        self.parameters = []
        self.query_pending = False
        self.query_serial = 0
        self.last_export_dir = None
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
            "Wybierz parametr i okres. Podsumowania Garmin lub oznaczone średnie dzienne aplikacji.",
        )
        row = QHBoxLayout()
        self.parameter_list = QListWidget()
        self.parameter_list.setMinimumWidth(240)
        self.parameter_list.setMaximumWidth(340)
        row.addWidget(self.parameter_list)
        right = QVBoxLayout()
        controls = QHBoxLayout()
        self.range = QComboBox()
        self.range.setItemDelegate(QStyledItemDelegate(self.range))
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
        self.trend = QCheckBox("Linia trendu")
        self.trend.setToolTip(
            "Regresja liniowa względem czasu dla widocznych poprawnych wartości liczbowych. "
            "Obliczana tylko na wykresie; nie jest podsumowaniem Garmin i nie trafia do eksportu."
        )
        self.trend.setEnabled(False)
        right.addWidget(self.trend)
        self.chart_title = QLabel("Wybierz parametr")
        right.addWidget(self.chart_title)
        self.chart = Chart()
        self.chart_view = ChartView(self.chart)
        right.addWidget(self.chart_view, 1)
        self.chart_message = QLabel()
        self.chart_message.setWordWrap(True)
        right.addWidget(self.chart_message)
        row.addLayout(right, 1)
        layout.addLayout(row, 1)
        self.parameter_list.currentItemChanged.connect(self.parameter_changed)
        self.range.currentIndexChanged.connect(self.update_range)
        self.chart_from.dateChanged.connect(self.update_range)
        self.chart_to.dateChanged.connect(self.update_range)
        self.trend.toggled.connect(self.chart.set_trend_visible)

    def build_export(self):
        layout = self.page(
            "Eksport dla AI",
            "Historia podsumowań i pełne szczegóły — osobne pliki dla każdego parametru. Każdy eksport ma nowy folder.",
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
        self.summary_period = QComboBox()
        self.summary_period.addItem("Dzienne (zalecane)", "day")
        self.summary_period.addItem("Miesięczne", "month")
        self.summary_period.setCurrentIndex(
            0 if self.settings.summary_period == "day" else 1
        )
        self.summary_period.setToolTip(
            "Dotyczy obliczonych podsumowań. Podsumowania Garmin zachowują oryginalną postać."
        )
        form.addRow("Podsumowania historii", self.summary_period)
        self.output = QLineEdit(self.settings.export_dir)
        form.addRow("Folder na eksporty", self.output)
        layout.addLayout(form)
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
                    QUrl.fromLocalFile(str(self.last_export_dir or self.output.text()))
                ),
            )
        )
        layout.addLayout(buttons)
        self.export_result = QLabel()
        self.export_result.setWordWrap(True)
        layout.addWidget(self.export_result)

    def build_settings(self):
        outer = self.page(
            "Ustawienia", "Dane lokalne, udostępnianie i połączenie z Garmin."
        )
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setStyleSheet("QScrollArea { border:0; }")
        outer.addWidget(scroll)
        self.build_storage_settings(
            self.settings_section(layout, "Dane lokalne i PostgreSQL")
        )
        self.build_login_settings(
            self.settings_section(layout, "Logowanie do Garmin Connect")
        )
        self.build_sharing(self.settings_section(layout, "Udostępnianie danych"))
        layout.addStretch()
        footer = QHBoxLayout()
        self.settings_status = QLabel()
        self.settings_status.setWordWrap(True)
        footer.addWidget(self.settings_status, 1)
        self.save_button = button("Zapisz ustawienia", self.save_settings, True)
        footer.addWidget(self.save_button)
        outer.addLayout(footer)

    def settings_section(self, layout, title):
        group = QGroupBox(title)
        section = QVBoxLayout(group)
        section.setSpacing(12)
        layout.addWidget(group)
        return section

    def build_storage_settings(self, layout):
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.data_path = QLineEdit(self.settings.data_dir)
        self.data_path.setCursorPosition(0)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.data_path, 1)
        self.browse_data_button = button(
            "Wybierz…", lambda: self.pick_folder(self.data_path)
        )
        self.browse_data_button.setAccessibleName("Wybierz folder danych")
        self.browse_data_button.setToolTip("Wybierz folder danych")
        folder_row.addWidget(self.browse_data_button)
        form.addRow("Folder danych", folder_row)
        self.database_dsn = QLineEdit(self.settings.database_dsn)
        self.database_dsn.setCursorPosition(0)
        self.database_dsn.setPlaceholderText(
            "host=localhost port=5432 dbname=garmin user=garmin"
        )
        self.database_dsn.setToolTip(
            "Parametry PostgreSQL bez hasła. Hasło: pgpass; puste pole: GARMIN_DATABASE_DSN / libpq."
        )
        form.addRow("Połączenie PostgreSQL", self.database_dsn)
        layout.addLayout(form)
        label = QLabel(
            "Ustawienia: "
            + str(self.settings_path or application_dir() / "settings.json")
        )
        label.setWordWrap(True)
        label.setStyleSheet("color:#a3afbf;")
        layout.addWidget(label)
        layout.addWidget(QLabel("Strefa zakresu importu i wykresów: Europe/Warsaw"))

    def build_login_settings(self, layout):
        garmin_account = QLabel(
            "Login i hasło do konta "
            '<a href="https://connect.garmin.com/" style="color:#4fa4f3;">'
            "Garmin Connect (connect.garmin.com)</a>."
        )
        garmin_account.setOpenExternalLinks(True)
        garmin_account.setWordWrap(True)
        layout.addWidget(garmin_account)
        form = QFormLayout()
        self.email = QLineEdit()
        form.addRow("E-mail Garmin", self.email)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Hasło Garmin", self.password)
        layout.addLayout(form)
        self.login_button = button("Zaloguj do Garmin", self.login)
        actions = QHBoxLayout()
        actions.addWidget(self.login_button)
        actions.addStretch()
        layout.addLayout(actions)
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

    def build_sharing(self, layout):
        layout.addWidget(
            QLabel("Niezależny wybór parametrów dla eksportu i lokalnego MCP.")
        )
        self.mcp_enabled = QCheckBox("Zezwalaj na odczyt przez lokalny MCP")
        self.mcp_enabled.setChecked(self.settings.mcp_enabled)
        layout.addWidget(self.mcp_enabled)
        self.sharing_group = QComboBox()
        self.sharing_group.addItem("Wszystkie grupy", "")
        self.sharing_group.currentIndexChanged.connect(self.filter_sharing)
        layout.addWidget(self.sharing_group)
        self.sharing_table = QTableWidget(0, 5)
        self.sharing_table.setHorizontalHeaderLabels(
            ["Parametr", "Jednostka", "Eksport", "MCP", "Podsumowanie"]
        )
        self.sharing_table.setMinimumHeight(210)
        self.sharing_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.sharing_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.sharing_table)
        for column, name in [(2, "Eksport"), (3, "MCP")]:
            actions = QHBoxLayout()
            actions.addWidget(
                button(
                    name + ": zaznacz grupę",
                    lambda checked=False, c=column: self.select_sharing(c, True),
                )
            )
            actions.addWidget(
                button(
                    name + ": odznacz grupę",
                    lambda checked=False, c=column: self.select_sharing(c, False),
                )
            )
            layout.addLayout(actions)
        actions = QHBoxLayout()
        actions.addWidget(
            button("Kopiuj Eksport → MCP", lambda: self.copy_sharing(2, 3))
        )
        actions.addWidget(
            button("Kopiuj MCP → Eksport", lambda: self.copy_sharing(3, 2))
        )
        layout.addLayout(actions)
        layout.addWidget(
            button("Skopiuj konfigurację klienta MCP", self.copy_mcp_config)
        )
        layout.addWidget(
            QLabel(
                "Zapisz ustawienia, aby zastosować wybór. Proces MCP uruchamia klient."
            )
        )

    def refresh_sharing(self):
        groups = sorted({p["group"] for p in self.parameters})
        with QSignalBlocker(self.sharing_group):
            self.sharing_group.clear()
            self.sharing_group.addItem("Wszystkie grupy", "")
            for group in groups:
                self.sharing_group.addItem(group, group)
        self.sharing_table.setRowCount(len(self.parameters))
        methods = {
            "sample_mean": "Średnia próbek",
            "garmin": "Źródłowe Garmin",
            "value_counts": "Liczności kategorii",
            "last_observed": "Ostatnia obserwacja",
        }
        for row, param in enumerate(self.parameters):
            label = QTableWidgetItem(param["label"])
            label.setData(Qt.ItemDataRole.UserRole, param)
            label.setToolTip(param["key"])
            self.sharing_table.setItem(row, 0, label)
            self.sharing_table.setItem(row, 1, QTableWidgetItem(param["unit"] or "—"))
            self.sharing_table.setItem(
                row, 4, QTableWidgetItem(methods[summary_method(param)])
            )
            for column, channel in [(2, "export"), (3, "mcp")]:
                self.sharing_table.setItem(
                    row, column, self.sharing_checkbox(param, channel)
                )
            for column in (0, 1, 4):
                self.sharing_table.item(row, column).setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.filter_sharing()

    def sharing_checkbox(self, param, channel):
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        supported = channel == "export" or param["key"] in MEAN_PARAMETERS
        if not supported:
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setToolTip(
                "Ten parametr nie jest obsługiwany przez pierwszą wersję MCP."
            )
        selected = param["key"] in (
            getattr(self.settings, channel + "_parameters") or []
        )
        item.setCheckState(
            Qt.CheckState.Checked if selected and supported else Qt.CheckState.Unchecked
        )
        return item

    def filter_sharing(self):
        group = self.sharing_group.currentData()
        for row in range(self.sharing_table.rowCount()):
            param = self.sharing_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.sharing_table.setRowHidden(
                row, bool(group and param["group"] != group)
            )

    def select_sharing(self, column, selected):
        for row in range(self.sharing_table.rowCount()):
            item = self.sharing_table.item(row, column)
            if (
                not self.sharing_table.isRowHidden(row)
                and item.flags() & Qt.ItemFlag.ItemIsEnabled
            ):
                item.setCheckState(
                    Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked
                )

    def copy_sharing(self, source, target):
        for row in range(self.sharing_table.rowCount()):
            item = self.sharing_table.item(row, target)
            if (
                not self.sharing_table.isRowHidden(row)
                and item.flags() & Qt.ItemFlag.ItemIsEnabled
            ):
                item.setCheckState(self.sharing_table.item(row, source).checkState())

    def sharing_keys(self, column):
        return [
            self.sharing_table.item(row, 0).data(Qt.ItemDataRole.UserRole)["key"]
            for row in range(self.sharing_table.rowCount())
            if self.sharing_table.item(row, column).checkState()
            == Qt.CheckState.Checked
        ]

    def copy_mcp_config(self):
        QApplication.clipboard().setText(
            json.dumps(client_config(self.settings_path), ensure_ascii=False, indent=2)
        )

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
        if self.settings.migrate(self.parameters):
            self.settings.save(self.settings_path)
        self.refresh_sharing()
        self.update_status(info)
        self.populate_parameters()

    def update_status(self, info):
        unresolved = sum(
            v
            for k, v in info["days"].items()
            if k not in {"downloaded", "empty_zip", "no_data_confirmed"}
        )
        self.status.setText(
            f"Ostatni pobrany dzień: {info['last_downloaded'] or 'brak'}\nZakres zarejestrowany w bazie: {info['first_day'] or 'brak'} — {info['last_day'] or 'brak'}\nArchiwa w bazie: {info['archives']}   •   Zaimportowane FIT: {info['files']}\nWiadomości: {info['messages']:,}   •   Fizyczne pola: {info['fields']:,}\nDni czekające na rejestrację: {info['pending_days']}   •   Oczekujące FIT: {info['pending_files']}\nDni brakujące / nierozstrzygnięte: {unresolved}   •   Nieznane warianty pól: {info['unknown_variants']}\nZIP w bazie: {info['archive_bytes'] / 1024**2:.1f} MB   •   PostgreSQL: {info['database_bytes'] / 1024**2:.1f} MB"
        )
        self.status.setText(
            self.status.text()
            + f"\nRozpoznane serie / właściwości: {len(self.parameters)}"
        )

    def populate_parameters(self):
        selected = set(self.settings.parameters)
        previous = self.selected_parameter()
        previous_key = previous["key"] if previous else None
        selected_row = None
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
            if selected_row is None or param["key"] == previous_key:
                selected_row = self.parameter_list.count() - 1
            self.add_export_parameter(param, selected)
        if selected_row is not None:
            self.parameter_list.setCurrentRow(selected_row)
        self.parameter_list.blockSignals(False)
        self.parameter_changed()

    def add_export_parameter(self, param, selected):
        if param["key"] not in self.settings.export_parameters:
            return
        item = QListWidgetItem(
            icon(symbol(param)), param["label"] + " — " + param["group"]
        )
        item.setData(Qt.ItemDataRole.UserRole, param)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked
            if param["key"] in selected
            else Qt.CheckState.Unchecked
        )
        self.export_list.addItem(item)

    def selected_parameter(self):
        item = self.parameter_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def parameter_changed(self):
        parameter = self.selected_parameter()
        summaries = parameter and has_chart_summary(parameter)
        for index in range(self.range.count()):
            enabled = bool(summaries) or index == 0
            item = self.range.model().item(index)
            item.setEnabled(enabled)
            item.setForeground(QBrush(QColor("#e9eef5" if enabled else "#778393")))
        self.range.setToolTip(
            ""
            if summaries
            else "Ten parametr ma tylko dane szczegółowe. Dostępny jest zakres Dzień."
        )
        self.update_range()

    def update_range(self):
        """Przeglądanie i ograniczenia zakresów: docs/11-desktop-ui.md."""
        parameter = self.selected_parameter()
        summaries = parameter and has_chart_summary(parameter)
        if not summaries and self.range.currentIndex() != 0:
            with QSignalBlocker(self.range):
                self.range.setCurrentIndex(0)
        option = self.range.currentText()
        self.chart_from.setEnabled(bool(summaries) and option == "Własny zakres")
        with QSignalBlocker(self.chart_from):
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
        param = self.selected_parameter()
        self.query_serial += 1
        serial = self.query_serial
        if not param:
            self.query_pending = False
            self.show_chart_error("Wybierz parametr")
            self.chart_title.setText("Wybierz parametr")
            return
        start = selected_date(self.chart_from)
        end = selected_date(self.chart_to)
        if start > end:
            self.query_pending = False
            self.show_chart_error("Data początkowa jest późniejsza niż końcowa")
            return
        self.chart_title.setText(param["label"] + " • " + param["original"])
        self.chart_message.setText("Odczytywanie wybranego parametru…")
        self.chart_view.set_loading(True)
        self.trend.setEnabled(False)
        if self.query_worker is not None:
            self.query_pending = True
            return
        db = self.db
        worker = Worker(lambda w: Queries(db).chart(param, start, end), self)
        self.query_worker = worker
        worker.success.connect(
            lambda result: (
                self.show_chart(result, param) if serial == self.query_serial else None
            )
        )
        worker.failure.connect(
            lambda message: (
                self.show_chart_error(message) if serial == self.query_serial else None
            )
        )

        def release_query():
            if self.query_worker is worker:
                self.query_worker = None
            worker.deleteLater()
            if self.query_pending:
                self.query_pending = False
                self.load_chart()

        worker.finished.connect(release_query)
        worker.start()

    def show_chart(self, result, param):
        self.chart.set_series(result[0], param["unit"], param["enum"])
        self.chart_view.set_loading(False)
        self.trend.setEnabled(bool(self.chart.trend_points))
        if not self.chart.trend_points:
            self.trend.setChecked(False)
        self.chart_message.setText(result[1])

    def show_chart_error(self, message):
        self.chart.set_series([])
        self.chart_view.set_loading(False)
        self.trend.setEnabled(False)
        self.trend.setChecked(False)
        self.chart_message.setText(message)

    def start_work(self, operation):
        if self.work_is_running():
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

    def work_is_running(self):
        return self.worker is not None and self.worker.isRunning()

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
        if isinstance(result, ExportResult):
            self.last_export_dir = result.directory
            self.export_result.setText(
                f"Folder: {result.directory}\nWygenerowano {len(result.files)} plików danych "
                + f"({sum(result.files.values()) / 1024:.1f} KB). Historia: history; szczegóły: details."
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
        if self.login_dialog is not None:
            self.login_dialog.raise_()
            self.login_dialog.activateWindow()
            return
        if self.work_is_running():
            return
        email = self.email.text().strip()
        password = self.password.text()
        self.password.clear()
        if not email or not password:
            self.session_status.setText("Podaj e-mail i hasło")
            return

        def operation(w):
            source = GarminSource()
            source.login(email, password, w.ask_mfa, stop=w.stop)
            return "login"

        dialog = LoginDialog(Worker(operation), self)
        self.login_dialog = dialog
        dialog.status_changed.connect(self.session_status.setText)
        dialog.finished.connect(self.login_closed)
        dialog.open()
        dialog.start()

    def login_closed(self, result):
        dialog = self.login_dialog
        self.login_dialog = None
        dialog.deleteLater()
        if self.closing:
            QTimer.singleShot(0, self.close)
        elif not dialog.authenticated:
            self.password.setFocus()

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
        period = self.summary_period.currentData()
        db = self.db
        self.settings.parameters = [p["key"] for p in params]
        self.settings.history_from = start.isoformat()
        self.settings.history_to = end.isoformat()
        self.settings.export_dir = output
        self.settings.recent_days = recent
        self.settings.summary_period = period
        try:
            self.settings.save(self.settings_path)
        except Exception as e:
            self.export_result.setText(
                "Nie można zapisać ustawień: " + type(e).__name__
            )
            return
        self.export_result.setText("Generowanie podsumowań i szczegółów…")
        self.start_work(
            lambda w: Exporter(db, self.settings, self.settings_path).generate(
                output, params, start, end, recent, w.stop, period, w.progress.emit
            )
        )
        self.worker.failure.connect(self.export_result.setText)

    def save_settings(self):
        old = (
            self.settings.data_dir,
            self.settings.database_dsn,
            self.settings.export_dir,
        )
        try:
            from dataclasses import replace

            candidate = replace(
                self.settings,
                data_dir=self.data_path.text(),
                database_dsn=self.database_dsn.text(),
                export_dir=self.output.text(),
                export_parameters=self.sharing_keys(2),
                mcp_parameters=self.sharing_keys(3),
                mcp_enabled=self.mcp_enabled.isChecked(),
            )
            candidate.validate()
            db = Database(candidate.data_dir, candidate.database_dsn)
            with db.writer_lock():
                db.initialize()
            candidate.save(self.settings_path)
            self.settings = candidate
            self.db = db
            self.refresh()
            self.settings_status.setText("Ustawienia zapisane")
        except Exception as e:
            (
                self.settings.data_dir,
                self.settings.database_dsn,
                self.settings.export_dir,
            ) = old
            self.settings_status.setText(
                "Nie można zapisać ustawień: " + type(e).__name__
            )

    def closeEvent(self, event):
        if self.cancel_active_login():
            event.ignore()
            return
        if self.work_is_running():
            self.confirm_stop_work()
            event.ignore()
            return
        if self.query_worker and self.query_worker.isRunning():
            self.query_worker.wait()
        event.accept()

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
