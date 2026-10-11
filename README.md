# GarminDatabase

Prywatna aplikacja okienkowa dla Windows 11 do pobierania dziennych archiwów dobrostanu z Garmin Connect, przechowywania danych, przeglądania prostych wykresów i eksportowania JSON dla Claude i ChatGPT. Docelowo wspólna logika będzie również działać bez UI na Raspberry Pi.

## Stan projektu

Uzgodniono wymagania; aplikacja nie jest jeszcze zaimplementowana. Test użytkownika potwierdził identyczną zawartość wszystkich 20 plików FIT z WebAPI i ręcznego eksportu dla 2026-10-09. Pobrano i przeskanowano 844 archiwa: 10 994 FIT, 69 typów wiadomości i 1133 warianty pól. Ciągła historia archiwów zaczyna się 2024-06-19; osobny METRICS pochodzi z 2024-02-17. Ustalono kompletny schemat SQLite v1, ale baza nie jest jeszcze zasilona. Część pól pozostaje bez publicznie opisanej semantyki.

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
10. [Schemat SQLite v1](docs/10-sqlite-schema.md) — [DDL](schema/001_initial.sql)
11. [Interfejs Windows i ustawienia aplikacji](docs/11-desktop-ui.md)

## Pobranie historii do analizy

```powershell
cd D:\Projects\GarminDatabase
.\.venv\Scripts\python.exe .\scripts\download_history.py
```

Zakres domyślny: 2024-01-01 do wczoraj. Skrypt zapisuje oryginalne ZIP-y i raport metadanych, zachowuje postęp i może korzystać z lokalnie zapisanej sesji. Nie dekoduje jeszcze FIT ani nie buduje bazy. Szczegóły w instrukcji powyżej.

Pierwszy etap realizacji opisano w dokumencie źródła danych. Dane prywatne, sesje logowania i eksporty są wykluczone z Git przez `.gitignore`. Wykluczenie z Git nie szyfruje plików i nie tworzy kopii zapasowej.
