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
            host.settings.collector_config_path or host.services.collector_path()
        )
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
        self.account = QLineEdit()
        form.addRow("Konto uruchamiające kolektor", self.account)
        self.data_dir = QLineEdit(host.settings.data_dir)
        self.dsn = QLineEdit(host.settings.database_dsn)
        self.dsn.setPlaceholderText("Połączenie PostgreSQL bez hasła; puste: libpq")
        form.addRow("Folder danych kolektora", self.data_dir)
        form.addRow("PostgreSQL kolektora", self.dsn)
        layout.addLayout(form)
        note = QLabel(
            "Kolektor ma własną sesję Garmin na koncie zadania. Pierwsze logowanie wykonaj przez CLI pod tym kontem. Terminy oznaczają stały odstęp czasu; po zmianie czasu lokalna godzina może się przesunąć."
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

        def current(result):
            if self.path.text() == path:
                success(result)

        def failed(message):
            if self.path.text() == path:
                self.message.setText(message)

        self.message.setText("Wykonywanie operacji kolektora…")
        self.host.start_aux(
            self.buttons[key],
            lambda worker: operation(manager),
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
        self.data_dir.setText(config.data_dir)
        self.dsn.setText(config.database_dsn)
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
            data_dir=self.data_dir.text(),
            database_dsn=self.dsn.text(),
        )

        def operation(manager):
            config = (
                manager.files.load_config()
                if manager.files.config_path.exists()
                else manager.files.defaults(values["data_dir"], values["database_dsn"])
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
