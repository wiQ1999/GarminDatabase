import json
import os
from collections import deque
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFontDatabase
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
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.busy import BusyButton, BusyIndicator
from garmin_database.adapters.inbound.desktop.chart import (
    Chart,
    ChartView,
    prepare_series,
)
from garmin_database.adapters.inbound.desktop.icons import (
    application_icon,
    icon,
    symbol,
)
from garmin_database.adapters.inbound.desktop.login_dialog import LoginDialog
from garmin_database.adapters.inbound.desktop.overview import OverviewPoller
from garmin_database.adapters.inbound.desktop.parameter_help import parameter_help
from garmin_database.adapters.inbound.mcp.client_config import client_config
from garmin_database.application.dto import ExportResult, SyncSummary
from garmin_database.application.ports import DesktopServices
from garmin_database.application.sync_messages import sync_heading, sync_summary_text
from garmin_database.domain.aggregation import (
    MEAN_PARAMETERS,
    has_chart_summary,
    summary_method,
)
from garmin_database.domain.time import today

from .workers import Worker

STYLE = """
QWidget { background:#10141c; color:#e9eef5; font-family:'Segoe UI'; font-size:14px; }
QMainWindow { background:#10141c; }
QPushButton { background:#252d3a; border:1px solid #354154; border-radius:6px; padding:10px 16px; }
QPushButton:hover { background:#34445a; }
QPushButton:disabled { color:#778393; }
QPushButton[loading=true] { padding-right:34px; }
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


def button(text, slot, primary=False):
    result = BusyButton(text)
    result.setProperty("primary", primary)
    result.clicked.connect(slot)
    return result


def date_edit(value):
    result = QDateEdit(QDate(value.year, value.month, value.day))
    result.setCalendarPopup(True)
    result.setDisplayFormat("yyyy-MM-dd")
    result.setMaximumDate(QDate(today().year, today().month, today().day))
    return result


def selected_date(widget):
    return widget.date().toPython()


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
        self.query_worker = None
        self.aux_worker = None
        self.aux_button = None
        self.operation_button = None
        self.folder_dialog = None
        self.closing = False
        self.parameters = []
        self.query_pending = False
        self.query_serial = 0
        self.chart_dirty = True
        self.status_info = {}
        self.state_error = ""
        self.catalog_error = ""
        self.catalog_loaded = False
        self.session_cached = None
        self.progress_pending = None
        self.progress_details = deque(maxlen=500)
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(100)
        self.progress_timer.timeout.connect(self.flush_progress)
        self.last_export_dir = None
        self.setWindowTitle("GarminDatabase")
        self.setWindowIcon(application_icon())
        self.resize(1180, 800)
        self.setMinimumSize(900, 650)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(18, 18, 18, 18)
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
        self.navigation.addItems(["Start", "Dane", "Eksport", "Ustawienia"])
        self.navigation.setFixedWidth(185)
        nav.addWidget(self.navigation)
        nav.addWidget(QLabel("Archiwum dobrostanu\nDane z Garmin Connect"))
        row.addLayout(nav)
        self.pages = QStackedWidget()
        row.addWidget(self.pages, 1)
        self.navigation.currentRowChanged.connect(self.page_changed)
        self.build_start()
        self.build_data()
        self.build_export()
        self.build_settings()
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
        self.overview.busy_changed.connect(self.status_indicator.set_loading)
        self.overview.busy_changed.connect(self.update_action_states)
        self.overview.idle.connect(self.close_if_idle)
        QTimer.singleShot(0, self.refresh)

    def page_changed(self, index):
        self.pages.setCurrentIndex(index)
        if index == 1 and self.chart_dirty:
            self.load_chart()

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
            "Pobieraj dane do dzisiaj, sprawdzaj dostępność danych i stan importu.",
        )
        self.status = QLabel()
        self.status.setText("Odczytywanie stanu archiwum…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            "background:#191e27;padding:22px;border-radius:8px;font-size:16px;"
        )
        layout.addWidget(self.status)
        state_header = QHBoxLayout()
        state_header.addWidget(
            QLabel("Stan aktualizuje się automatycznie co 15 sekund")
        )
        state_header.addStretch()
        self.status_indicator = BusyIndicator(self)
        state_header.addWidget(self.status_indicator)
        layout.addLayout(state_header)
        self.status_error = QLabel()
        self.status_error.setWordWrap(True)
        self.status_error.setStyleSheet("color:#ffbc70;")
        self.status_error.hide()
        layout.addWidget(self.status_error)
        actions = QHBoxLayout()
        self.download_button = button("Pobierz nowe dane", self.sync, True)
        actions.addWidget(self.download_button)
        self.download_all_button = button("Pobierz wszystko", lambda: self.sync(refresh_all=True))
        actions.addWidget(self.download_all_button)
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.stage = QLabel("Gotowe do pracy")
        self.stage.setWordWrap(True)
        layout.addWidget(self.stage)
        self.stop_button = button("Zatrzymaj", self.stop_work)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        layout.addWidget(QLabel("Dziennik operacji"))
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName("Dziennik operacji")
        self.details.setPlaceholderText(
            "Tutaj pojawi się postęp pobierania, importu i eksportu."
        )
        self.details.setMinimumHeight(100)
        self.details.document().setMaximumBlockCount(500)
        layout.addWidget(self.details, 1)

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
        layout.addWidget(QLabel("Dane bieżącego dnia mogą być niepełne do kolejnej synchronizacji."))
        self.chart_from = date_edit(today() - timedelta(days=29))
        self.chart_to = date_edit(today())
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
        self.chart.setMinimumHeight(240)
        self.chart_view = ChartView(self.chart)
        right.addWidget(self.chart_view, 1)
        self.chart_message = QLabel()
        self.chart_message.setWordWrap(True)
        right.addWidget(self.chart_message)
        self.parameter_help = QTextBrowser()
        self.parameter_help.setAccessibleName("Wyjaśnienie parametru Garmin")
        self.parameter_help.setMinimumHeight(100)
        self.parameter_help.setMaximumHeight(150)
        self.parameter_help.setOpenLinks(False)
        self.parameter_help.setOpenExternalLinks(False)
        self.parameter_help.anchorClicked.connect(
            lambda url: self.open_link(url.toString())
        )
        self.parameter_help.setHtml(parameter_help(None))
        right.addWidget(self.parameter_help)
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
            else today()
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
        self.browse_export_button = button(
            "Wybierz folder",
            lambda: self.pick_folder(self.output, self.browse_export_button),
        )
        buttons.addWidget(self.browse_export_button)
        self.export_button = button("Generuj pliki JSON", self.export, True)
        buttons.addWidget(self.export_button)
        self.open_export_button = button(
            "Otwórz folder eksportu", self.open_export_folder
        )
        buttons.addWidget(self.open_export_button)
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
            "Wybierz…",
            lambda: self.pick_folder(self.data_path, self.browse_data_button),
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
            + str(self.services.settings_store.location(self.settings_path))
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
        garmin_account.setOpenExternalLinks(False)
        garmin_account.linkActivated.connect(self.open_link)
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
        self.session_status = QLabel("Sprawdzanie dostępności zapisanej sesji Garmin…")
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
        self.copy_config_button = button(
            "Skopiuj konfigurację klienta MCP", self.copy_mcp_config
        )
        layout.addWidget(self.copy_config_button)
        layout.addWidget(
            QLabel(
                "Zapisz ustawienia, aby zastosować wybór. Proces MCP uruchamia klient."
            )
        )

    def refresh_sharing(self, preserve=True):
        previous_group = self.sharing_group.currentData()
        previous = self.sharing_selection() if preserve else {}
        groups = sorted({p["group"] for p in self.parameters})
        with QSignalBlocker(self.sharing_group):
            self.sharing_group.clear()
            self.sharing_group.addItem("Wszystkie grupy", "")
            for group in groups:
                self.sharing_group.addItem(group, group)
            self.sharing_group.setCurrentIndex(
                max(0, self.sharing_group.findData(previous_group))
            )
        self.sharing_table.setUpdatesEnabled(False)
        self.sharing_table.setRowCount(0)
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
                item = self.sharing_checkbox(param, channel)
                if (
                    param["key"] in previous
                    and item.flags() & Qt.ItemFlag.ItemIsEnabled
                ):
                    item.setCheckState(previous[param["key"]][column - 2])
                self.sharing_table.setItem(row, column, item)
            for column in (0, 1, 4):
                self.sharing_table.item(row, column).setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.filter_sharing()
        self.sharing_table.setUpdatesEnabled(True)

    def sharing_selection(self):
        return {
            self.sharing_table.item(row, 0).data(Qt.ItemDataRole.UserRole)["key"]: (
                self.sharing_table.item(row, 2).checkState(),
                self.sharing_table.item(row, 3).checkState(),
            )
            for row in range(self.sharing_table.rowCount())
        }

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
        store, path = self.services.settings_store, self.settings_path
        self.start_aux(
            self.copy_config_button,
            lambda w: json.dumps(
                client_config(store.location(path)), ensure_ascii=False, indent=2
            ),
            lambda text: QApplication.clipboard().setText(text),
        )

    def open_export_folder(self):
        services = self.services
        path = str(self.last_export_dir or self.output.text())
        self.start_aux(
            self.open_export_button,
            lambda w: services.open_folder(path),
            failure=self.export_result.setText,
        )

    def open_link(self, url):
        services = self.services
        self.start_aux(self.login_button, lambda w: services.open_url(url))

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

    def select_exports(self, selected):
        for i in range(self.export_list.count()):
            self.export_list.item(i).setCheckState(
                Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked
            )

    def refresh(self):
        self.overview.request()

    def show_overview(self, result):
        self.status_info = result["status"]
        self.state_error = ""
        if "catalog_revision" in result:
            self.catalog_error = ""
            self.catalog_loaded = True
        self.show_overview_errors()
        if "settings" in result:
            self.settings = result["settings"]
        parameters = result["parameters"]
        if parameters is not None and parameters != self.parameters:
            self.parameters = parameters
            self.refresh_sharing()
            self.populate_parameters()
        self.update_status(self.status_info)
        available = result["session_available"]
        if available != self.session_cached and self.login_dialog is None:
            self.session_cached = available
            self.session_status.setText(
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
                self.status.setText("Stan archiwum jest chwilowo niedostępny.")
            self.show_overview_errors()

    def overview_catalog_error(self, message):
        if not self.closing:
            self.catalog_error = (
                "Nie udało się odczytać listy parametrów. Kolejna próba nastąpi automatycznie.\n"
                + message
            )
            self.show_overview_errors()
            if self.status_info:
                self.update_status(self.status_info)

    def show_overview_errors(self):
        message = "\n".join(
            error for error in (self.state_error, self.catalog_error) if error
        )
        self.status_error.setText(message)
        self.status_error.setVisible(bool(message))

    def update_status(self, info):
        unresolved = sum(
            v
            for k, v in info["days"].items()
            if k not in {"downloaded", "empty_zip", "no_data_confirmed"}
        )
        self.status.setText(
            f"Ostatni pobrany dzień: {info['last_downloaded'] or 'brak'}\nZakres zarejestrowany w bazie: {info['first_day'] or 'brak'} — {info['last_day'] or 'brak'}\nArchiwa w bazie: {info['archives']}   •   Zaimportowane FIT: {info['files']}\nWiadomości: {info['messages']:,}   •   Fizyczne pola: {info['fields']:,}\nDni czekające na rejestrację: {info['pending_days']}   •   Oczekujące FIT: {info['pending_files']}\nDni brakujące / nierozstrzygnięte: {unresolved}   •   Nieznane warianty pól: {info['unknown_variants']}\nRozmiar zarejestrowanych ZIP: {info['archive_bytes'] / 1024**2:.1f} MB   •   PostgreSQL: {info['database_bytes'] / 1024**2:.1f} MB"
        )
        count = (
            str(len(self.parameters))
            if self.catalog_loaded
            else "oczekiwanie na listę parametrów"
        )
        self.status.setText(
            self.status.text() + "\nRozpoznane serie / właściwości: " + count
        )

    def populate_parameters(self, preserve=True):
        selected = (
            self.export_selection()
            if preserve and self.export_list.count()
            else set(self.settings.parameters)
        )
        previous = self.selected_parameter()
        previous_key = previous["key"] if previous else None
        selected_row = None
        self.parameter_list.blockSignals(True)
        self.parameter_list.setUpdatesEnabled(False)
        self.export_list.setUpdatesEnabled(False)
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
        self.parameter_list.setUpdatesEnabled(True)
        self.export_list.setUpdatesEnabled(True)
        self.parameter_changed()

    def export_selection(self):
        return {
            self.export_list.item(i).data(Qt.ItemDataRole.UserRole)["key"]
            for i in range(self.export_list.count())
            if self.export_list.item(i).checkState() == Qt.CheckState.Checked
        }

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
        self.parameter_help.setHtml(parameter_help(parameter))
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
                first = self.status_info.get("first_day")
                if first:
                    d = date.fromisoformat(first)
                    self.chart_from.setDate(QDate(d.year, d.month, d.day))
        self.load_chart()

    def load_chart(self):
        if self.closing:
            return
        self.chart_dirty = False
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
        db = self.services

        def query(worker):
            points, message = db.chart(param, start, end, worker.stop)
            return points, message, prepare_series(points, param["enum"])

        worker = Worker(query, self)
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
            worker.operation = None
            worker.deleteLater()
            if self.query_pending and not self.closing:
                self.query_pending = False
                self.load_chart()
            self.close_if_idle()

        worker.finished.connect(release_query)
        worker.start()

    def show_chart(self, result, param):
        self.chart.set_series(
            result[0],
            param["unit"],
            param["enum"],
            prepared=result[2] if len(result) > 2 else None,
        )
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

    def update_action_states(self, *args):
        busy = self.work_is_running() or self.aux_worker is not None or self.closing
        for b in (
            self.download_button,
            self.download_all_button,
            self.export_button,
            self.login_button,
            self.save_button,
        ):
            b.setEnabled(not busy)
        if hasattr(self, "overview") and (
            not self.overview.initialized
            or (self.overview.busy and self.settings.settings_version == 1)
        ):
            self.save_button.setEnabled(False)
            self.export_button.setEnabled(False)
        self.stop_button.setEnabled(self.work_is_running() and not self.closing)

    def start_work(self, operation, trigger=None):
        if self.work_is_running() or self.aux_worker is not None or self.closing:
            return False
        if self.worker is not None:
            self.worker.deleteLater()
        worker = Worker(operation, self)
        self.worker = worker
        worker.progress.connect(self.on_progress)
        worker.failure.connect(self.on_failure)
        worker.success.connect(self.on_success)
        worker.finished.connect(self.work_finished)
        self.operation_button = trigger
        if trigger:
            trigger.set_loading(True)
        self.stage.setText("Rozpoczynanie…")
        self.details.clear()
        self.progress_pending = None
        self.progress_details.clear()
        self.progress.setRange(0, 0)
        self.stop_button.set_loading(False)
        self.progress_timer.start()
        worker.start()
        self.update_action_states()
        return True

    def work_is_running(self):
        return self.worker is not None and self.worker.isRunning()

    def on_progress(self, day, stage, index, total):
        self.progress_pending = (day, stage, index, total)
        self.progress_details.append(f"{day} — {stage} ({index}/{total})")

    def flush_progress(self):
        if self.progress_pending is None:
            return
        day, stage, index, total = self.progress_pending
        self.progress_pending = None
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(index)
        if not self.worker or not self.worker.stop.is_set():
            self.stage.setText(f"{day} — {stage} ({index}/{total})")
        self.details.append("\n".join(self.progress_details))
        self.progress_details.clear()

    def stop_work(self):
        if self.worker:
            self.worker.stop.set()
            self.stop_button.set_loading(True)
            self.stage.setText("Zatrzymywanie w bezpiecznym punkcie…")

    def on_failure(self, message):
        self.flush_progress()
        self.stage.setText(message)
        self.details.append(message)

    def on_success(self, result):
        self.flush_progress()
        if isinstance(result, SyncSummary):
            self.stage.setText(sync_heading(result))
            self.details.append(sync_summary_text(result))
            return
        self.stage.setText(
            "Ukończono"
            if not isinstance(result, int) or result == 0
            else f"Podsumowanie całej operacji: zgłoszono problemy: {result}. Szczegóły w dzienniku operacji."
        )
        self.details.append(self.stage.text())
        if isinstance(result, ExportResult):
            self.last_export_dir = result.directory
            self.export_result.setText(
                f"Folder: {result.directory}\nWygenerowano {len(result.files)} plików danych "
                + f"({sum(result.files.values()) / 1024:.1f} KB). Historia: history; szczegóły: details."
            )

    def work_finished(self):
        self.progress_timer.stop()
        if self.operation_button:
            self.operation_button.set_loading(False)
        self.operation_button = None
        self.progress.setRange(0, max(1, self.progress.maximum()))
        self.stop_button.setEnabled(False)
        self.stop_button.set_loading(False)
        self.update_action_states()
        self.chart_dirty = True
        if self.worker:
            self.worker.operation = (
                None  # release closures that may contain credentials
            )
        self.close_if_idle()

    def sync(self, refresh_all=False):
        db = self.services
        delay = self.settings.delay
        trigger = self.download_all_button if refresh_all else self.download_button
        self.start_work(
            lambda w: db.sync(
                date(2024, 1, 1), today(), w.stop, w.progress.emit,
                delay=delay, detailed=True, refresh_all=refresh_all,
            ), trigger,
        )

    def login(self):
        if self.login_dialog is not None:
            self.login_dialog.raise_()
            self.login_dialog.activateWindow()
            return
        if self.work_is_running() or self.aux_worker is not None or self.closing:
            return
        email = self.email.text().strip()
        password = self.password.text()
        self.password.clear()
        if not email or not password:
            self.session_status.setText("Podaj e-mail i hasło")
            return

        def operation(w):
            return self.services.login(
                email, password, w.ask_mfa, w.stop, w.login_stage.emit
            )

        dialog = LoginDialog(Worker(operation), self)
        self.login_dialog = dialog
        dialog.status_changed.connect(self.session_status.setText)
        dialog.status_changed.connect(self.details.append)
        dialog.finished.connect(self.login_closed)
        self.login_button.set_loading(True)
        dialog.open()
        dialog.start()

    def login_closed(self, result):
        dialog = self.login_dialog
        self.login_dialog = None
        self.login_button.set_loading(False)
        dialog.deleteLater()
        if self.closing:
            QTimer.singleShot(0, self.close)
        elif not dialog.authenticated:
            self.password.setFocus()

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
        db = self.services
        settings = replace(
            self.settings,
            parameters=[p["key"] for p in params],
            history_from=start.isoformat(),
            history_to=end.isoformat(),
            export_dir=output,
            recent_days=recent,
            summary_period=period,
        )
        path = self.settings_path

        def operation(worker):
            db.settings_store.save(settings, path)
            return db.export(settings, path).generate(
                output,
                params,
                start,
                end,
                recent,
                worker.stop,
                period,
                worker.progress.emit,
            )

        self.export_result.setText("Generowanie podsumowań i szczegółów…")
        if self.start_work(operation, self.export_button):
            self.settings = self.overview.settings = settings
            self.worker.failure.connect(self.export_result.setText)

    def save_settings(self):
        candidate = replace(
            self.settings,
            data_dir=self.data_path.text(),
            database_dsn=self.database_dsn.text(),
            export_dir=self.output.text(),
            export_parameters=self.sharing_keys(2),
            mcp_parameters=self.sharing_keys(3),
            mcp_enabled=self.mcp_enabled.isChecked(),
        )
        previous, path = self.services, self.settings_path

        def operation(worker):
            candidate.validate()
            services = previous.reconfigure(candidate)
            services.settings_store.save(candidate, path)
            return candidate, services

        def apply(result):
            candidate, services = result
            changed_database = (candidate.data_dir, candidate.database_dsn) != (
                self.settings.data_dir,
                self.settings.database_dsn,
            )
            self.settings = candidate
            self.services = services
            self.query_serial += 1
            self.query_pending = False
            if self.query_worker is not None:
                self.query_worker.stop.set()
            if changed_database:
                self.parameters = []
                self.status_info = {}
                self.status.setText("Odczytywanie stanu nowej bazy…")
                self.state_error = self.catalog_error = ""
                self.catalog_loaded = False
                self.show_overview_errors()
                self.refresh_sharing(preserve=False)
                self.populate_parameters(preserve=False)
                self.show_chart_error("Odczytywanie katalogu nowej bazy…")
            else:
                self.populate_parameters(preserve=False)
            self.overview.configure(services, candidate)
            self.settings_status.setText("Ustawienia zapisane")

        self.settings_status.setText("Sprawdzanie połączenia i zapisywanie ustawień…")
        self.start_aux(
            self.save_button,
            operation,
            apply,
            self.settings_status.setText,
            exclusive=True,
        )

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
        self.aux_failure = failure or self.settings_status.setText
        self.aux_button = trigger
        self.details.append(trigger.text() + " — rozpoczęto")
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
        self.details.append(self.aux_button.text() + " — ukończono")
        if not self.closing and self.aux_success:
            self.aux_success(result)

    def aux_failed(self, message):
        self.details.append(self.aux_button.text() + " — " + message)
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
        self.progress_timer.stop()
        self.query_pending = False
        self.query_serial += 1
        for worker in (self.query_worker, self.aux_worker):
            if worker is not None:
                worker.stop.set()
        if (
            self.query_worker is not None
            or self.aux_worker is not None
            or self.overview.busy
        ):
            self.status.setText("Zamykanie: zatrzymywanie odczytów w tle…")
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
