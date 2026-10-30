"""Human-readable collector outcomes; persistent records retain stable codes."""

OUTCOME_LABELS = {
    "never_run": "jeszcze nie uruchomiono",
    "running": "synchronizacja trwa",
    "success": "synchronizacja zakończona",
    "issues": "synchronizacja z nierozstrzygniętymi dniami lub błędami",
    "auth_required": "wymagane logowanie Garmin na koncie kolektora",
    "access_denied": "Garmin odmówił dostępu",
    "rate_limited": "oczekiwanie po ograniczeniu liczby żądań Garmin",
    "database_error": "brak dostępu do PostgreSQL",
    "network_error": "błąd połączenia z Garmin",
    "cancelled": "synchronizacja zatrzymana",
    "config_error": "konfiguracja wymaga zastosowania lub poprawy",
    "session_error": "nie można odczytać lub zabezpieczyć sesji kolektora",
    "interrupted": "poprzednia synchronizacja została przerwana",
}
