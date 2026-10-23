# GarminDatabase

Prywatna aplikacja okienkowa dla Windows 11 do pobierania dziennych archiwów dobrostanu z Garmin Connect, przechowywania danych, przeglądania prostych wykresów i eksportowania JSON dla Claude i ChatGPT. Docelowo wspólna logika będzie również działać bez UI na Raspberry Pi.

## Stan projektu

Zaimplementowano aplikację Windows, importer PostgreSQL, klienta Garmin z sesją DPAPI, wykresy i strumieniowy eksport JSON. Paczka jest w `dist/GarminDatabase/GarminDatabase.exe`; należy zachować cały folder dystrybucji. [Uruchamianie i testy](docs/12-running-and-testing.md).

Eksport v2 tworzy osobny folder z datą i czasem, historię podsumowań oraz szczegóły w osobnych plikach każdego parametru. Schemat aplikacji v3 w PostgreSQL zachowuje źródła i dodatkowy, odtwarzalny cache podsumowań dziennych; eksport może wybrać podsumowania miesięczne. [Format i reguły podsumowań](docs/05-export.md).

Od 2026-10-23 aplikacja używa wyłącznie PostgreSQL 16+ — lokalnie i na serwerze. Nie przenosi danych ze starego SQLite; nową bazę zasila ponowne pobranie lub import oryginalnych ZIP. Najpierw skonfiguruj serwer i połączenie: [PostgreSQL na Windows, Linux i Raspberry Pi OS](docs/13-postgresql-setup.md).

Hasła połączenia nie zapisują się w ustawieniach. PostgreSQL wymaga osobnego zabezpieczenia nośnika i TLS; oryginalne ZIP oraz eksporty również zawierają dane wrażliwe.

## Dokumentacja

1. [Cel i wymagania](docs/01-requirements.md)
2. [Źródło danych i jego weryfikacja](docs/02-source-validation.md)
3. [Architektura i przechowywanie](docs/03-architecture.md)
4. [Synchronizacja i obsługa błędów](docs/04-synchronization.md)
5. [Eksport JSON](docs/05-export.md)
6. [Plan realizacji i kryteria odbioru](docs/06-implementation.md)
7. [Pobranie surowej historii — uruchomienie i wznowienie](docs/07-history-collection.md)
8. [Wyniki analizy pełnej historii FIT](docs/08-fit-analysis.md)
9. [Kompletny katalog wykrytych pól](docs/09-fit-field-catalog.md)
10. [Schemat PostgreSQL i podsumowania](docs/10-postgresql-schema.md) — [DDL źródeł](schema/001_initial.sql), [podsumowania v3](schema/003_summaries.sql)
11. [Interfejs Windows i ustawienia aplikacji](docs/11-desktop-ui.md)
12. [Uruchamianie, budowanie i testy](docs/12-running-and-testing.md)
13. [Konfiguracja PostgreSQL i ochrona danych](docs/13-postgresql-setup.md)

## Pobranie historii do analizy

```powershell
cd D:\Projects\GarminDatabase
.\.venv\Scripts\python.exe .\scripts\download_history.py
```

Zakres domyślny: 2024-01-01 do wczoraj. Skrypt zapisuje oryginalne ZIP-y i raport metadanych, zachowuje postęp i może korzystać z lokalnie zapisanej sesji. Nie dekoduje jeszcze FIT ani nie buduje bazy. Szczegóły w instrukcji powyżej.

Pierwszy etap realizacji opisano w dokumencie źródła danych. Dane prywatne, sesje logowania i eksporty są wykluczone z Git przez `.gitignore`. Wykluczenie z Git nie szyfruje plików i nie tworzy kopii zapasowej.
