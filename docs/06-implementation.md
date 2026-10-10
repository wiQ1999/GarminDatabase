# Plan realizacji i kryteria odbioru

## Etap 0: próba źródła

Uruchomić `scripts/probe_wellness.py` dla 2026-10-09 na koncie użytkownika. Porównać ZIP z ręcznym wzorcem; przy różnicach porównać zdekodowaną zawartość. Potwierdzić MFA, format odpowiedzi, starszą datę i sposób sygnalizowania braku danych. Zanotować wersję biblioteki. Jeśli źródła nie są równoważne, zatrzymać realizację importera i wyjaśnić ograniczenie użytkownikowi; nie dołączać innych endpointów bez zmiany zakresu.

Odbiór: dowód zgodności zawartości lub jednoznacznie opisane różnice zaakceptowane przez użytkownika.

## Etap 1: dekoder i model danych

Wybrać parser FIT na podstawie pokrycia wiadomości z próbki. Zidentyfikować wszystkie pola, szczegółowość, jednostki, znaczniki czasu i podsumowania dostarczane przez Garmin. Potwierdzić interpretację czasu na przykładzie pobudki około 07:00, traktując to jako orientacyjny punkt kontrolny, nie sposób przesuwania danych. Zbudować schemat SQLite z pochodzeniem rekordów i ewidencją pól nieznanych. Przypiąć zależności i wersję profilu FIT.

Odbiór: każdy rekord/nieobsługiwany fragment ma rozliczalne pochodzenie, archiwum pozostaje niezmienione, ponowne przetworzenie nie duplikuje danych.

## Etap 2: importer historii i zaległości

Zbudować konsolę, konfigurację katalogu i strefy, bezpieczne lokalne logowanie, stany dni, zapis atomowy i transakcje. Najpierw mały zakres, następnie historia od 2024-01-01. Import ręczny, bez harmonogramu.

Odbiór: dzisiejsza data jest wykluczona; zakończone dni nie są ponownie pobierane; błąd nie jest oznaczany jako brak danych; przerwane zadanie można wznowić; błąd dekodowania nie wymaga kolejnego pobrania.

## Etap 3: eksport

Wprowadzić katalog parametrów oparty na dekodowanych danych. Zbudować pliki historii źródłowych podsumowań oraz `recent.json`, a także pełny eksport wskazanego okresu. Sprawdzić rozmiar pakietu dla rzeczywistego 90-dniowego zakresu i ręczny odczyt w Claude i ChatGPT. Nie dodawać instrukcji dla AI ani obliczanych agregatów.

Odbiór: poprawny JSON, wszystkie wybrane próbki zachowane, zgodne wartości i jednostki, brak interpretacji, zakres i luki widoczne. Jeden plik na parametr bez automatycznego dzielenia.

## Etap 4: codzienne uruchamianie

Po stabilizacji wprowadzić harmonogram na Raspberry Pi. To samo polecenie `sync` nadrabia zaległe dni i kończy na wczoraj. Eksport pozostaje ręczny.

## Późniejsze rozszerzenia

Aktualizacja pobranych dni, podział dużych eksportów, inne metryki lub treningi, UI, bezpośredni dostęp agenta, API/MCP. Każde wymaga osobnego doprecyzowania zakresu. Dodatkowe kopie zapasowe nie są obecnie planowane.

## Konieczne sprawdzenia implementacji

- Zgodność ręcznego i automatycznego archiwum.
- Wierność pól FIT i obsługa nieznanych pól.
- Granice dat, zmiana czasu letniego i zimowego oraz rekordy przekraczające datę żądania.
- Wznowienie po błędzie, po zapisaniu ZIP przed transakcją i po przerwaniu dekodowania.
- Idempotencja ponownego przetwarzania oraz brak fałszywych duplikatów.
- Poprawność JSON i zgodność eksportowanych wartości z bazą i źródłem.
- `git check-ignore` dla archiwów, SQLite, sesji i eksportów; brak sekretów w logach.

## Pozostałe niewiadome

Zgodność kandydata WebAPI; dostępność historii; dokładne pola i metryki; rozróżnianie braku danych; zakres obsługi parsera; potrzeba MFA; objętość JSON. Nie są to brakujące decyzje produktowe, tylko pytania wymagające prób technicznych.
