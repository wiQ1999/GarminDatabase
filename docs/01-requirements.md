# Cel i wymagania

Dokument określa obowiązujący zakres aplikacji i kierunki rozwoju. Szczegóły dostępnych funkcji opisują dokumenty wskazane w [indeksie](README.md).

## Cel

Zachować dane dostępne w dziennym eksporcie dobrostanu Garmin i udostępnić je do przeglądania oraz analizy poza aplikacją. Eksport JSON i lokalny MCP dostarczają dane i metadane kompletności; interpretacja zdrowia, łączenie z innymi źródłami i diagnozy pozostają poza aplikacją.

## Środowisko

- Prywatne konto jednego użytkownika Garmin; źródłem są dzienne archiwa dobrostanu, nie zestaw wszystkich endpointów platformy.
- Aplikacja okienkowa Windows 11, uruchamiana ręcznie z EXE, bez konsoli, instalatora i osobnej instalacji Pythona.
- Rdzeń Python 3.12+, PostgreSQL Community 16+, psycopg 3. Ten sam silnik lokalnie i na serwerze; bez fallbacku SQLite i bez migracji jego danych.
- Polski interfejs PySide6/Qt Widgets, wykresy QPainter i dystrybucja PyInstaller onedir.
- Import, przetwarzanie i eksport są oddzielone od UI. Sesja Garmin tej wersji wymaga Windows DPAPI.

## Dostępny zakres

1. Pobieranie dziennego ZIP dobrostanu przez WebAPI. Domyślny początek historii to 2024-01-01, koniec to dzisiaj według Europe/Warsaw. Użytkownik może zawęzić zakres.
2. Pobieranie przyrostowe od ostatniego pobranego dnia oraz pobieranie całego zakresu. Wcześniejsze błędy i nieukończone importy są ponawiane. Import lokalnych ZIP i ponowne dekodowanie pozostają w CLI.
3. Zachowanie definicji i fizycznych pól FIT w PostgreSQL bez trwałego zapisywania pobieranych ZIP, także bez rozpoznanej nazwy lub semantyki. Identyczne treści FIT są deduplikowane po SHA-256.
4. Ekrany Start, Dane, Eksport i Ustawienia; postęp, zatrzymanie i przeglądanie już zatwierdzonych danych podczas importu.
5. Szczegóły pojedynczego dnia. Dłuższe zakresy pokazują oryginalne podsumowania Garmin albo oznaczone średnie dzienne HRV, tętna, oddechu, saturacji i stresu. Wykres odświeża się automatycznie; opcjonalny trend jest tylko prezentacją.
6. Ręczny eksport JSON v2 z wyborem parametrów, zakresu, dnia/miesiąca podsumowań i ostatnich N dni szczegółów. Każdy eksport tworzy nowy folder i zachowuje poprzednie pakiety.
7. Niezależne listy udostępniania eksportu i MCP. Pusta lista nie udostępnia żadnych danych; nowe serie nie włączają się same.
8. Lokalny MCP przez `stdio`: katalog, podsumowania dzienne i statystyki całego okresu dla pięciu obsługiwanych średnich pomiarów. Bez zapisów do bazy, sesji Garmin i serwera HTTP.
9. Logowanie Garmin z MFA i zaszyfrowaną sesją DPAPI. Hasła i kody MFA nie są zapisywane; błędy nie ujawniają sekretów ani treści odpowiedzi.

## Granice interpretacji i przechowywania

Nie interpolować, nie wypełniać luk zerami i nie zgadywać prywatnych metryk. Liczniki, kategorie i podsumowania Garmin zachowują odrębne znaczenie. Średnia próbek nie dowodzi pełnego pokrycia doby ani czasu noszenia zegarka. Nie odrzucać pól obecnych w ZIP tylko dlatego, że dotyczą wysiłku.

Archiwa, PostgreSQL i eksporty są trwałymi zasobami użytkownika. Foldery danych są konfigurowalne. Sesje, hasła, pomiary, logi i eksporty pozostają poza Git. Ochrona nośnika oraz kopie zapasowe wymagają konfiguracji niezależnej od aplikacji; nie ma automatycznych kopii ani własnego szyfrowania bazy.

## Kierunki rozwoju i funkcje poza zakresem

- Kolektor cykliczny Windows/Linux/Raspberry Pi OS ma [uzgodnioną specyfikację do realizacji](15-scheduled-collector.md): jednorazowy proces przez harmonogram systemowy, domyślnie co 2 h i minimum co 15 min, wspólne przyrostowe pobieranie, osobne konto i sesja oraz lokalne zarządzanie. Funkcja nie jest jeszcze dostępna.
- Raspberry Pi jako hub danych, protokół udostępniania i zdalna relacja z aplikacją Windows pozostają osobnym późniejszym zakresem.
- Sieciowy HTTP/API, zdalny MCP i dodatkowe kanały udostępniania wymagają osobnego projektu.
- Osobne pobieranie treningów, innych metryk, aktualizowanie pobranych dni i automatyczny eksport nie są dostępne.
- Kolejne funkcje MCP, źródłowe nocne podsumowania, okna godzinowe i dodatkowe statystyki wymagają doprecyzowania zakresu.
- Interpretacje medyczne, wykrywanie anomalii i instrukcje dla AI w plikach eksportu nie należą do zakresu aplikacji.

Testy techniczne nie dowodzą dostępności całej historii ani wszystkich metryk u każdego użytkownika. Odpowiedź 404 pozostaje nierozstrzygnięta, dopóki nie ma wiarygodnego potwierdzenia braku danych.
