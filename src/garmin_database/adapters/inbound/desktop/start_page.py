"""StartPage view and its local interactions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QWidget,
)

from garmin_database.adapters.inbound.desktop.busy import BusyIndicator
from garmin_database.application.dto import ExportResult, SyncSummary
from garmin_database.application.sync_messages import sync_heading, sync_summary_text

from .widgets import button, page_layout


class StartPage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        layout = page_layout(
            self,
            "Twoje archiwum Garmin",
            "Pobieraj dane do dzisiaj, sprawdzaj dostępność danych i stan importu.",
        )
        self.status = QLabel()
        self.status.setText("Odczytywanie stanu archiwum…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            "background:#191e27;padding:22px;border-radius:10px;font-size:14px;"
        )
        layout.addWidget(self.status)
        state_header = QHBoxLayout()
        self.refresh_note = QLabel(
            f"Automatyczne odświeżanie co {self.host.settings.refresh_seconds} s"
        )
        state_header.addWidget(self.refresh_note)
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
        self.download_button = button("Pobierz nowe dane", self.host.sync, True)
        actions.addWidget(self.download_button)
        self.download_all_button = button(
            "Pobierz wszystko", lambda: self.host.sync(refresh_all=True)
        )
        actions.addWidget(self.download_all_button)
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.stage = QLabel("Gotowe do pracy")
        self.stage.setWordWrap(True)
        layout.addWidget(self.stage)
        self.stop_button = button("Zatrzymaj", self.host.stop_work)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button, 0, Qt.AlignmentFlag.AlignLeft)
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
            str(len(self.host.parameters))
            if self.host.catalog_loaded
            else "oczekiwanie na listę parametrów"
        )
        self.status.setText(
            self.status.text() + "\nRozpoznane serie / właściwości: " + count
        )

    def show_overview_errors(self):
        message = "\n".join(
            error for error in (self.host.state_error, self.host.catalog_error) if error
        )
        self.status_error.setText(message)
        self.status_error.setVisible(bool(message))

    def on_progress(self, day, stage, index, total):
        self.host.progress_pending = (day, stage, index, total)
        self.host.progress_details.append(f"{day} — {stage} ({index}/{total})")

    def flush_progress(self):
        if self.host.progress_pending is None:
            return
        day, stage, index, total = self.host.progress_pending
        self.host.progress_pending = None
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(index)
        if not self.host.worker or not self.host.worker.stop.is_set():
            self.stage.setText(f"{day} — {stage} ({index}/{total})")
        self.details.append("\n".join(self.host.progress_details))
        self.host.progress_details.clear()

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
            self.host.export_page.last_export_dir = result.directory
            self.host.export_page.export_result.setText(
                f"Folder: {result.directory}\nWygenerowano {len(result.files)} plików danych "
                + f"({sum(result.files.values()) / 1024:.1f} KB). Historia: history; szczegóły: details."
            )
