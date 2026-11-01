import math

LOGIN_STAGES = {
    "connect": "łączenie z Garmin Connect",
    "mfa_wait": "oczekiwanie na kod MFA",
    "mfa_verify": "potwierdzanie kodu MFA i dostępu aplikacji do Garmin",
    "session_save": "zabezpieczanie i zapis sesji Garmin",
    "ready": "sesja gotowa",
}


class BusyError(RuntimeError):
    def __init__(self):
        super().__init__("Inny proces zapisuje dane lub korzysta z sesji Garmin")


class SessionStorageError(RuntimeError):
    def __init__(self):
        super().__init__(
            "Nie można odczytać lub zabezpieczyć sesji Garmin na tym koncie"
        )


class LoginFailed(RuntimeError):
    """A safe diagnostic for UI/CLI; never contains a response or credentials."""

    def __init__(self, stage, reason="CLIENT_ERROR", http_status=None):
        self.stage = stage if stage in LOGIN_STAGES else "connect"
        reasons = {
            "ACCESS_DENIED",
            "RATE_LIMIT",
            "CONNECTION",
            "CLIENT_ERROR",
            "LOCAL_RUNTIME",
            "LOCAL_SESSION",
        }
        reason = reason if reason in reasons else "CLIENT_ERROR"
        self.http_status = (
            http_status
            if type(http_status) is int and 100 <= http_status <= 599
            else None
        )
        self.code = f"{self.stage.upper()}/{reason}"
        message = f"Etap: {LOGIN_STAGES[self.stage]}.\nKod diagnostyczny: {self.code}"
        if self.http_status is not None:
            message += f"; HTTP {self.http_status}"
        if reason == "RATE_LIMIT":
            message += ". Odczekaj przed ponowieniem logowania."
        if reason == "LOCAL_RUNTIME":
            message += ". Brakuje składnika lokalnej paczki. Uruchom pełną aktualną wersję aplikacji."
        super().__init__(message)


class SessionRequired(RuntimeError):
    def __init__(self):
        super().__init__(
            "Brak zapisanej sesji Garmin. Otwórz Ustawienia i zaloguj się do Garmin."
        )


class CollectorLoginUnavailable(RuntimeError):
    """Fixed local setup guidance, safe for the login dialog."""

    def __init__(self, reason):
        messages = {
            "account": "Sesja kolektora wymaga konta zadania. Uruchom CLI login pod tym kontem Windows.",
            "configuration": "Najpierw zapisz konfigurację kolektora w Ustawieniach → Automatyczne pobieranie.",
        }
        super().__init__(
            messages.get(reason, "Sprawdź konfigurację logowania kolektora.")
        )


class CollectorInstallIncomplete(RuntimeError):
    def __init__(self):
        super().__init__(
            "Rejestracja kolektora nie jest kompletna: aplikacja nie może odczytać aktualnego zadania. "
            "Sprawdź uprawnienia harmonogramu."
        )


class AccessError(ValueError):
    """A controlled, actionable message that MCP may publish to its client."""


class ParameterSelectionError(ValueError):
    """A safe rejection of a missing, repeated or disabled parameter."""


class DownloadFailed(RuntimeError):
    """Transport-neutral failure; upstream responses never cross the source port."""

    def __init__(self, http_status=None, retry_after_seconds=None):
        super().__init__("Nie udało się pobrać danych Garmin")
        self.http_status = (
            http_status
            if type(http_status) is int and 100 <= http_status <= 599
            else None
        )
        self.retry_after_seconds = (
            retry_after_seconds
            if type(retry_after_seconds) in (int, float)
            and math.isfinite(retry_after_seconds)
            and retry_after_seconds >= 0
            else None
        )
