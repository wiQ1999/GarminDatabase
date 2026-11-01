"""Safe, human-readable log events; runtime outcome codes remain stable."""

from garmin_database.application.time_presentation import (
    collector_log_text,
    display_time,
    warsaw_time,
)

EVENT_MESSAGES = {
    "never_run": "Kolektor nie był jeszcze uruchamiany.",
    "running": "Trwa pobieranie i import danych Garmin.",
    "success": "Synchronizacja zakończona bez błędów i nierozstrzygniętych dni.",
    "issues": "Synchronizacja zakończona z nierozstrzygniętymi dniami lub błędami.",
    "auth_required": "Pobieranie wstrzymane: wymagane logowanie Garmin. Zaloguj Garmin dla kolektora w Ustawieniach lub poleceniem login na koncie zadania.",
    "access_denied": "Pobieranie zatrzymane: Garmin odmówił dostępu (HTTP 403). Sprawdź sesję i uprawnienia konta Garmin.",
    "rate_limited": "Pobieranie wstrzymane: Garmin ograniczył liczbę żądań (HTTP 429). Kolektor respektuje czas oczekiwania przed następną próbą.",
    "database_error": "Nie udało się skorzystać z PostgreSQL. Sprawdź uruchomienie serwera, połączenie i uprawnienia konta kolektora.",
    "network_error": "Nie udało się połączyć z Garmin. Sprawdź połączenie sieciowe i dostępność Garmin.",
    "cancelled": "Synchronizacja została zatrzymana przed zakończeniem.",
    "config_error": "Kolektor nie rozpoczął pobierania: konfiguracja harmonogramu wymaga zastosowania lub poprawy. W Ustawieniach wybierz „Zainstaluj / zaktualizuj kolektor” lub użyj polecenia schedule apply.",
    "session_error": "Nie można odczytać lub zabezpieczyć sesji Garmin. Sprawdź konto uruchamiające kolektor i uprawnienia do jego sesji.",
    "interrupted": "Synchronizacja nie została ukończona. Sprawdź stan kolektora i wynik następnego cyklu.",
    "skipped_busy": "Pominięto cykl: trwa inna operacja pobierania lub importu. Kolektor spróbuje ponownie w następnym zwykłym terminie.",
}

COUNTERS = (
    ("processed_days", "Obsłużone dni"),
    ("requested_days", "Dni w zakresie"),
    ("successful_days", "Dni z poprawnym importem"),
    ("confirmed_no_data_days", "Potwierdzony brak danych (dni)"),
    ("unresolved_days", "Nierozstrzygnięte dni (HTTP 404)"),
    ("download_errors", "Błędy pobierania (dni)"),
    ("import_errors", "Błędy importu FIT (pliki)"),
    ("archive_errors", "Błędy archiwów (dni)"),
    ("skipped_days", "Pominięte dni bez lokalnego ZIP"),
)


def safe_counts(summary):
    """Do not serialize arbitrary summary fields, upstream text, or measurements."""
    return {
        key: value
        for key, _ in COUNTERS
        if type(value := (summary or {}).get(key)) is int and value >= 0
    }


def event_text(outcome, *, summary=None, not_before=None):
    message = EVENT_MESSAGES[outcome]
    counts = safe_counts(summary)
    if counts:
        message += (
            " "
            + "; ".join(
                f"{label}: {counts[key]}" for key, label in COUNTERS if key in counts
            )
            + "."
        )
    elif outcome == "issues":
        message += " Ten wpis nie zawiera szczegółowego podsumowania przyczyny."
    if counts.get("unresolved_days", 0):
        message += " HTTP 404 nie potwierdza braku danych; dostępność jest sprawdzana ponownie po upływie 24 godzin od poprzedniego sprawdzenia."
    if outcome == "rate_limited" and not_before:
        message += " Najwcześniejsza kolejna próba: " + display_time(not_before) + "."
    return message


def readable_log(text):
    """Translate legacy code-only events in either historical timestamp format."""
    lines = []
    for line in collector_log_text(text).splitlines(keepends=True):
        parts = line.rstrip("\r\n").split(" ", 3)
        if len(parts) == 4 and parts[3] in EVENT_MESSAGES:
            try:
                warsaw_time(parts[0] + "T" + parts[1] + parts[2])
            except ValueError:
                pass  # Includes a partial first line from a bounded log tail.
            else:
                ending = line[len(line.rstrip("\r\n")) :]
                line = " ".join(parts[:3]) + " " + event_text(parts[3]) + ending
        lines.append(line)
    return "".join(lines)
