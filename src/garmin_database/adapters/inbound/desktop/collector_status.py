"""Independent, paced, read-only diagnostics for the collector page."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from garmin_database.adapters.inbound.desktop.busy import BusyButton
from garmin_database.adapters.inbound.desktop.workers import Worker
from garmin_database.application.collector_log import outcome_message, readable_log
from garmin_database.application.collector_messages import OUTCOME_LABELS
from garmin_database.application.time_presentation import display_time


class CollectorStatusPanel(QWidget):
    idle = Signal()

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.worker = None
        self.generation = 0
        self.stopped = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.message = QLabel("Odczytywanie stanu kolektora…")
        self.message.setWordWrap(True)
        self.message.setStyleSheet(
            "background:#191e27;padding:20px;border-radius:10px;font-size:16px;"
        )
        layout.addWidget(self.message)
        form = QFormLayout()
        self.values = {}
        for key, label in [
            ("account", "Konto systemowe"),
            ("logon", "Tryb uruchamiania"),
            ("next", "Następny termin"),
            ("started", "Ostatnie rozpoczęcie"),
            ("finished", "Ostatnie zakończenie"),
            ("success", "Ostatni sukces"),
            ("pause", "Oczekiwanie do"),
        ]:
            self.values[key] = QLabel("brak")
            self.values[key].setWordWrap(True)
            form.addRow(label, self.values[key])
        layout.addLayout(form)
        self.refresh_button = BusyButton("Odśwież stan i log")
        self.refresh_button.clicked.connect(self.poll)
        layout.addWidget(self.refresh_button)
        layout.addWidget(QLabel("Dziennik kolektora"))
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
        panel = self.host.collector_panel
        if panel.config is None and not panel.edited:
            panel._loaded(config)
        task, state = result["schedule"], result["state"]
        registration = "niezarejestrowany"
        if task.get("error") == "access_denied":
            registration = "brak dostępu do istniejącego zadania; zainstaluj / zaktualizuj kolektor, aby naprawić uprawnienia"
        elif task["installed"]:
            registration = "aktywny" if task["enabled"] else "wyłączony"
            if not task["revision_matches"]:
                registration += "; zmiany niezastosowane"
        outcome = OUTCOME_LABELS.get(state["outcome"], "nieznany stan")
        if state["outcome"] == "issues" and state.get("summary"):
            outcome = outcome_message("issues", state["summary"]).rstrip(".")
        self.message.setText(f"Harmonogram: {registration}. Ostatni wynik: {outcome}.")
        self.values["account"].setText(task.get("account") or config.run_as)
        logon = task.get(
            "logon_type", 3 if config.windows_logon == "interactive" else 1
        )
        self.values["logon"].setText(
            "Po zalogowaniu, bez hasła Windows"
            if logon == 3
            else "Także po wylogowaniu"
        )
        if result.get("session_present") is False:
            instruction = (
                "zaloguj Garmin w aplikacji"
                if config.windows_logon == "interactive"
                else "przygotuj sesję Garmin konta zadania"
            )
            self.message.setText(
                self.message.text() + " Brak sesji: " + instruction + "."
            )
        for key, value in [
            ("next", result["next_run"]),
            ("started", state.get("started_at")),
            ("finished", state.get("finished_at")),
            ("success", state.get("last_success")),
            ("pause", state.get("not_before")),
        ]:
            self.values[key].setText(display_time(value))
        self.log_view.setPlainText(readable_log(log))

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
