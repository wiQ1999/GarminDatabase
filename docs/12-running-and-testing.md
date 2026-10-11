# Uruchamianie aplikacji i testy

Pierwsza wersja ma interfejs Windows 11 oraz wspólny rdzeń importu i eksportu. Kod znajduje się w `garmin_database/`; `desktop.py` jest punktem wejścia paczki Windows. UI używa PySide6 Essentials 6.12.0 i własnego wykresu QPainter, a dystrybucja — PyInstaller onedir.

## Użytkowanie Windows

Uruchom `dist/GarminDatabase/GarminDatabase.exe`. Zachowaj cały folder obok pliku EXE, w tym `_internal`; pojedynczy EXE nie stanowi całej aplikacji. Nie trzeba instalować Pythona ani uruchamiać konsoli.

W checkoutcie projektu paczka automatycznie wybiera istniejący katalog `data/`. Po skopiowaniu samej dystrybucji w inne miejsce domyślne dane są obok EXE; istniejące archiwa można wskazać w Ustawieniach. Dotychczasowe ustawienia użytkownika mają pierwszeństwo nad domyślną lokalizacją.

1. W Ustawieniach sprawdź folder danych, podaj e-mail i hasło Garmin, a następnie zaloguj się. Kod MFA jest wymagany tylko wtedy, gdy zażąda go Garmin. Sesja jest szyfrowana DPAPI; hasło i kod nie są zapisywane.
2. „Pobierz dane” nadrabia dni od 2024-01-01 do wczoraj i importuje je do SQLite. „Importuj lokalne archiwa” wykorzystuje istniejące ZIP bez logowania i sieci. „Przetwórz ponownie” odbudowuje wyniki dekodowania z oryginałów.
3. W Danych wybierz parametr i zakres. Wykres ładuje się automatycznie; spinner na rozmytym tle sygnalizuje odczyt. Dzień pokazuje szczegóły. Dłuższe okresy pokazują podsumowania Garmin albo oznaczone średnie dzienne HRV, tętna, oddechu, saturacji i stresu. Pozostałe serie bez podsumowań Garmin mają tylko dzień. Checkbox „Linia trendu” dodaje oznaczoną regresję tylko na wykresie; nie trafia do eksportów. Nie ma tabeli, zoomu lub interpolacji próbek.
4. W Eksporcie wybierz parametry, zakres historii, podsumowania dzienne lub miesięczne, liczbę dni szczegółów i folder nadrzędny. Powstaje nowy folder z datą i czasem, zawierający `history/{parametr}.json`, `details/{parametr}.json` i `manifest.json`. Domyślnie szczegóły obejmują ostatnie 90 dni. Nie powstaje zbiorczy `recent.json`; historia ma tylko podsumowania. Starsze eksporty pozostają na dysku. „Otwórz folder eksportu” otwiera nowy pakiet, a ustawienia są zapamiętywane.

Stan Start rozdziela datę pobrania od rejestracji i dekodowania w bazie. Nieznane pola zachowują identyfikatory źródłowe w SQLite; UI nie przypisuje im zgadywanych metryk. Ścieżka ustawień to `%LOCALAPPDATA%/GarminDatabase/settings.json`, sesji — `auth/session.bin` w tym samym katalogu. Dotychczasowa sesja skryptu w `private/garmin-session` nie jest automatycznie kopiowana do magazynu aplikacji.

## Środowisko deweloperskie

W Pythonie 3.12 utwórz `.venv`, następnie zainstaluj `requirements-dev.txt`, np. przez pip lub uv. Zależności aplikacji i narzędzi testowych są przypięte w plikach wymagań.

```powershell
uv pip install --cache-dir .uv-cache --python .venv/Scripts/python.exe -r requirements-dev.txt
.\.venv\Scripts\python.exe -m garmin_database
powershell -NoProfile -File scripts/run_tests.ps1
powershell -NoProfile -File scripts/build_windows.ps1
powershell -NoProfile -File scripts/smoke_windows.ps1
```

