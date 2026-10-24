# GarminDatabase

Prywatna aplikacja Windows do pobierania dziennych archiwów dobrostanu z Garmin Connect, zachowania źródłowych danych FIT w PostgreSQL, przeglądania wykresów i eksportu JSON. Lokalny serwer MCP udostępnia wybrane podsumowania tylko do odczytu przez `stdio`.

## Możliwości aplikacji

- Pobieranie brakujących dni od wybranego początku do wczoraj według Europe/Warsaw, import i wznowienie przerwanej pracy.
- Zachowanie oryginalnych ZIP i fizycznych pól FIT, w tym pól bez rozpoznanej semantyki.
- Szczegóły pojedynczego dnia, podsumowania Garmin i jawnie oznaczone średnie dzienne obsługiwanych pomiarów.
- Eksport v2: nowy folder z manifestem oraz osobnymi plikami historii i szczegółów dla każdego parametru.
- Niezależny wybór parametrów eksportu i MCP. MCP nie pobiera danych z Garmin i nie zapisuje do bazy.
- Logowanie z MFA i sesją chronioną Windows DPAPI. Hasła i kody nie są zapisywane.

Aplikacja wymaga **PostgreSQL 16+**. Serwer działa osobno i nie jest częścią EXE. Nie ma wariantu SQLite ani migracji jego danych. Rdzeń importu i eksportu działa bez UI; harmonogram, ochrona sesji Linux i hub Raspberry Pi pozostają kierunkami rozwoju.

## Uruchomienie

Najpierw [przygotuj PostgreSQL i połączenie](docs/13-postgresql-setup.md). Użytkownik paczki Windows uruchamia `GarminDatabase.exe`, zachowując cały folder dystrybucji z `_internal`. W Ustawieniach konfiguruje folder danych, połączenie i logowanie Garmin, a następnie wybiera „Pobierz dane”.

Kod ma układ `src/` i stosuje [Clean Architecture](docs/03-architecture.md). Ze źródeł: po instalacji `python -m pip install -e .` uruchom `python -m garmin_database`. Instalację zależności, CLI, build i testy opisuje [instrukcja uruchamiania](docs/12-running-and-testing.md). Szczegóły istniejącej lokalnej instalacji i jej launchera znajdują się w ignorowanym `local-runtime/README-local.md`.

Hasło PostgreSQL dostarcza pgpass lub środowisko procesu. Dane, sesje i eksporty są poza Git; wykluczenie z repozytorium nie zastępuje ochrony nośnika ani kopii zapasowej.

## Dokumentacja

[Indeks dokumentacji](docs/README.md) prowadzi do aktualnych wymagań, architektury, reguł synchronizacji, eksportu, schematu, UI i instrukcji obsługi. Opisy dotyczą stanu aplikacji i jawnie określonych celów rozwoju.

Analizy pojedynczych zbiorów, raporty testów, opisy incydentów i wcześniejsze wersje dokumentów trafiają do ignorowanego `local-notes/` lub `test-results/`. Nie są częścią dokumentacji produktu w `docs/`.
