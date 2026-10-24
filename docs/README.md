# Dokumentacja GarminDatabase

Ten katalog opisuje aktualny stan aplikacji, jej kontrakty, wymagania, cele rozwoju oraz sposób uruchamiania i utrzymania.

| Dokument | Zakres |
| --- | --- |
| [Cel i wymagania](01-requirements.md) | Obsługiwany zakres, ograniczenia i kierunki rozwoju |
| [Źródło danych](02-source-validation.md) | Archiwa Garmin, format FIT, granice interpretacji i weryfikacja zgodności |
| [Architektura](03-architecture.md) | Moduły, przepływ danych, trwałość, wspólny odczyt eksportu i MCP |
| [Synchronizacja](04-synchronization.md) | Pobieranie, wznowienie, logowanie, stany i obsługa błędów |
| [Eksport JSON](05-export.md) | Kontrakt v2, agregacje, kompletność i wybór parametrów |
| [Schemat PostgreSQL](10-postgresql-schema.md) | Tabele, migracje, typy, czas, deduplikacja i podsumowania |
| [Interfejs i ustawienia](11-desktop-ui.md) | Ekrany Windows, wykresy, MFA, sesja i udostępnianie danych |
| [Uruchamianie i testy](12-running-and-testing.md) | Instalacja, CLI, build, smoke, testy oraz konfiguracja i kontrakt MCP |
| [Konfiguracja PostgreSQL](13-postgresql-setup.md) | Serwer, role, połączenie, pgpass i ochrona danych |

## Zasada utrzymania

Do `docs/` trafiają tylko informacje istotne dla obecnego stanu lub rozwoju aplikacji. Zmiana funkcji aktualizuje właściwy dokument zamiast dodawać dziennik kolejnych prób. Cele przyszłych prac są jawnie oddzielone od funkcji dostępnych.

Analizy danych, wygenerowane katalogi konkretnego skanu, wyniki testów i coverage, opisy błędów i ich dochodzenia oraz zrealizowane plany przechowuje się w ignorowanym `local-notes/` lub `test-results/`. Trwałe reguły wynikające z takich prac należy przenieść do właściwej instrukcji, bez kopiowania historii incydentu. Dokumentacja śledzona przez Git nie wymaga dostępu do lokalnych raportów.

Przed zatwierdzeniem zmiany sprawdź zgodność z kodem, odnośniki i przykładowe polecenia. Dane pomiarowe, hasła, tokeny i surowe prywatne wyjątki nie należą do dokumentacji.