`run_tests.ps1` zapisuje raport JUnit i HTML coverage w ignorowanym `test-results/`. Tymczasowe katalogi testów również znajdują się w projekcie, co pozwala uruchamiać testy w ograniczonym środowisku Windows. `smoke_windows.ps1` uruchamia EXE z osobną pustą bazą, ukrytym oknem i zrzutem do testowego folderu.

Jeżeli system blokuje pliki istniejącej paczki, nie zatrzymywać aplikacji użytkownika. Można zbudować nową dystrybucję przez `scripts/build_windows.ps1 -Destination D:/Projects/GarminDatabase/dist/ui-update`, a następnie sprawdzić ją przez `scripts/smoke_windows.ps1 -Executable D:/Projects/GarminDatabase/dist/ui-update/GarminDatabase/GarminDatabase.exe`. Zachować cały nowy folder; aplikacja nadal używa tych samych ustawień i wskazanego w nich katalogu danych.

Statyczna kontrola i formatowanie:

```powershell
.\.venv\Scripts\ruff.exe check garmin_database tests desktop.py
.\.venv\Scripts\ruff.exe format --check garmin_database tests desktop.py
```

Skrypt budowania usuwa błędnie zebrane DLL ICU 78 z runtime deweloperskiego. Qt 6.12 w tej paczce korzysta z niesufiksowanego API ICU systemu Windows 11. Test uruchomienia EXE jest konieczny, ponieważ zwykłe testy Python nie wykrywają kolizji bibliotek dołączonych przez pakowanie.

## Testy według piramidy

Zestaw zawiera 195 testów: 137 jednostkowych, 44 integracyjne i 14 UI. Testy ze starych skryptów nadal są uruchamiane. Fixture FIT/ZIP są syntetyczne i mają poprawne CRC; nie zawierają danych użytkownika.

| Warstwa | Sprawdzane zachowanie |
| --- | --- |
| Jednostkowe | Typy i precyzja, sentinele, skrócone czasy, strefa i DST, ustawienia, HTTP, nazwy plików i kolizje folderów, regresja, średnie próbek i ważenie miesięczne, puste zestawienia, kategorie i liczniki bez niepoprawnego uśredniania |
| Integracyjne | ZIP → SQLite → JSON, CRC i rollback, wznowienie i deduplikacja FIT, subpola i komponenty, DPAPI, zachowanie starych eksportów, pliki per parametr, anulowanie i stany manifestu, spójny eksport podczas nowego importu, migracja v2→v3, cache, unieważnianie po reprocess i rollback cache, ponowienia HTTP |
| UI | Nawigacja, automatyczne odświeżanie, blokowanie zakresów i korekta dat, animacja ładowania, pomijanie starszych wyników i błędów, zakończenie ładowania po błędzie, przełączanie trendu, generowanie eksportu, zapis ustawień, zatrzymanie przy zamknięciu, obsługa żądania MFA |

Coverage rdzenia i CLI obejmuje także rozgałęzienia; skrypt wymaga co najmniej 85%. UI, rysowanie i biblioteki Qt są sprawdzane w osobnej warstwie testów, a nie wliczane do tego progu. Wynik coverage nie jest dowodem, że dowolna przyszła odpowiedź Garmin będzie obsłużona bez błędu; nieznana semantyka pozostaje jawna i nie powoduje usuwania oryginału.

Odbiór z 2026-10-11: wszystkie 139 testów przeszły, coverage rdzenia i CLI z rozgałęzieniami wynosi **92,36%**, a kontrola Ruff i sprawdzenie formatowania zakończyły się bez błędów. Raporty lokalne: `test-results/results.xml`, `test-results/coverage/index.html`, `test-results/final-validation.json` oraz `test-results/final-export-validation.json`. Raporty nie trafiają do Git.

## Sprawdzenie rzeczywistej historii

