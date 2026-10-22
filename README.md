# GarminDatabase

Prywatna aplikacja okienkowa dla Windows 11 do pobierania dziennych archiwów dobrostanu z Garmin Connect, przechowywania danych, przeglądania prostych wykresów i eksportowania JSON dla Claude i ChatGPT. Docelowo wspólna logika będzie również działać bez UI na Raspberry Pi.

## Stan projektu

Zaimplementowano aplikację Windows, importer SQLite, klienta Garmin z sesją DPAPI, wykresy i strumieniowy eksport JSON. Paczka jest w `dist/GarminDatabase/GarminDatabase.exe`; należy zachować cały folder dystrybucji. [Uruchamianie i testy](docs/12-running-and-testing.md).

Eksport v2 tworzy osobny folder z datą i czasem, historię podsumowań oraz szczegóły w osobnych plikach każdego parametru. SQLite v3 zachowuje źródła i dodatkowy, odtwarzalny cache podsumowań dziennych; eksport może wybrać podsumowania miesięczne. [Format i reguły podsumowań](docs/05-export.md).

Zaimportowano 844 archiwa: 10 994 FIT, 8 307 429 wiadomości i 20 841 953 pola fizyczne. Ciągła historia archiwów zaczyna się 2024-06-19; osobny METRICS pochodzi z 2024-02-17. Część pól pozostaje bez publicznie opisanej semantyki i jest zachowywana pod identyfikatorami źródłowymi. Testy obejmują piramidę jednostkowe/integracyjne/UI, uruchomienie paczki Windows i rzeczywisty eksport WebAPI.

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
10. [Schemat SQLite i podsumowania](docs/10-sqlite-schema.md) — [DDL źródeł](schema/001_initial.sql), [podsumowania v3](schema/003_summaries.sql)
11. [Interfejs Windows i ustawienia aplikacji](docs/11-desktop-ui.md)
12. [Uruchamianie, budowanie i testy](docs/12-running-and-testing.md)
13. [Plan wspólnego eksportu i lokalnego MCP](docs/13-mcp-plan.md) — propozycja etapów, wyboru parametrów i pierwszych trzech narzędzi: katalogu, podsumowań dziennych i średnich okresowych; jeszcze bez implementacji MCP

## Pobranie historii do analizy

```powershell
cd D:\Projects\GarminDatabase
.\.venv\Scripts\python.exe .\scripts\download_history.py
```

Zakres domyślny: 2024-01-01 do wczoraj. Skrypt zapisuje oryginalne ZIP-y i raport metadanych, zachowuje postęp i może korzystać z lokalnie zapisanej sesji. Nie dekoduje jeszcze FIT ani nie buduje bazy. Szczegóły w instrukcji powyżej.

Pierwszy etap realizacji opisano w dokumencie źródła danych. Dane prywatne, sesje logowania i eksporty są wykluczone z Git przez `.gitignore`. Wykluczenie z Git nie szyfruje plików i nie tworzy kopii zapasowej.
