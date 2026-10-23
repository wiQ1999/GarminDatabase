# Plan realizacji i kryteria odbioru

Stan 2026-10-23: zrealizowano rdzeń, importer, eksport i UI Windows. Historia jest w PostgreSQL; testy jednostkowe, integracyjne, UI oraz uruchomienie paczki opisuje [instrukcja](12-running-and-testing.md). Poniższe etapy zachowują wymagania odbioru; etap Raspberry Pi/huba pozostaje przyszłym rozszerzeniem.

## Etap 0: próba źródła

Uruchomić `scripts/probe_wellness.py` dla 2026-10-09 na koncie użytkownika. Porównać ZIP z ręcznym wzorcem; przy różnicach porównać zdekodowaną zawartość. Potwierdzić MFA, format odpowiedzi, starszą datę i sposób sygnalizowania braku danych. Zanotować wersję biblioteki. Jeśli źródła nie są równoważne, zatrzymać realizację importera i wyjaśnić ograniczenie użytkownikowi; nie dołączać innych endpointów bez zmiany zakresu.

Odbiór: dowód zgodności zawartości lub jednoznacznie opisane różnice zaakceptowane przez użytkownika.

## Etap 1: dekoder i model danych

Historyczny etap analizy SQLite: przeskanowano całą pobraną historię. Obecnie używamy [schematu PostgreSQL v1](10-postgresql-schema.md). Struktura jest odczytywana przez fitdecode 0.11.0, a aktualna semantyka korzysta z profilu Garmin FIT SDK 21.218.0. Wyniki, pokrycie i ograniczenia są w [analizie](08-fit-analysis.md). Importer, kontekst czasu, reguły profilu i zapis do PostgreSQL są zaimplementowane i testowane.

Wybrać parser FIT na podstawie pokrycia wiadomości z próbki. Zidentyfikować wszystkie pola, szczegółowość, jednostki, znaczniki czasu i podsumowania dostarczane przez Garmin. Potwierdzić interpretację czasu na przykładzie pobudki około 07:00, traktując to jako orientacyjny punkt kontrolny, nie sposób przesuwania danych. Zbudować schemat PostgreSQL z pochodzeniem rekordów i ewidencją pól nieznanych. Przypiąć zależności i wersję profilu FIT.

Odbiór: każdy rekord/nieobsługiwany fragment ma rozliczalne pochodzenie, archiwum pozostaje niezmienione, ponowne przetworzenie nie duplikuje danych.

## Etap 2: importer historii i zaległości

Zbudować rdzeń operacji niezależny od UI: konfigurację katalogu i strefy, logowanie, stany dni, zapis atomowy i transakcje. Udostępnić go aplikacji Windows opisanej w [specyfikacji UI](11-desktop-ui.md). Pierwsza wersja nie wymaga konsoli od użytkownika. Najpierw mały zakres, następnie historia od 2024-01-01. Import ręczny, bez harmonogramu.

Odbiór: dzisiejsza data jest wykluczona; zakończone dni nie są ponownie pobierane; błąd nie jest oznaczany jako brak danych; przerwane zadanie można wznowić; błąd dekodowania nie wymaga kolejnego pobrania.

## Etap 3: eksport

Wprowadzić katalog parametrów oparty na dekodowanych danych. Zbudować oddzielne pliki `history/{parametr}.json` z podsumowaniami i `details/{parametr}.json` z pełnymi danymi ostatnich wybranych dni. Średnie dzienne i miesięczne oraz podsumowania kategorii i liczników realizują późniejsze wymaganie użytkownika. Każde generowanie tworzy nowy folder z datą i czasem. Sprawdzić rozmiary i odczyt przez AI. Nie dodawać instrukcji dla AI ani interpretacji.

Odbiór: poprawny JSON, wszystkie wybrane próbki zachowane, zgodne wartości i jednostki, brak interpretacji, zakres i luki widoczne. Jeden plik na parametr bez automatycznego dzielenia.

## Etap 4: aplikacja Windows i wykresy

Wybrać technologię UI, wykresów i pakowania zgodną z Pythonem oraz samodzielnym `.exe` na Windows 11. Zrealizować Start, Dane, Eksport i Ustawienia, ciemny motyw z niebieskimi akcentami oraz ikony według referencji. Formularz logowania obsługuje MFA i sesję szyfrowaną DPAPI poza bazą; ustawienia są w `%LOCALAPPDATA%/GarminDatabase/settings.json`.

