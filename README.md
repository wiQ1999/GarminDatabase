# GarminDatabase

Prywatne narzędzie do pobierania dziennych archiwów dobrostanu z Garmin Connect, przechowywania danych i eksportowania ich do JSON dla Claude i ChatGPT.

## Stan projektu

Uzgodniono wymagania; aplikacja nie jest jeszcze zaimplementowana. Dostępny jest skrypt próbny pobrania i porównania archiwów. Test użytkownika potwierdził identyczną zawartość wszystkich 20 plików FIT z WebAPI i ręcznego eksportu dla 2026-10-09. Nie potwierdzono jeszcze zakresu pól FIT ani dostępności całej historii.

## Dokumentacja

1. [Cel i wymagania](docs/01-requirements.md)
2. [Źródło danych i jego weryfikacja](docs/02-source-validation.md)
3. [Architektura i przechowywanie](docs/03-architecture.md)
4. [Synchronizacja i obsługa błędów](docs/04-synchronization.md)
5. [Eksport JSON](docs/05-export.md)
6. [Plan realizacji i kryteria odbioru](docs/06-implementation.md)

Pierwszy etap realizacji opisano w dokumencie źródła danych. Dane prywatne, sesje logowania i eksporty są wykluczone z Git przez `.gitignore`. Wykluczenie z Git nie szyfruje plików i nie tworzy kopii zapasowej.
