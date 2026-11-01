"""DataPage view and its local interactions."""

from datetime import date, timedelta

from PySide6.QtCore import QDate, QSignalBlocker, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.chart import (
    Chart,
    ChartView,
    prepare_series,
)
from garmin_database.adapters.inbound.desktop.icons import (
    icon,
    symbol,
)
from garmin_database.adapters.inbound.desktop.parameter_help import parameter_help
from garmin_database.domain.aggregation import (
    has_chart_summary,
)
from garmin_database.domain.time import today

from .widgets import date_edit, page_layout, selected_date
from .workers import Worker


class DataPage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.query_worker = None
        self.query_pending = False
        self.query_serial = 0
        self.chart_dirty = True
        layout = page_layout(
            self,
            "Dane",
            "Wybierz parametr i okres. Podsumowania Garmin lub oznaczone średnie dzienne aplikacji.",
        )
        row = QHBoxLayout()
        self.parameter_list = QListWidget()
        self.parameter_list.setMinimumWidth(240)
        self.parameter_list.setMaximumWidth(340)
        row.addWidget(self.parameter_list)
        right = QVBoxLayout()
        right.setSpacing(8)
        controls = QHBoxLayout()
        self.range = QComboBox()
        self.range.setItemDelegate(QStyledItemDelegate(self.range))
        self.range.addItems(
            ["Dzień", "7 dni", "30 dni", "90 dni", "Cała historia", "Własny zakres"]
        )
        self.range.setCurrentIndex(2)
        controls.addWidget(self.range)
        layout.addWidget(
            QLabel("Dane bieżącego dnia mogą być niepełne do kolejnej synchronizacji.")
        )
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
        self.chart_title.setStyleSheet("font-size:18px;font-weight:600;")
        right.addWidget(self.chart_title)
        self.chart = Chart()
        self.chart.setMinimumHeight(240)
        self.chart_view = ChartView(self.chart)
        self.chart_view.setMinimumHeight(240)
        right.addWidget(self.chart_view, 1)
        self.chart_message = QLabel()
        self.chart_message.setWordWrap(True)
        right.addWidget(self.chart_message)
        self.parameter_help = QTextBrowser()
        self.parameter_help.setAccessibleName("Wyjaśnienie parametru Garmin")
        self.parameter_help.setMinimumHeight(100)
        self.parameter_help.setMaximumHeight(120)
        self.parameter_help.setOpenLinks(False)
        self.parameter_help.setOpenExternalLinks(False)
        self.parameter_help.anchorClicked.connect(
            lambda url: self.host.open_link(url.toString())
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

    def populate_parameters(self, preserve=True):
        selected = (
            self.host.export_page.export_selection()
            if preserve and self.host.export_page.export_list.count()
            else set(self.host.settings.parameters)
        )
        previous = self.selected_parameter()
        previous_key = previous["key"] if previous else None
        selected_row = None
        self.parameter_list.blockSignals(True)
        self.parameter_list.setUpdatesEnabled(False)
        self.host.export_page.export_list.setUpdatesEnabled(False)
        self.parameter_list.clear()
        self.host.export_page.export_list.clear()
        previous_group = None
        for param in self.host.parameters:
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
            self.host.export_page.add_export_parameter(param, selected)
        if selected_row is not None:
            self.parameter_list.setCurrentRow(selected_row)
        self.parameter_list.blockSignals(False)
        self.parameter_list.setUpdatesEnabled(True)
        self.host.export_page.export_list.setUpdatesEnabled(True)
        self.parameter_changed()

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
                first = self.host.status_info.get("first_day")
                if first:
                    d = date.fromisoformat(first)
                    self.chart_from.setDate(QDate(d.year, d.month, d.day))
        self.load_chart()

    def load_chart(self):
        if self.host.closing:
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
        db = self.host.services

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
            if self.query_pending and not self.host.closing:
                self.query_pending = False
                self.load_chart()
            self.host.close_if_idle()

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
