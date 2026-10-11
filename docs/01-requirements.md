# Cel i wymagania

Ustalenia z rozmowy, aktualizacja 2026-10-11. Wymagania użytkownika mają pierwszeństwo przed propozycjami implementacji w pozostałych dokumentach.

## Cel

Zapewnić pełne zachowanie danych dostępnych w dziennym eksporcie dobrostanu Garmin oraz czytelny eksport danych dla modeli AI. Dane będą kontekstem do analizy zdrowia, snu, anomalii i trendów oraz konkretnych problemów medycznych. Interpretację i łączenie z innymi źródłami wykonuje model AI poza aplikacją.

## Użytkownik i środowisko

- Jeden użytkownik, jedno prywatne konto Garmin.
- Jeden zegarek: Garmin Epix gen 2, używany nieprzerwanie od nieustalonej daty w 2024 roku.
- Pierwsza wersja: aplikacja okienkowa na Windows 11, uruchamiana ręcznie z pliku `.exe`, bez konsoli, przeglądarki, instalatora i osobnej instalacji Pythona.
- Python i SQLite; realizacja UI: PySide6 Essentials/Qt Widgets i QPainter, pakowanie PyInstaller onedir.
- W przyszłości Raspberry Pi jako automat importu według harmonogramu i hub dostępu do danych, bez UI, ze wspólną logiką aplikacji.

## Zakres pierwszej wersji

1. Jedna metoda pobierania: WebAPI dziennego archiwum dobrostanu ZIP, po potwierdzeniu zgodności z ręcznym eksportem.
2. Pierwszy import sprawdza każdy dzień od 2024-01-01 do wczoraj. Nieznany początek historii ustala się na podstawie uzyskanych danych; dni bez danych nie są błędami sieciowymi.
3. Kolejne uruchomienia pobierają niepobrane dni, także zaległości. Nigdy nie pobierają dzisiejszego ani przyszłego dnia.
4. Zachowanie oryginalnych archiwów oraz dekodowanie danych do SQLite bez utraty dostępnych pól.
5. Ręczne generowanie JSON z wyborem parametrów i okresu.
6. Dane źródłowe i SQLite stanowią trwałe zasoby. Eksporty są plikami wynikowymi tworzonymi na żądanie, nie kolejnym archiwum.
7. Interfejs po polsku: Start, Dane, Eksport, Ustawienia; ciemny motyw z niebieskimi akcentami i ikonami wzorowanymi na Garmin Connect.
8. Przeglądanie stanu importu, kompletności danych i wykresów rozpoznanych parametrów. Dłuższe okresy pokazują tylko podsumowania źródłowe Garmin; szczegółowe próbki są wyświetlane dla pojedynczego dnia. Bez tabel rekordów, powiększania, interpolacji i własnych agregatów.
9. Przycisk „Pobierz dane” uruchamia pobieranie i import; postęp, zatrzymanie i późniejsze wznowienie są widoczne w UI. Przeglądanie już zaimportowanych danych jest dostępne podczas pracy.

Szczegóły uzgodnionego interfejsu i przechowywania ustawień: [specyfikacja UI](11-desktop-ui.md).

## Poza zakresem

- Osobne pobieranie treningów i dodatkowych metryk z innych endpointów.
- Automatyczne ponowne pobieranie zakończonych dni i przyrostowe aktualizacje dawnych danych.
- Własne średnie, agregaty, trendy, anomalie, diagnozy i dodatkowe wskaźniki.
- Instrukcje lub interpretacje dla AI w plikach eksportu.
- Automatyczny eksport, WebAPI aplikacji, MCP i bezpośrednie odpytywanie bazy przez model w pierwszej wersji. Przyszła rola Raspberry Pi jako huba wymaga osobnego projektu sposobu udostępniania danych.
- Automatyczne kopie zapasowe i dodatkowe trwałe kopie danych.

Nie odrzucać pól znajdujących się w archiwum dlatego, że dotyczą wysiłku. Ograniczenie treningów dotyczy osobnego pobierania, a nie usuwania zawartości ZIP.

## Przechowywanie

Początkowo folder projektu, z konfigurowalną ścieżką. Oryginalne archiwa, SQLite, eksporty, logi i sesje nigdy nie trafiają do Git. Przed użyciem niestandardowego katalogu w repozytorium należy sprawdzić reguły ignorowania.

Brak dodatkowej kopii jest świadomym ograniczeniem tej wersji: awaria dysku może oznaczać utratę danych. Zachowanie archiwów umożliwia odbudowę bazy, ale tylko gdy same archiwa pozostały dostępne.
