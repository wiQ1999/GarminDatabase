"""Local automation controls; all disk and OS work goes through the host worker."""

import os
from dataclasses import replace
from datetime import datetime, timezone

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.busy import BusyButton


def warsaw_datetime(value):
    # Construct from an instant: QDateTime(datetime) can discard Python tzinfo.
    return QDateTime.fromMSecsSinceEpoch(
        int(value.timestamp() * 1000), QTimeZone(b"Europe/Warsaw")
    )


class CollectorPanel(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.config = None
        self.edited = False
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.path = QLineEdit(
            host.services.collector_path(
                host.services.settings_store.location(host.settings_path)
            )
        )
        self.path.setReadOnly(True)
        self.path.hide()
        self.enabled = QCheckBox("Włącz cykliczne pobieranie")
        form.addRow(self.enabled)
        self.interval = QSpinBox()
        self.interval.setRange(15, 525600)
        self.interval.setValue(120)
        self.interval.setSuffix(" min")
        form.addRow("Odstęp między terminami", self.interval)
        self.anchor = QDateTimeEdit()
        self.anchor.setTimeZone(QTimeZone(b"Europe/Warsaw"))
        self.anchor.setDateTime(
            warsaw_datetime(datetime(2024, 1, 1, tzinfo=timezone.utc))
        )
        self.anchor.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.anchor.setCalendarPopup(True)
        form.addRow("Początek harmonogramu (Warszawa)", self.anchor)
        self.windows_logon = QComboBox()
        self.windows_logon.addItem("Bieżące konto — bez hasła Windows", "interactive")
        self.windows_logon.addItem("Także po wylogowaniu — hasło Windows", "password")
        if os.name != "nt":
            self.windows_logon.setCurrentIndex(1)
            self.windows_logon.setEnabled(False)
        form.addRow("Tryb uruchamiania", self.windows_logon)
        self.account = QLineEdit(host.services.current_account())
        form.addRow("Konto uruchamiające kolektor", self.account)
        layout.addLayout(form)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        actions = QHBoxLayout()
        self.buttons = {}
        for key, text, slot in [
            ("load", "Wczytaj", self.load),
            ("save", "Zapisz konfigurację", self.save),
            ("apply", "Zainstaluj / zaktualizuj kolektor", self.apply),
        ]:
            trigger = BusyButton(text)
            trigger.clicked.connect(slot)
            actions.addWidget(trigger)
            self.buttons[key] = trigger
        layout.addLayout(actions)
        self.message = QLabel(
            "Zapisz konfigurację bez instalacji albo zainstaluj kolektor jednym przyciskiem."
        )
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.interval.valueChanged.connect(self.mark_edited)
        self.enabled.toggled.connect(self.mark_edited)
        self.account.textEdited.connect(self.mark_edited)
        self.anchor.dateTimeChanged.connect(self.mark_edited)
        self.windows_logon.currentIndexChanged.connect(self._mode_changed)
        self.windows_logon.currentIndexChanged.connect(self.mark_edited)
        self._mode_changed()

    def _mode_changed(self, *args):
        interactive = self.windows_logon.currentData() == "interactive"
        self.account.setReadOnly(interactive)
        if interactive:
            self.account.setText(self.host.services.current_account())
        explanation = (
            "Działa na bieżącym koncie po zalogowaniu, również przy zablokowanym ekranie. "
            "Nie wymaga hasła Windows i korzysta z sesji Garmin aplikacji. "
            if interactive
            else "Działa również po wylogowaniu. Rejestracja wymaga hasła konta Windows, nie PIN/Hello. "
            "Sesję Garmin przygotuj osobno dla konta zadania; inne konto wymaga CLI login. "
        )
        self.note.setText(
            explanation
            + "Połączenie i początek pobierania pochodzą z zapisanych ustawień aplikacji. "
            "Początek harmonogramu wyznacza terminy, nie zakres danych."
        )

    def mark_edited(self, *args):
        self.edited = True

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
            if key not in {"save", "apply"}:
                try:
                    manager.files.load_config()
                except FileNotFoundError:
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
        self.windows_logon.setCurrentIndex(
            self.windows_logon.findData(config.windows_logon)
        )
        self.account.setText(config.run_as)
        self.anchor.setDateTime(
            warsaw_datetime(
                datetime.fromisoformat(config.anchor_at.replace("Z", "+00:00"))
            )
        )
        self.message.setText("Konfiguracja wczytana")

    def save(self, *, install=False):
        values = dict(
            enabled=self.enabled.isChecked(),
            interval_minutes=self.interval.value(),
            anchor_at=self.anchor.dateTime()
            .toUTC()
            .toPython()
            .replace(tzinfo=timezone.utc)
            .isoformat(),
        )
        account = self.account.text().strip()
        mode = self.windows_logon.currentData()
        data_dir = self.host.settings.data_dir
        settings_path = self.host.services.settings_store.location(
            self.host.settings_path
        )

        def operation(manager):
            try:
                config = manager.files.load_config()
            except FileNotFoundError:
                legacy = manager.files.config_path.parent / "collector.json"
                if legacy.is_file():
                    config = self.host.services.collector_manager(
                        legacy
                    ).files.load_config()
                    config = replace(
                        config,
                        settings_path=str(settings_path),
                        database_dsn=None,
                        download_from=None,
                    )
                else:
                    config = manager.files.defaults(
                        data_dir, None, settings_path=settings_path
                    )
            config = manager.files.for_account(replace(config, **values), account, mode)
            manager.files.save_config(config)
            if install:
                manager.install(manager.files.load_config())
            return config

        def saved(config):
            self.config = config
            self.message.setText(
                "Kolektor zainstalowany. Sprawdź następny termin i stan sesji w zakładce Kolektor."
                if install
                else "Konfiguracja zapisana. Zainstaluj / zaktualizuj kolektor, aby zastosować harmonogram."
            )

        self._run("apply" if install else "save", operation, saved)

    def apply(self):
        self.save(install=True)
