"""Local automation controls; all disk and OS work goes through the host worker."""

from dataclasses import replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.busy import BusyButton
from garmin_database.application.collector_messages import OUTCOME_LABELS


class CollectorPanel(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.config = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.path = QLineEdit(
            host.services.collector_path(
                host.services.settings_store.location(host.settings_path)
            )
        )
        self.path.setReadOnly(True)
        form.addRow("Konfiguracja kolektora", self.path)
        self.enabled = QCheckBox("Włącz cykliczne pobieranie")
        form.addRow(self.enabled)
        self.interval = QSpinBox()
        self.interval.setRange(15, 525600)
        self.interval.setValue(120)
        self.interval.setSuffix(" min")
        form.addRow("Odstęp między terminami", self.interval)
        self.anchor = QDateTimeEdit()
        self.anchor.setTimeZone(QTimeZone(b"Europe/Warsaw"))
        self.anchor.setDateTime(QDateTime(datetime(2024, 1, 1, tzinfo=timezone.utc)))
        self.anchor.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.anchor.setCalendarPopup(True)
        form.addRow("Początek harmonogramu (Warszawa)", self.anchor)
        self.account = QLineEdit(host.services.current_account())
        form.addRow("Konto uruchamiające kolektor", self.account)
        layout.addLayout(form)
        note = QLabel(
            "Połączenie PostgreSQL i początek pobierania pochodzą z zapisanych ustawień aplikacji. "
            "Konto Windows wymaga hasła; PIN/Hello nie wystarcza do pracy po wylogowaniu. "
            "Kolektor ma własną sesję Garmin: pierwsze logowanie wykonaj przez CLI pod kontem zadania. "
            "Początek harmonogramu określa terminy uruchomień, a nie zakres danych. "
            "Po zmianie czasu lokalna godzina terminu może się przesunąć."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        self.buttons = {}
        for key, text, slot in [
            ("load", "Wczytaj", self.load),
            ("save", "Zapisz konfigurację", self.save),
            ("apply", "Zastosuj harmonogram", self.apply),
            ("status", "Sprawdź stan", self.status),
            ("logs", "Pokaż log", self.logs),
        ]:
            trigger = BusyButton(text)
            trigger.clicked.connect(slot)
            actions.addWidget(trigger)
            self.buttons[key] = trigger
        layout.addLayout(actions)
        self.message = QLabel(
            "Konfiguracja automatyzacji jest niezależna od preferencji aplikacji. Zapisz ją, a następnie zastosuj harmonogram."
        )
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(160)
        self.log_view.document().setMaximumBlockCount(500)
        self.log_view.hide()
        layout.addWidget(self.log_view)

    def _run(self, key, operation, success):
        if self.host.aux_worker is not None or self.host.closing:
            return
        path = self.path.text()
        if not path:
            self.message.setText("Wskaż plik konfiguracji kolektora")
            return
        manager = self.host.services.collector_manager(path)
        missing = object()

        def current(result):
            if self.path.text() == path:
                if result is missing:
                    self.message.setText(
                        "Brak konfiguracji kolektora. Najpierw wybierz „Zapisz konfigurację”."
                    )
                else:
                    success(result)

        def failed(message):
            if self.path.text() == path:
                self.message.setText(message)

        def execute(worker):
            if key != "save" and not manager.files.config_path.is_file():
                return missing
            return operation(manager)

        self.message.setText("Wykonywanie operacji kolektora…")
        self.host.start_aux(
            self.buttons[key],
            execute,
            current,
            failed,
        )

    def load(self):
        self._run("load", lambda manager: manager.files.load_config(), self._loaded)

    def _loaded(self, config):
        self.config = config
        self.interval.setValue(config.interval_minutes)
        self.enabled.setChecked(config.enabled)
        self.account.setText(config.run_as)
        self.anchor.setDateTime(
            QDateTime(datetime.fromisoformat(config.anchor_at.replace("Z", "+00:00")))
        )
        self.message.setText("Konfiguracja wczytana")

    def save(self):
        values = dict(
            enabled=self.enabled.isChecked(),
            interval_minutes=self.interval.value(),
            anchor_at=self.anchor.dateTime()
            .toUTC()
            .toPython()
            .replace(tzinfo=timezone.utc)
            .isoformat(),
            run_as=self.account.text().strip(),
        )
        data_dir = self.host.settings.data_dir
        settings_path = self.host.services.settings_store.location(
            self.host.settings_path
        )

        def operation(manager):
            config = (
                manager.files.load_config()
                if manager.files.config_path.exists()
                else manager.files.defaults(data_dir, None, settings_path=settings_path)
            )
            config = replace(config, **values)
            manager.files.save_config(config)
            return config

        def saved(config):
            self.config = config
            self.message.setText(
                "Konfiguracja zapisana. Zastosuj harmonogram, aby zmiana zaczęła działać."
            )

        self._run("save", operation, saved)

    def apply(self):
        self._run(
            "apply",
            lambda manager: manager.apply(manager.files.load_config()),
            lambda _: self.message.setText("Harmonogram zastosowany"),
        )

    def status(self):
        self._run("status", lambda manager: manager.status(), self._status)

    def _status(self, result):
        task, state = result["schedule"], result["state"]
        registration = (
            "aktywny"
            if task["enabled"]
            else "wyłączony"
            if task["installed"]
            else "niezarejestrowany"
        )
        if task["installed"] and not task["revision_matches"]:
            registration += "; zmiany niezastosowane"
        when = result["next_run"]
        if when:
            when = (
                datetime.fromisoformat(when)
                .astimezone(ZoneInfo("Europe/Warsaw"))
                .strftime("%Y-%m-%d %H:%M %z")
            )
        session = (
            "wymaga logowania na koncie kolektora"
            if state["auth_required"]
            else "sprawdź wynik ostatniej synchronizacji"
        )
        outcome = OUTCOME_LABELS.get(state["outcome"], "nieznany stan")
        self.message.setText(
            f"Harmonogram: {registration}. Następny termin: {when or 'brak'}. Ostatni wynik: {outcome}. Sesja kolektora: {session}."
        )

    def logs(self):
        def show(text):
            self.log_view.setPlainText(text)
            self.log_view.show()
            self.message.setText("Log kolektora")

        self._run(
            "logs",
            lambda manager: manager.files.logs(manager.files.load_config()),
            show,
        )
