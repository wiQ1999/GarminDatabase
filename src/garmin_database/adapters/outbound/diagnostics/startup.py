"""Safe startup diagnostics: never persist database errors or connection options."""

import os
import re
import sys
from pathlib import Path

from psycopg import OperationalError
from psycopg.conninfo import conninfo_to_dict

from garmin_database.adapters.outbound.filesystem.files import atomic_json
from garmin_database.adapters.outbound.filesystem.settings_json import application_dir
from garmin_database.domain.time import utc_now

ERROR_PATTERNS = {
    "PASSWORD_MISSING": "no password supplied",
    "PASSWORD_REJECTED": "password authentication failed",
    "LOCAL_NETWORK": "could not create socket",
    "ACCESS_DENIED": "permission denied",
    "SERVER_UNAVAILABLE": "connection refused",
    "TIMEOUT": "timeout expired",
    "HOST_NOT_FOUND": "could not translate host name",
}
EXPLANATIONS = {
    "PASSWORD_MISSING": "Nie odczytano hasła PostgreSQL. Sprawdź plik pgpass i jego uprawnienia.",
    "PASSWORD_REJECTED": "PostgreSQL odrzucił hasło konta bazy danych.",
    "LOCAL_NETWORK": "System nie pozwolił utworzyć połączenia sieciowego z PostgreSQL.",
    "ACCESS_DENIED": "Odmowa dostępu podczas łączenia z PostgreSQL.",
    "SERVER_UNAVAILABLE": "Serwer PostgreSQL nie przyjmuje połączeń. Uruchom aplikację przez plik CMD.",
    "TIMEOUT": "Upłynął czas oczekiwania na połączenie z PostgreSQL.",
    "HOST_NOT_FOUND": "Nie można ustalić adresu serwera PostgreSQL.",
    "DATABASE_MISSING": "Wskazana baza PostgreSQL nie istnieje.",
    "CONNECTION": "Nie udało się połączyć z PostgreSQL.",
    "APPLICATION": "Nie udało się przygotować aplikacji do pracy.",
}


def startup_code(error):
    status = getattr(error, "sqlstate", None)
    known = {"28P01": "PASSWORD_REJECTED", "3D000": "DATABASE_MISSING"}
    if status in known:
        return known[status]
    if not isinstance(error, OperationalError):
        return "APPLICATION"
    # Classify locally, but never return or persist upstream error text.
    text = str(error).lower()
    for code, pattern in ERROR_PATTERNS.items():
        if pattern in text:
            return code
    return "CONNECTION"


def password_file_access(settings):
    if settings is None:
        return {"readable": None}
    options = conninfo_to_dict(settings.database_dsn)
    default = (
        Path(os.environ.get("APPDATA", Path.home())) / "postgresql/pgpass.conf"
        if os.name == "nt"
        else Path.home() / ".pgpass"
    )
    path = Path(options.get("passfile") or os.environ.get("PGPASSFILE") or default)
    standard = path.resolve() == default.resolve()
    try:
        with path.open("rb"):
            return {"readable": True, "standard_location": standard}
    except OSError as error:
        return {
            "readable": False,
            "standard_location": standard,
            "error_type": type(error).__name__,
            "errno": error.errno,
            "winerror": getattr(error, "winerror", None),
        }


def startup_failure(error, settings=None, settings_path=None):
    code = startup_code(error)
    state = getattr(error, "sqlstate", None)
    diagnostic = {
        "time": utc_now(),
        "code": "STARTUP/" + code,
        "type": type(error).__name__,
        "exception_module": type(error).__module__,
        "sqlstate": state if re.fullmatch(r"[0-9A-Z]{5}", state or "") else None,
        "pid": os.getpid(),
        "executable": str(Path(sys.executable).resolve()),
        "working_directory": str(Path.cwd()),
        "settings_file": str(
            Path(settings_path or application_dir() / "settings.json").resolve()
        ),
        "password_file_access": password_file_access(settings),
        "password_environment_present": "PGPASSWORD" in os.environ,
    }
    path = application_dir() / "logs/startup-failure.json"
    message = f"Nie można uruchomić aplikacji.\n{EXPLANATIONS[code]}\nKod: {diagnostic['code']}"
    try:
        atomic_json(path, diagnostic)
    except OSError:
        return message
    return message + f"\nSzczegóły: {path}"