Połączyć „Pobierz dane” z pobieraniem i importem w tle, dodać postęp, zatrzymanie i wznowienie. Przeglądanie dotyczy zatwierdzonych danych podczas importu. Dla pojedynczego dnia pokazywać szczegółowe próbki, dla dłuższych zakresów podsumowania Garmin lub oznaczone średnie dzienne pięciu obsługiwanych pomiarów. Bez tabel rekordów i powiększania wykresu. Eksport zachowuje wcześniejsze wyniki i zapamiętuje ustawienia.

Aktualizacja przeglądania: wykres ładuje się po zmianie parametru, zakresu i dat, bez dodatkowego przycisku. Podczas zapytania pokazuje spinner i rozmywa poprzedni obraz. Niedostępne zakresy są wyszarzone; wybór serii bez podsumowań Garmin i bez obsługiwanej średniej przełącza na dzień. Checkbox włącza regresję liniową na wyświetlanych danych liczbowych, bez utrwalania obliczeń. Testować również szybkie zmiany filtrów, zakończenie ładowania po błędzie i brak trendu dla kategorii.

Odbiór: kryteria ze specyfikacji UI, uruchomienie na Windows 11 bez osobnej instalacji Pythona, poprawne współbieżne przeglądanie i import oraz brak sekretów w ustawieniach i logach. Etapy rdzenia i UI można realizować częściowo równolegle, ale pierwszy produkt dla użytkownika ma interfejs okienkowy.

## Etap 5: codzienne uruchamianie i hub danych

Po stabilizacji wprowadzić harmonogram na Raspberry Pi bez UI. Wspólna operacja `sync` nadrabia zaległe dni i kończy na wczoraj. Eksport pozostaje ręczny. Zaprojektować udostępnianie danych z Raspberry Pi jako huba oraz mechanizm ochrony sesji na Linux; protokół dostępu i relacja z aplikacją Windows nie są jeszcze ustalone.

## Późniejsze rozszerzenia

Aktualizacja pobranych dni, podział dużych eksportów, inne metryki lub treningi i sieciowy hub danych wymagają osobnego doprecyzowania zakresu. Lokalny MCP tylko do odczytu jest już zaimplementowany w ograniczonym zakresie: katalog, podsumowania dzienne i średnie całego okresu dla pięciu istniejących metryk. Korzysta ze wspólnych reguł eksportu i niezależnych list parametrów w Ustawieniach. Kolejne funkcje MCP, HTTP i Raspberry Pi są późniejszym etapem. Dodatkowe kopie zapasowe nie są obecnie planowane. Kontrakt, dystrybucję i odbiór opisuje [instrukcja](12-running-and-testing.md).

## Konieczne sprawdzenia implementacji

- Zgodność ręcznego i automatycznego archiwum.
- Wierność pól FIT i obsługa nieznanych pól.
- Granice dat, zmiana czasu letniego i zimowego oraz rekordy przekraczające datę żądania.
- Wznowienie po błędzie, po zapisaniu ZIP przed transakcją i po przerwaniu dekodowania.
- Idempotencja ponownego przetwarzania oraz brak fałszywych duplikatów.
- Poprawność JSON i zgodność eksportowanych wartości z bazą i źródłem.
- `git check-ignore` dla archiwów, PostgreSQL, sesji i eksportów; brak sekretów w logach.

## Pozostałe niewiadome

Zgodność WebAPI z ręcznym eksportem została potwierdzona dla 2026-10-09; dostępność archiwów i katalog pól sprawdzono dla całego pobranego zakresu. Skrócone czasy, komponenty i subpola są pokryte testami. Zmierzono bazę i przykładowy eksport, a zapisanie i wznowienie sesji sprawdzono; [wyniki odbioru](12-running-and-testing.md).

Nadal nie ustalono znaczenia 169 odpowiedzi 404 ani semantyki 737 wariantów pól nieopisanych publicznie. Aplikacja pokazuje te ograniczenia i zachowuje źródła. Przyszłe zmiany usługi Garmin, wygaśnięcie sesji na rzeczywistym koncie i wielkość eksportu przy innym wyborze parametrów wymagają kontroli w użytkowaniu. Nie są to brakujące funkcje pierwszej wersji.
