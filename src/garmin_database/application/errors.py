LOGIN_STAGES = {
    "connect": "łączenie z Garmin Connect",
    "mfa_wait": "oczekiwanie na kod MFA",
    "mfa_verify": "potwierdzanie kodu MFA i dostępu aplikacji do Garmin",
    "session_save": "zabezpieczanie i zapis sesji Windows",
    "ready": "sesja gotowa",
}


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
