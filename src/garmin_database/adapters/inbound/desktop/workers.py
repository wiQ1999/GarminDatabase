import threading

from PySide6.QtCore import QThread, Signal

from garmin_database.application.errors import LoginFailed, SessionRequired
from garmin_database.domain.cancellation import Cancelled, check_stop


class Worker(QThread):
    success = Signal(object)
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
        except Exception as error:
            self.failure.emit(
                str(error)
                if isinstance(error, (SessionRequired, LoginFailed))
                else "Operacja nie powiodła się: "
                + type(error).__name__
                + ". Sprawdź połączenie, sesję i katalog docelowy."
            )