We wcześniejszym odbiorze do SQLite zaimportowano 844 archiwa i 10 994 FIT. Liczniki fizycznych danych były identyczne z niezależnym skanowaniem: 8 307 429 wiadomości i 20 841 953 wystąpienia pól. Zachowano 737 publicznie nierozpoznanych wariantów pól; UI udostępnia 56 rozpoznanych serii i właściwości. Baza zajmowała około 3,11 GB, oryginalne archiwa 42,33 MB. Aktualna wersja migracji wynosi 3; nowsze pobrania mogą zwiększać liczniki historii.

Walidacja z 2026-10-11 obejmuje CRC każdego FIT, kontrolę SQLite, kluczy obcych i porównanie współrzędnych katalogu semantyki z definicjami fizycznymi. Dodatkowa kontrola wykryła błąd cache opartego na adresach obiektów; cache używa teraz współrzędnych semantycznych, a objęte błędem 1314 FIT zostały ponownie przetworzone. Regresję sprawdza test 300 redefinicji wiadomości lokalnych.

Wynik końcowy: `quick_check=ok`, zero błędów kluczy obcych, zero niezgodnych powiązań katalogu, zero błędów dekodowania i zero oczekujących FIT. Wszystkie 10 994 aktywne dekodowania mają status `complete`. Kontrola SHA-256 potwierdziła, że wszystkie oryginalne ZIP pozostały niezmienione. Zbudowany EXE przeszedł test zarówno z pustą bazą, jak i z całą historią.

Klient z zaszyfrowaną sesją został również sprawdzony na rzeczywistym WebAPI: kontrolne 20 FIT za 2026-10-09 ma identyczną zawartość jak archiwum lokalne. Test eksportu dwóch parametrów z 90 dni wygenerował poprawny `recent.json` o rozmiarze 4 956 982 bajtów, ze 106 674 próbkami tętna i 91 źródłowymi wartościami nocnego HRV. Osobna historia wybranego HRV miała 12 994 bajty. Liczba wartości nie musi być równa liczbie dni: zachowujemy różne wiadomości źródłowe. Raportowano tylko rozmiary i liczniki, bez wartości pomiarowych. Błędy sieci i ponowne żądanie MFA są pokryte testami kontrolowanymi; zachowanie Garmin po przyszłych zmianach usługi wymaga ponownej weryfikacji.

## Wznowienie, rozmiar bazy i brak sesji

Zwykłe „Pobierz dane” albo import lokalny pomijają dekodowanie ukończonego FIT. Ponowne odwiedzenie niezmienionego, kompletnego ZIP nie tworzy dodatkowego przebiegu dekodowania. „Przetwórz ponownie” wymusza wymianę wyników z zachowaniem tej samej liczby pomiarów. Nie pobiera ponownie ZIP ani nie tworzy rozpakowanej kopii.

Rozmiar SQLite może rosnąć wskutek reorganizacji dużych tabel i indeksów podczas tej wymiany; aktywny WAL jest dodatkowym tymczasowym plikiem transakcji. Zwolniona przestrzeń jest używana przez SQLite ponownie, ale sam plik nie jest automatycznie zmniejszany. Dziennik `decode_runs` przechowuje małe rekordy techniczne. Rosnący rozmiar pliku nie oznacza automatycznie duplikowania danych. Kompaktowanie nie odbywa się automatycznie i wymaga zaplanowania pracy poza aktywnym importem.

Puste pola e-mail i hasła są zamierzone: aplikacja nie zapisuje hasła. Nowe pobieranie korzysta z zaszyfrowanej sesji, jeśli istnieje. Gdy sesji brak, aplikacja nadal może importować istniejące lokalne ZIP, a na pierwszym nowym dniu kończy operację z instrukcją logowania w Ustawieniach. Nie interpretuje braku pliku sesji jako odpowiedzi Garmin ani nie ponawia go trzy razy. Ustawienia pokazują, czy plik sesji istnieje; jego ważność sprawdza dopiero połączenie z usługą.

