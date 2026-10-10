# Cel i wymagania

Ustalenia z rozmowy, 2026-10-10. Wymagania użytkownika mają pierwszeństwo przed propozycjami implementacji w pozostałych dokumentach.

## Cel

Zapewnić pełne zachowanie danych dostępnych w dziennym eksporcie dobrostanu Garmin oraz czytelny eksport danych dla modeli AI. Dane będą kontekstem do analizy zdrowia, snu, anomalii i trendów oraz konkretnych problemów medycznych. Interpretację i łączenie z innymi źródłami wykonuje model AI poza aplikacją.

## Użytkownik i środowisko

- Jeden użytkownik, jedno prywatne konto Garmin.
- Jeden zegarek: Garmin Epix gen 2, używany nieprzerwanie od nieustalonej daty w 2024 roku.
- Początkowo ręczne uruchamianie konsoli na Windows; w przyszłości Raspberry Pi i codzienny harmonogram.
- Python i SQLite. Bez interfejsu graficznego w pierwszej wersji.

## Zakres pierwszej wersji

1. Jedna metoda pobierania: WebAPI dziennego archiwum dobrostanu ZIP, po potwierdzeniu zgodności z ręcznym eksportem.
2. Pierwszy import sprawdza każdy dzień od 2024-01-01 do wczoraj. Nieznany początek historii ustala się na podstawie uzyskanych danych; dni bez danych nie są błędami sieciowymi.
3. Kolejne uruchomienia pobierają niepobrane dni, także zaległości. Nigdy nie pobierają dzisiejszego ani przyszłego dnia.
4. Zachowanie oryginalnych archiwów oraz dekodowanie danych do SQLite bez utraty dostępnych pól.
5. Ręczne generowanie JSON z wyborem parametrów i okresu.
6. Dane źródłowe i SQLite stanowią trwałe zasoby. Eksporty są plikami wynikowymi tworzonymi na żądanie, nie kolejnym archiwum.

## Poza zakresem

- Osobne pobieranie treningów i dodatkowych metryk z innych endpointów.
- Automatyczne ponowne pobieranie zakończonych dni i przyrostowe aktualizacje dawnych danych.
- Własne średnie, agregaty, trendy, anomalie, diagnozy i dodatkowe wskaźniki.
- Instrukcje lub interpretacje dla AI w plikach eksportu.
- Automatyczny eksport, UI, WebAPI aplikacji, MCP i bezpośrednie odpytywanie bazy przez model.
- Automatyczne kopie zapasowe i dodatkowe trwałe kopie danych.

Nie odrzucać pól znajdujących się w archiwum dlatego, że dotyczą wysiłku. Ograniczenie treningów dotyczy osobnego pobierania, a nie usuwania zawartości ZIP.

## Przechowywanie

Początkowo folder projektu, z konfigurowalną ścieżką. Oryginalne archiwa, SQLite, eksporty, logi i sesje nigdy nie trafiają do Git. Przed użyciem niestandardowego katalogu w repozytorium należy sprawdzić reguły ignorowania.

Brak dodatkowej kopii jest świadomym ograniczeniem tej wersji: awaria dysku może oznaczać utratę danych. Zachowanie archiwów umożliwia odbudowę bazy, ale tylko gdy same archiwa pozostały dostępne.
