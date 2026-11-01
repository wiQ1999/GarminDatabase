"""SettingsPage view and its local interactions."""

import json
from dataclasses import replace
from datetime import date

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.collector import CollectorPanel
from garmin_database.adapters.inbound.mcp.client_config import client_config
from garmin_database.application.mcp_metrics import MCP_PARAMETERS
from garmin_database.domain.aggregation import (
    summary_method,
)

from .widgets import button, date_edit, page_layout, selected_date


class SettingsPage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        outer = page_layout(
            self, "Ustawienia", "Dane lokalne, udostępnianie i połączenie z Garmin."
        )
        self.settings_tabs = QTabWidget()
        outer.addWidget(self.settings_tabs, 1)
        sections = []
        for title in ("Ogólne", "Automatyczne pobieranie", "Garmin", "Udostępnianie"):
            content = QWidget()
            section = QVBoxLayout(content)
            section.setContentsMargins(0, 0, 8, 0)
            section.setSpacing(20)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content)
            scroll.setStyleSheet("QScrollArea { border:0; }")
            self.settings_tabs.addTab(scroll, title)
            sections.append(section)
        self.build_storage_settings(
            self.settings_section(sections[0], "Dane lokalne i PostgreSQL")
        )
        self.collector_panel = CollectorPanel(host)
        self.settings_section(sections[1], "Automatyczne pobieranie").addWidget(
            self.collector_panel
        )
        self.build_login_settings(
            self.settings_section(sections[2], "Logowanie do Garmin Connect")
        )
        self.build_sharing(self.settings_section(sections[3], "Udostępnianie danych"))
        for section in sections:
            section.addStretch()
        self.open_config_button = button(
            "Otwórz folder konfiguracji", self.open_config_folder
        )
        outer.addWidget(self.open_config_button, 0, Qt.AlignmentFlag.AlignLeft)
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
        self.data_path = QLineEdit(self.host.settings.data_dir)
        self.data_path.setCursorPosition(0)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.data_path, 1)
        self.browse_data_button = button(
            "Wybierz…",
            lambda: self.host.pick_folder(self.data_path, self.browse_data_button),
        )
        self.browse_data_button.setAccessibleName("Wybierz folder danych")
        self.browse_data_button.setToolTip("Wybierz folder danych")
        folder_row.addWidget(self.browse_data_button)
        form.addRow("Folder danych", folder_row)
        self.database_dsn = QLineEdit(self.host.settings.database_dsn)
        self.database_dsn.setCursorPosition(0)
        self.database_dsn.setPlaceholderText(
            "host=localhost port=5432 dbname=garmin user=garmin"
        )
        self.database_dsn.setToolTip(
            "Parametry PostgreSQL bez hasła. Hasło: pgpass; puste pole: GARMIN_DATABASE_DSN / libpq."
        )
        form.addRow("Połączenie PostgreSQL", self.database_dsn)
        self.download_from = date_edit(
            date.fromisoformat(self.host.settings.download_from)
        )
        form.addRow("Początek pobierania z Garmin", self.download_from)
        self.refresh_seconds = QSpinBox()
        self.refresh_seconds.setRange(5, 3600)
        self.refresh_seconds.setSuffix(" s")
        self.refresh_seconds.setValue(self.host.settings.refresh_seconds)
        form.addRow("Odświeżanie stanu bazy i kolektora", self.refresh_seconds)
        layout.addLayout(form)
        layout.addWidget(QLabel("Strefa zakresu importu i wykresów: Europe/Warsaw"))

    def open_config_folder(self):
        path = self.host.services.settings_store.location(
            self.host.settings_path
        ).parent
        self.host.start_aux(
            self.open_config_button, lambda worker: self.host.services.open_folder(path)
        )

    def build_login_settings(self, layout):
        garmin_account = QLabel(
            "Login i hasło do konta "
            '<a href="https://connect.garmin.com/" style="color:#4fa4f3;">'
            "Garmin Connect (connect.garmin.com)</a>."
        )
        garmin_account.setOpenExternalLinks(False)
        garmin_account.linkActivated.connect(self.host.open_link)
        garmin_account.setWordWrap(True)
        layout.addWidget(garmin_account)
        form = QFormLayout()
        self.email = QLineEdit()
        self.login_target = QComboBox()
        self.login_target.addItem("Aplikacja — pobieranie ręczne", "application")
        self.login_target.addItem("Kolektor — aktualne konto Windows", "collector")
        form.addRow("Sesja Garmin", self.login_target)
        form.addRow("E-mail Garmin", self.email)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Hasło Garmin", self.password)
        layout.addLayout(form)
        self.login_button = button("Zaloguj do Garmin", self.host.login)
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
        self.mcp_enabled.setChecked(self.host.settings.mcp_enabled)
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
        self.sharing_table.setAlternatingRowColors(True)
        self.sharing_table.setShowGrid(False)
        self.sharing_table.verticalHeader().hide()
        self.sharing_table.verticalHeader().setDefaultSectionSize(36)
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
        groups = sorted({p["group"] for p in self.host.parameters})
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
        self.sharing_table.setRowCount(len(self.host.parameters))
        methods = {
            "sample_mean": "Średnia próbek",
            "garmin": "Źródłowe Garmin",
            "value_counts": "Liczności kategorii",
            "last_observed": "Ostatnia obserwacja",
        }
        for row, param in enumerate(self.host.parameters):
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
        supported = channel == "export" or param["key"] in MCP_PARAMETERS
        if not supported:
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setToolTip(
                "Ten parametr nie jest obsługiwany przez pierwszą wersję MCP."
            )
        selected = param["key"] in (
            getattr(self.host.settings, channel + "_parameters") or []
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
        store, path = self.host.services.settings_store, self.host.settings_path
        self.host.start_aux(
            self.copy_config_button,
            lambda w: json.dumps(
                client_config(store.location(path)), ensure_ascii=False, indent=2
            ),
            lambda text: QApplication.clipboard().setText(text),
        )

    def save_settings(self):
        candidate = replace(
            self.host.settings,
            data_dir=self.data_path.text(),
            database_dsn=self.database_dsn.text(),
            download_from=selected_date(self.download_from).isoformat(),
            export_dir=self.host.export_page.output.text(),
            export_parameters=self.sharing_keys(2),
            mcp_parameters=self.sharing_keys(3),
            mcp_enabled=self.mcp_enabled.isChecked(),
            refresh_seconds=self.refresh_seconds.value(),
        )
        previous, path = self.host.services, self.host.settings_path

        def operation(worker):
            candidate.validate()
            services = previous.reconfigure(candidate)
            services.settings_store.save(candidate, path)
            return candidate, services

        def apply(result):
            candidate, services = result
            changed_database = (candidate.data_dir, candidate.database_dsn) != (
                self.host.settings.data_dir,
                self.host.settings.database_dsn,
            )
            self.host.settings = candidate
            self.host.services = services
            self.host.data_page.query_serial += 1
            self.host.data_page.query_pending = False
            if self.host.data_page.query_worker is not None:
                self.host.data_page.query_worker.stop.set()
            if changed_database:
                self.host.parameters = []
                self.host.status_info = {}
                self.host.start_page.status.setText("Odczytywanie stanu nowej bazy…")
                self.host.state_error = self.host.catalog_error = ""
                self.host.catalog_loaded = False
                self.host.start_page.show_overview_errors()
                self.refresh_sharing(preserve=False)
                self.host.data_page.populate_parameters(preserve=False)
                self.host.data_page.show_chart_error(
                    "Odczytywanie katalogu nowej bazy…"
                )
            else:
                self.host.data_page.populate_parameters(preserve=False)
            self.host.overview.configure(services, candidate)
            self.host.collector_status.generation += 1
            self.host.start_page.refresh_note.setText(
                f"Automatyczne odświeżanie co {candidate.refresh_seconds} s"
            )
            self.settings_status.setText("Ustawienia zapisane")

        self.settings_status.setText("Sprawdzanie połączenia i zapisywanie ustawień…")
        self.host.start_aux(
            self.save_button,
            operation,
            apply,
            self.settings_status.setText,
            exclusive=True,
        )