Kontrola po poprawce: wszystkie 143 testy przeszły, coverage rdzenia i CLI z gałęziami wynosi 92,38%. Dodano regresje dla braku sesji, braku niepotrzebnych ponowień, informacji w UI i pomijania fikcyjnych przebiegów importu. Wyniki wcześniejszego odbioru pełnej historii pozostają powyżej.

Kontrola po poprawkach przeglądania: wszystkie 157 testów przeszły, coverage rdzenia i CLI z gałęziami wynosi 92,50%, a sam moduł regresji jest pokryty w 100%. Testy UI sprawdzają opóźnione zapytanie, kilka zmian dat podczas odczytu oraz błąd nieaktualnego żądania. Dane testowe są syntetyczne; trend nie zmienia punktów źródłowych.

Kontrola po dodaniu pośrednich podpisów osi czasu: 166 testów przeszło, coverage rdzenia i CLI z gałęziami wynosi 92,62%. Dodatkowe testy sprawdzają dobór godzin, sekund i dat, offset podczas zmiany DST oraz czytelność podpisów po zwężeniu wykresu. Sprawdzono także wygląd na syntetycznym wykresie.

Kontrola eksportu v2 i podsumowań: 195 testów przeszło, coverage rdzenia i CLI z gałęziami wynosi **93,42%**. Same obliczenia i cache mają 97%, a eksport 98%. Testy sprawdzają także ważenie miesięcy różnymi liczbami próbek, nietimestampowane rekordy, anulowanie publikacji cache i niezmienność poprzednich pakietów. Nowe średnie są oznaczane na wykresach; dzień wciąż pokazuje źródłowe próbki. Raporty: `test-results/summary-tests-final.log` i standardowy raport HTML coverage.

Walidacja rzeczywistego eksportu v2 objęła wszystkie 56 rozpoznanych parametrów i 112 plików danych: około 6,32 MB historii podsumowań i 30,62 MB szczegółów z 90 dni. Historia HRV ma 834 wiersze i 109 943 bajty, a szczegóły HRV 8 222 rekordy i 382 723 bajty. Źródłowe tętno spoczynkowe zachowało 7 929 oryginalnych podsumowań w historii. W SQLite powstało 17 726 dziennych rekordów cache dla 30 parametrów bez reprezentacji źródłowego podsumowania.

Niezależna kontrola SQL porównała obliczone średnie, minima, maksima i liczności z fizycznymi polami FIT dla wszystkich 4 207 dni pięciu parametrów pomiarowych: brak niezgodności, tolerancja średniej 1e-7. Klucze obce są poprawne, a hashe wcześniejszych eksportów nie zmieniły się. Raporty `test-results/summary-real-validation.json` i `test-results/summary-independent-sql.log` zawierają tylko metadane i liczniki; testowe kopie prywatnych plików wynikowych usunięto po sprawdzeniu. Zbudowana paczka z migracją 003 przeszła smoke zarówno w osobnym folderze, jak i w zwykłym `dist/GarminDatabase/`. Wygląd formularza i oznaczonej średniej sprawdzono na danych syntetycznych.

## Operacje bez UI

Do lokalnych sprawdzeń i przyszłego harmonogramu służy wspólny moduł CLI:

```powershell
.\.venv\Scripts\python.exe -m garmin_database.cli status --data-dir data
.\.venv\Scripts\python.exe -m garmin_database.cli import-local --data-dir data
.\.venv\Scripts\python.exe -m garmin_database.cli reprocess --data-dir data --from 2026-09-01
.\.venv\Scripts\python.exe -m garmin_database.cli export --data-dir data --parameters monitoring.heart_rate --from 2026-09-01 --to 2026-09-30 --recent-days 30 --summary-period day --output exports
```

`sync` wymaga dostępnej sesji aplikacji Windows. Mechanizm ochrony sesji na Linux i sieciowy hub Raspberry Pi pozostają późniejszym etapem, zgodnie z uzgodnionym zakresem.
