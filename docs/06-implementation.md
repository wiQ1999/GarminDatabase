# Plan realizacji i kryteria odbioru

## Etap 0: próba źródła

Uruchomić `scripts/probe_wellness.py` dla 2026-10-09 na koncie użytkownika. Porównać ZIP z ręcznym wzorcem; przy różnicach porównać zdekodowaną zawartość. Potwierdzić MFA, format odpowiedzi, starszą datę i sposób sygnalizowania braku danych. Zanotować wersję biblioteki. Jeśli źródła nie są równoważne, zatrzymać realizację importera i wyjaśnić ograniczenie użytkownikowi; nie dołączać innych endpointów bez zmiany zakresu.

Odbiór: dowód zgodności zawartości lub jednoznacznie opisane różnice zaakceptowane przez użytkownika.

## Etap 1: dekoder i model danych

Stan: przeskanowano całą pobraną historię i ustalono [schemat SQLite v1](10-sqlite-schema.md). Struktura jest odczytywana przez fitdecode 0.11.0, a aktualna semantyka korzysta z profilu Garmin FIT SDK 21.218.0. Wyniki, pokrycie i ograniczenia są w [analizie](08-fit-analysis.md). Pozostaje realizacja importera, poprawna obsługa kontekstu czasu i reguł komponentów oraz zapis danych do bazy.

Wybrać parser FIT na podstawie pokrycia wiadomości z próbki. Zidentyfikować wszystkie pola, szczegółowość, jednostki, znaczniki czasu i podsumowania dostarczane przez Garmin. Potwierdzić interpretację czasu na przykładzie pobudki około 07:00, traktując to jako orientacyjny punkt kontrolny, nie sposób przesuwania danych. Zbudować schemat SQLite z pochodzeniem rekordów i ewidencją pól nieznanych. Przypiąć zależności i wersję profilu FIT.

Odbiór: każdy rekord/nieobsługiwany fragment ma rozliczalne pochodzenie, archiwum pozostaje niezmienione, ponowne przetworzenie nie duplikuje danych.

## Etap 2: importer historii i zaległości

Zbudować rdzeń operacji niezależny od UI: konfigurację katalogu i strefy, logowanie, stany dni, zapis atomowy i transakcje. Udostępnić go aplikacji Windows opisanej w [specyfikacji UI](11-desktop-ui.md). Pierwsza wersja nie wymaga konsoli od użytkownika. Najpierw mały zakres, następnie historia od 2024-01-01. Import ręczny, bez harmonogramu.

Odbiór: dzisiejsza data jest wykluczona; zakończone dni nie są ponownie pobierane; błąd nie jest oznaczany jako brak danych; przerwane zadanie można wznowić; błąd dekodowania nie wymaga kolejnego pobrania.

## Etap 3: eksport

Wprowadzić katalog parametrów oparty na dekodowanych danych. Zbudować pliki historii źródłowych podsumowań oraz `recent.json`, a także pełny eksport wskazanego okresu. Sprawdzić rozmiar pakietu dla rzeczywistego 90-dniowego zakresu i ręczny odczyt w Claude i ChatGPT. Nie dodawać instrukcji dla AI ani obliczanych agregatów.

Odbiór: poprawny JSON, wszystkie wybrane próbki zachowane, zgodne wartości i jednostki, brak interpretacji, zakres i luki widoczne. Jeden plik na parametr bez automatycznego dzielenia.

## Etap 4: aplikacja Windows i wykresy

Wybrać technologię UI, wykresów i pakowania zgodną z Pythonem oraz samodzielnym `.exe` na Windows 11. Zrealizować Start, Dane, Eksport i Ustawienia, ciemny motyw z niebieskimi akcentami oraz ikony według referencji. Formularz logowania obsługuje MFA i sesję szyfrowaną DPAPI poza bazą; ustawienia są w `%LOCALAPPDATA%/GarminDatabase/settings.json`.

Połączyć „Pobierz dane” z pobieraniem i importem w tle, dodać postęp, zatrzymanie i wznowienie. Przeglądanie dotyczy zatwierdzonych danych podczas importu. Dla pojedynczego dnia pokazywać szczegółowe próbki, dla dłuższych zakresów tylko podsumowania Garmin; brak podsumowań nie uruchamia agregacji. Bez tabel rekordów i powiększania wykresu. Eksport zastępuje wcześniejsze wyniki i zapamiętuje ustawienia.

Odbiór: kryteria ze specyfikacji UI, uruchomienie na Windows 11 bez osobnej instalacji Pythona, poprawne współbieżne przeglądanie i import oraz brak sekretów w ustawieniach i logach. Etapy rdzenia i UI można realizować częściowo równolegle, ale pierwszy produkt dla użytkownika ma interfejs okienkowy.

## Etap 5: codzienne uruchamianie i hub danych

Po stabilizacji wprowadzić harmonogram na Raspberry Pi bez UI. Wspólna operacja `sync` nadrabia zaległe dni i kończy na wczoraj. Eksport pozostaje ręczny. Zaprojektować udostępnianie danych z Raspberry Pi jako huba oraz mechanizm ochrony sesji na Linux; protokół dostępu i relacja z aplikacją Windows nie są jeszcze ustalone.

## Późniejsze rozszerzenia

Aktualizacja pobranych dni, podział dużych eksportów, inne metryki lub treningi, bezpośredni dostęp agenta, API/MCP. Każde wymaga osobnego doprecyzowania zakresu. UI jest już częścią pierwszej wersji; przyszły hub danych wymaga ustalenia sposobu dostępu. Dodatkowe kopie zapasowe nie są obecnie planowane.

## Konieczne sprawdzenia implementacji

- Zgodność ręcznego i automatycznego archiwum.
- Wierność pól FIT i obsługa nieznanych pól.
- Granice dat, zmiana czasu letniego i zimowego oraz rekordy przekraczające datę żądania.
- Wznowienie po błędzie, po zapisaniu ZIP przed transakcją i po przerwaniu dekodowania.
- Idempotencja ponownego przetwarzania oraz brak fałszywych duplikatów.
- Poprawność JSON i zgodność eksportowanych wartości z bazą i źródłem.
- `git check-ignore` dla archiwów, SQLite, sesji i eksportów; brak sekretów w logach.

## Pozostałe niewiadome

Zgodność WebAPI z ręcznym eksportem została potwierdzona dla 2026-10-09; dostępność archiwów i katalog pól sprawdzono dla całego pobranego zakresu. Pozostają: znaczenie 169 odpowiedzi 404, semantyka 737 wariantów pól nieopisanych publicznie, weryfikacja czasu skróconego i reguł komponentów w importerze, zachowanie zapisanej sesji po wygaśnięciu oraz rzeczywisty rozmiar bazy i eksportów JSON. Nie są to brakujące decyzje produktowe, tylko pytania wymagające dalszych prób technicznych.
