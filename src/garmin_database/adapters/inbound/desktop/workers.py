import threading

from PySide6.QtCore import QThread, Signal

from garmin_database.application.errors import (
    BusyError,
    LoginFailed,
    SessionRequired,
    SessionStorageError,
)
from garmin_database.application.ports import ReadFailure
from garmin_database.domain.cancellation import Cancelled, check_stop


class Worker(QThread):
    success = Signal(object)
    preview = Signal(object)
    failure = Signal(str)
    progress = Signal(str, str, int, int)
    mfa_requested = Signal()
    login_stage = Signal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.stop = threading.Event()
        self.mfa_ready = threading.Event()
        self.code = None

    def ask_mfa(self):
        self.code = None
        self.mfa_ready.clear()
        self.mfa_requested.emit()
        while not self.mfa_ready.wait(0.2):
            check_stop(self.stop)
        check_stop(self.stop)
        value = self.code
        self.code = None
        if not value:
            raise Cancelled()
        return value

    def run(self):
        try:
            check_stop(self.stop)
            result = self.operation(self)
            check_stop(self.stop)
            self.success.emit(result)
        except Cancelled:
            self.failure.emit("Zatrzymano. Ukończone dane zostały zachowane.")
        except ReadFailure as error:
            self.failure.emit(
                {
                    "timeout": "Przekroczono czas odczytu danych. Połączenie może być aktywne; zapytanie trwało zbyt długo.",
                    "connection": "Nie można połączyć się z PostgreSQL. Sprawdź dostępność serwera i konfigurację połączenia.",
                }.get(error.reason, "Nie można odczytać danych z PostgreSQL.")
            )
        except Exception as error:
            self.failure.emit(
                str(error)
                if isinstance(
                    error,
                    (SessionRequired, SessionStorageError, LoginFailed, BusyError),
                )
                else "Operacja nie powiodła się: "
                + type(error).__name__
                + ". Sprawdź połączenie, sesję i katalog docelowy."
            )
