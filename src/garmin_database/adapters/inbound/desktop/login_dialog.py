"""Qt login progress and MFA; see docs/11-desktop-ui.md."""

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from garmin_database.application.errors import LOGIN_STAGES


class LoginSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self.setAccessibleName("Trwa logowanie")
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.advance)

    def advance(self):
        self.angle = (self.angle + 16) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QRectF(5, 5, 38, 38)
        pen = QPen(QColor("#354154"), 4)
        painter.setPen(pen)
        painter.drawEllipse(ring)
        pen.setColor(QColor("#4fa4f3"))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(ring, -self.angle * 16, 110 * 16)


class LoginDialog(QDialog):
    """Own one login attempt until its thread has actually finished."""

    status_changed = Signal(str)

    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self.worker = worker
        worker.setParent(self)
        self.authenticated = False
        self.mfa_dialog = None
        self.setWindowTitle("Logowanie do Garmin Connect")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("Logowanie do Garmin Connect")
        title.setStyleSheet("font-size:20px;font-weight:600;")
        layout.addWidget(title)
        progress = QHBoxLayout()
        self.spinner = LoginSpinner(self)
        progress.addWidget(self.spinner)
        self.message = QLabel("Łączenie z Garmin Connect…")
        self.message.setWordWrap(True)
        self.message.setMinimumWidth(320)
        progress.addWidget(self.message, 1)
        layout.addLayout(progress)
        self.hint = QLabel(
            "Poczekaj na zakończenie logowania. Jeśli Garmin wymaga kodu MFA, "
            "pojawi się okno jego wprowadzenia."
        )
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#a3afbf;")
        layout.addWidget(self.hint)
        actions = QHBoxLayout()
        actions.addStretch()
        self.close_button = QPushButton("Anuluj")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        worker.success.connect(self.succeeded)
        worker.failure.connect(self.failed)
        worker.finished.connect(self.work_finished)
        worker.mfa_requested.connect(self.request_mfa)
        worker.login_stage.connect(self.show_login_stage)

    def start(self):
        self.spinner.timer.start()
        self.worker.start()

    def show_login_stage(self, stage):
        self.message.setText(LOGIN_STAGES.get(stage, "Łączenie z Garmin Connect") + "…")

    def succeeded(self, result):
        self.authenticated = True
        self.message.setText("Zalogowano. Sesja została zaszyfrowana i zapisana.")

    def failed(self, message):
        # Worker forwards only the safe core diagnostic or a generic error code.
        self.message.setText("Nie udało się zalogować. " + message)

    def work_finished(self):
        self.worker.operation = None  # Release captured credentials on every outcome.
        self.worker.code = None
        self.worker.mfa_ready.clear()
        self.spinner.timer.stop()
        self.spinner.hide()
        if self.worker.stop.is_set():
            self.status_changed.emit(
                "Logowanie anulowane. Możesz rozpocząć nową próbę."
            )
            super().reject()
            return
        self.close_button.setText(
            "Zamknij" if self.authenticated else "Wróć do logowania"
        )
        self.hint.setText(
            "Możesz teraz pobierać dane."
            if self.authenticated
            else "Wróć do formularza i ponownie wpisz hasło przed następną próbą."
        )
        self.status_changed.emit(self.message.text())

    def reject(self):
        if not self.worker.isRunning():
            super().reject()
            return
        self.worker.stop.set()
        self.worker.mfa_ready.set()
        if self.mfa_dialog is not None:
            self.mfa_dialog.reject()
        self.message.setText("Anulowanie logowania…")
        self.hint.setText("Czekam na zakończenie bieżącego żądania do Garmin.")
        self.close_button.setEnabled(False)

    def closeEvent(self, event):
        if self.worker.isRunning():
            self.reject()
            event.ignore()
            return
        super().closeEvent(event)

    def request_mfa(self):
        if self.worker.stop.is_set():
            self.worker.mfa_ready.set()
            return
        self.message.setText("Czekam na kod uwierzytelnienia Garmin…")
        prompt = QInputDialog(self)
        self.mfa_dialog = prompt
        prompt.setWindowTitle("Garmin — uwierzytelnienie")
        prompt.setLabelText("Podaj kod MFA")
        prompt.setTextEchoMode(QLineEdit.EchoMode.Normal)
        prompt.finished.connect(self.mfa_finished)
        prompt.open()

    def mfa_finished(self, result):
        prompt = self.mfa_dialog
        self.mfa_dialog = None
        self.worker.code = (
            prompt.textValue().strip()
            if result == QDialog.DialogCode.Accepted
            else None
        )
        if result != QDialog.DialogCode.Accepted:
            self.worker.stop.set()
        prompt.setTextValue("")
        prompt.deleteLater()
        self.message.setText("Weryfikowanie logowania…")
        self.worker.mfa_ready.set()
