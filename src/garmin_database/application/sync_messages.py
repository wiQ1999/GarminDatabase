"""Unambiguous operation-wide summaries, shared by GUI and CLI."""


def sync_heading(result):
    if result.halted:
        outcome = "przerwano przed końcem zakresu"
    elif result.error_count:
        outcome = "zakończono z błędami"
    elif result.unresolved_days:
        outcome = "zakończono; pozostały nierozstrzygnięte dni HTTP 404"
    else:
        outcome = "zakończono bez błędów"
    return "Podsumowanie całej operacji: " + outcome + "."


def sync_summary_text(result):
    lines = [
        sync_heading(result),
        f"Zakres całej operacji: {result.start} — {result.end}. Obsłużono dni: {result.processed_days}/{result.requested_days}.",
        f"Dni z poprawnym importem: {result.successful_days}. Potwierdzony brak danych: {result.confirmed_no_data_days}. Pominięte dni bez lokalnego ZIP: {result.skipped_days}.",
        f"Błędy pobierania (dni): {result.download_errors}. Błędy importu FIT (pliki): {result.import_errors}. Błędy archiwów (dni): {result.archive_errors}.",
        f"Dni nierozstrzygnięte (HTTP 404): {result.unresolved_days}.",
    ]
    if result.unresolved_days:
        lines.append(
            f"Nierozstrzygnięte daty mieszczą się w zakresie: {result.first_unresolved} — {result.last_unresolved}. HTTP 404 nie potwierdza braku danych."
        )
    if result.last_day:
        lines.append(
            f"Ostatni obsłużony dzień: {result.last_day} — {result.last_day_result}."
        )
    return "\n".join(lines)
