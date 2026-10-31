"""Independent, paced, read-only diagnostics for the collector page."""

from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from garmin_database.adapters.inbound.desktop.busy import BusyButton
from garmin_database.adapters.inbound.desktop.workers import Worker
from garmin_database.application.collector_messages import OUTCOME_LABELS


def local_time(value):
    if not value:
        return "brak"
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(ZoneInfo("Europe/Warsaw"))
        .strftime("%Y-%m-%d %H:%M %z")
    )


class CollectorStatusPanel(QWidget):
    idle = Signal()

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.worker = None
        self.generation = 0
        self.stopped = False
        layout = QVBoxLayout(self)
        self.message = QLabel("Odczytywanie stanu kolektora…")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        form = QFormLayout()
        self.values = {}
        for key, label in [
            ("account", "Konto systemowe"),
            ("next", "Następny termin"),
            ("started", "Ostatnie rozpoczęcie"),
            ("finished", "Ostatnie zakończenie"),
            ("success", "Ostatni sukces"),
            ("pause", "Oczekiwanie do"),
        ]:
            self.values[key] = QLabel("brak")
            form.addRow(label, self.values[key])
        layout.addLayout(form)
        self.refresh_button = BusyButton("Odśwież stan i log")
        self.refresh_button.clicked.connect(self.poll)
        layout.addWidget(self.refresh_button)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.document().setMaximumBlockCount(500)
        layout.addWidget(self.log_view, 1)

    @property
    def busy(self):
        return self.worker is not None

    def poll(self):
        if (
            self.stopped
            or self.busy
            or not self.host.isVisible()
            or self.host.isMinimized()
        ):
            return
        manager = self.host.services.collector_manager(
            self.host.collector_panel.path.text()
        )
        generation = self.generation

        def read(worker):
            try:
                config = manager.files.load_config()
            except FileNotFoundError:
                return None
            return config, manager.status(config), manager.files.logs(config)

        def accept(result):
            if not self.stopped and generation == self.generation:
                self.render(result)

        def failed(message):
            if not self.stopped and generation == self.generation:
                self.message.setText(
                    "Nie udało się odczytać stanu kolektora. " + message
                )

        worker = Worker(read, self)
        self.worker = worker
        worker.success.connect(accept)
        worker.failure.connect(failed)
        worker.finished.connect(self.release)
        self.refresh_button.set_loading(True)
        self.refresh_button.setEnabled(False)
        worker.start()

    def render(self, result):
        if result is None:
            self.message.setText(
                "Kolektor nie jest skonfigurowany. Otwórz Ustawienia → Automatyczne pobieranie."
            )
            self.log_view.setPlainText("Brak logów kolektora")
            for value in self.values.values():
                value.setText("brak")
            return
        config, result, log = result
        task, state = result["schedule"], result["state"]
        registration = "niezarejestrowany"
        if task["installed"]:
            registration = "aktywny" if task["enabled"] else "wyłączony"
            if not task["revision_matches"]:
                registration += "; zmiany niezastosowane"
        outcome = OUTCOME_LABELS.get(state["outcome"], "nieznany stan")
        self.message.setText(f"Harmonogram: {registration}. Ostatni wynik: {outcome}.")
        self.values["account"].setText(config.run_as)
        for key, value in [
            ("next", result["next_run"]),
            ("started", state.get("started_at")),
            ("finished", state.get("finished_at")),
            ("success", state.get("last_success")),
            ("pause", state.get("not_before")),
        ]:
            self.values[key].setText(local_time(value))
        self.log_view.setPlainText(log)

    def release(self):
        worker, self.worker = self.worker, None
        worker.operation = None
        worker.deleteLater()
        self.refresh_button.set_loading(False)
        self.refresh_button.setEnabled(True)
        self.idle.emit()

    def shutdown(self):
        self.stopped = True
        if self.worker is not None:
            self.worker.stop.set()
