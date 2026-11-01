"""ExportPage view and its local interactions."""

from dataclasses import replace
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.icons import (
    icon,
    symbol,
)
from garmin_database.domain.time import today

from .widgets import button, date_edit, page_layout, selected_date


class ExportPage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.last_export_dir = None
        layout = page_layout(
            self,
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
        self.export_from = date_edit(
            date.fromisoformat(self.host.settings.history_from)
        )
        self.export_to = date_edit(
            date.fromisoformat(self.host.settings.history_to)
            if self.host.settings.history_to
            else today()
        )
        form.addRow("Historia od", self.export_from)
        form.addRow("Historia do", self.export_to)
        self.recent = QSpinBox()
        self.recent.setRange(1, 10000)
        self.recent.setValue(self.host.settings.recent_days)
        form.addRow("Szczegółowe ostatnie dni", self.recent)
        self.summary_period = QComboBox()
        self.summary_period.addItem("Dzienne (zalecane)", "day")
        self.summary_period.addItem("Miesięczne", "month")
        self.summary_period.setCurrentIndex(
            0 if self.host.settings.summary_period == "day" else 1
        )
        self.summary_period.setToolTip(
            "Dotyczy obliczonych podsumowań. Podsumowania Garmin zachowują oryginalną postać."
        )
        form.addRow("Podsumowania historii", self.summary_period)
        self.output = QLineEdit(self.host.settings.export_dir)
        form.addRow("Folder na eksporty", self.output)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.browse_export_button = button(
            "Wybierz folder",
            lambda: self.host.pick_folder(self.output, self.browse_export_button),
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

    def open_export_folder(self):
        services = self.host.services
        path = str(self.last_export_dir or self.output.text())
        self.host.start_aux(
            self.open_export_button,
            lambda w: services.open_folder(path),
            failure=self.export_result.setText,
        )

    def select_exports(self, selected):
        for i in range(self.export_list.count()):
            self.export_list.item(i).setCheckState(
                Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked
            )

    def export_selection(self):
        return {
            self.export_list.item(i).data(Qt.ItemDataRole.UserRole)["key"]
            for i in range(self.export_list.count())
            if self.export_list.item(i).checkState() == Qt.CheckState.Checked
        }

    def add_export_parameter(self, param, selected):
        if param["key"] not in self.host.settings.export_parameters:
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
        if start > end:
            self.export_result.setText(
                "Początek zakresu nie może być późniejszy niż koniec"
            )
            return
        output = self.output.text()
        recent = self.recent.value()
        period = self.summary_period.currentData()
        db = self.host.services
        settings = replace(
            self.host.settings,
            parameters=[p["key"] for p in params],
            history_from=start.isoformat(),
            history_to=end.isoformat(),
            export_dir=output,
            recent_days=recent,
            summary_period=period,
        )
        path = self.host.settings_path

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
        if self.host.start_work(operation, self.export_button):
            self.host.settings = self.host.overview.settings = settings
            self.host.worker.failure.connect(self.export_result.setText)
