# GarminDatabase — pamięć implementacji

## Dokumentacja i materiały lokalne

**Do `docs/` trafiają wyłącznie aktualne informacje istotne dla stanu i rozwoju aplikacji:** wymagania, cele, zakres dostępnych funkcji, kontrakty, architektura, format danych oraz instrukcje obsługi, wdrożenia i testowania. Aktualizuj właściwy dokument zamiast dopisywać historię kolejnych prób. Indeks: [docs/README.md](docs/README.md).

Analizy zbiorów danych, wygenerowane katalogi ze skanów, raporty testów/coverage, opisy incydentów, dochodzenia błędów, porównania i zakończone plany zapisuj w ignorowanym **`local-notes/`** (raporty testów mogą pozostać w `test-results/`). Nie dodawaj ich do Git ani do `docs/`. Trwałe wnioski przepisuj do aktualnej specyfikacji jako regułę działania, bez przebiegu diagnozy, numerów kolejnych paczek i wyników poszczególnych uruchomień. Przed usunięciem historycznych dokumentów zachowaj lokalny oryginał; popraw odnośniki i generatory. `scripts/render_fit_inventory_docs.py` zapisuje wyniki w `local-notes/fit-reports/`.

Pamięć projektu utrzymuj jako aktualne decyzje i ograniczenia, nie dziennik sesji. Dokumentacja śledzona w Git nie może wymagać obecności lokalnego raportu. Dane pomiarowe, hasła, tokeny i surowe prywatne wyjątki nie należą do żadnej dokumentacji.


## Bieżąca decyzja — PostgreSQL, 2026-10-23

- Użytkownik zdecydował zastąpić SQLite przez **PostgreSQL 16+**. Jeden silnik obowiązuje lokalnie i na serwerze; nie dodawać fallbacku SQLite ani wariantu lokalnego z innym SQL.
- **Nie implementować migracji danych SQLite.** Użytkownik pobierze historię ponownie i zapisze ją w PostgreSQL.
- **Przed rozpoczęciem lokalnych testów zamknąć starą aplikację/importer i usunąć starą bazę `garmin.sqlite3` oraz istniejące `garmin.sqlite3-wal`, `garmin.sqlite3-shm`, `garmin.sqlite3-journal` z faktycznego `settings.data_dir`.** Nie usuwać oryginalnych ZIP w `raw/`, sesji, ustawień, eksportów ani bazy PostgreSQL. W checkoutcie cloud przy wdrażaniu zmiany nie było starego pliku bazy do usunięcia.
- Połączenie: niepusty `Settings.database_dsn`, następnie `GARMIN_DATABASE_DSN`, następnie libpq (`PGHOST`, `PGPORT`, `PGUSER`, `PGSERVICE`; domyślna baza `garmin`). Hasło przez pgpass/PGPASSFILE lub środowisko, nigdy w settings.json; walidacja odrzuca `password` również w URI.
- Pełne testy wymagają osobnego PostgreSQL wskazanego przez `GARMIN_TEST_DATABASE_DSN`. Każdy test integracyjny/UI tworzy własny schemat i go usuwa. Nie wskazywać bazy użytkownika. Testy nie mogą cicho pomijać braku PostgreSQL.
- Serwer nie jest częścią EXE. Konfiguracja Windows/Linux/Raspberry Pi OS i ochrona danych: [docs/13-postgresql-setup.md](docs/13-postgresql-setup.md). PostgreSQL sam nie szyfruje plików: osobno zabezpieczyć nośnik, WAL, backup, oryginalne ZIP i eksporty; zdalnie TLS `verify-full`.

## Projekt i zasady danych

- Checkout Windows: `D:/Projects/GarminDatabase`; wcześniejszy C: nie jest głównym checkoutem. W środowisku cloud: `/workspace/GarminDatabase`.
- Python 3.12+, PostgreSQL, psycopg 3. Zachowujemy fizyczne pola FIT raz, oryginalne ZIP bez zmian i wersjonowaną semantykę publicznego profilu. Nie zgadujemy prywatnych metryk.
- Polski UI Windows 11: PySide6 Essentials/Qt Widgets, wykres QPainter, PyInstaller onedir bez konsoli. Rdzeń nie importuje Qt. Raspberry Pi: rdzeń bez UI; ochrona sesji Linux i protokół huba wymagają osobnego projektu.
- Sesja Garmin: DPAPI użytkownika, `%LOCALAPPDATA%/GarminDatabase/auth/session.bin`, bez hasła/MFA. Nie logować surowych wyjątków Garmin/psycopg, tokenów, parametrów połączenia ani pomiarów. Dwa testy prawdziwego DPAPI wymagają Windows i mają jawny skip na Linux.
- Dane, eksporty, logi, build/dist, work i raporty są ignorowane w Git. Testy korzystają z syntetycznych FIT/ZIP, nigdy prywatnych fixture. Skany rzeczywistych danych mogą raportować wyłącznie liczniki i bezpieczne metadane; usuwać tylko własne testowe kopie.

## PostgreSQL i import

- Schemat i aktualizacje są w `schema/` i `garmin_database/resources/`; treść obu kopii musi być identyczna. `schema_migrations` przechowuje wersje 1–3 i SHA-256, bez PRAGMA/user_version. Inicjalizacja jest atomowa, odrzuca przyszłą wersję i niezgodne SHA.
- Identyfikatory/timestampy: BIGINT, generowanie przez IDENTITY i `RETURNING id`; zmiennoprzecinkowe: DOUBLE PRECISION. JSON jest tekstem walidowanym przez CHECK `::json`, z dotychczasowym kontraktem serializacji. Kolumna `offset` wymaga cudzysłowów w SQL PostgreSQL.
- Każdy FIT jest transakcyjny; CRC/błąd/anulowanie wycofują cały nieukończony wynik, także wymianę poprzedniego dekodowania. Ponowny import kompletnych ZIP nie tworzy fikcyjnych `decode_runs`. Hash FIT deduplikuje treść między archiwami; zapytania nie mnożą pomiarów przez pochodzenie.
- `Database.writer_lock()` łączy lokalną blokadę OS z PostgreSQL session advisory lock dla bazy/schematu; działa między hostami. Importer, Sync, inicjalizacja i cache respektują tę samą blokadę. Zagnieżdżenie na tym samym obiekcie/wątku jest dozwolone dla pipeline; cache używa `allow_nested=False` i pomija publikację przy zajętym writerze.
- Odczyty: `REPEATABLE READ READ ONLY`, wartości i metadane kompletności z jednego połączenia/snapshotu. Strumieniowanie próbek przez nazwany kursor serwerowy po 1000 wierszy; zamknąć go także po przerwaniu generatora.
- `dataset_state`, `summary_cache`, `daily_summaries` i widok aktualnych podsumowań są odtwarzalne i wersjonowane. Triggery PostgreSQL podnoszą rewizję raz na instrukcję; rollback cofa rewizję. Cache publikuje osobnym połączeniem po uzyskaniu blokady i potwierdzeniu rewizji, bez częściowych wyników po anulowaniu.
- Indeks `fit_fields(field_definition_id, message_definition_id)` jest konieczny przy zastępowaniu dekodowania. Nie uruchamiać automatycznie `VACUUM FULL`. PostgreSQL używa autovacuum; wzrost rozmiaru nie oznacza powielenia pomiarów.
- Cache opisów FIT używa współrzędnych semantycznych, nigdy `id(field_def)`. Regresja: 300 redefinicji. Nieznany czas pozostaje NULL; dzień żądania jest osobnym metadanym, również w eksporcie. Skrócone czasy rekonstruować tylko z kontekstu FIT.

## UI, podsumowania i eksport

- Start/Dane/Eksport/Ustawienia, ciemny motyw. „Pobierz dane” pobiera tylko do wczoraj Europe/Warsaw i importuje. Brak sesji to `SessionRequired` z instrukcją logowania, bez sieciowych ponowień. Import lokalny nie wymaga logowania i nie dowodzi pobrania nowych danych.
- Szczegóły wyłącznie dnia; dłuższe okresy: oryginalne podsumowania Garmin i oznaczone średnie dzienne HRV/tętna/oddechu/saturacji/stresu. `MEAN_PARAMETERS` jest jawną listą; bez ważenia czasem, wypełniania luk i ujemnych wartości stresu. Miesiąc ważony licznością poprawnych próbek. Kategorie: liczności; liczniki: ostatnia obserwacja.
- Wykres odświeża się po zmianie filtrów. Jeden worker i ostatnie oczekujące żądanie, odrzucanie nieaktualnych wyników/błędów. Spinner pozostaje do aktualnego wyniku; nie odpinać go po zakończeniu starego żądania. Qt ComboBox wymaga QStyledItemDelegate dla koloru nieaktywnych pozycji.
- `trend.linear_trend`: regresja względem rzeczywistego czasu, skończone wartości, minimum dwa różne czasy. Przerywana linia tylko w UI, bez zmiany danych i JSON. `time_axis` dobiera podpisy Europe/Warsaw i offset DST po pomiarze szerokości, z odstępem co najmniej 12 px.
- Eksport v2: strumieniowy i atomowy per plik, nowy folder z datą/czasem, manifest, `history/{parametr}.json`, `details/{parametr}.json`. Nie usuwać starych eksportów, nie tworzyć recent.json ani pełnych próbek w historii. `full_samples` jest ignorowane, `summary_period` wybiera dzień/miesiąc. `ExportResult` zwraca folder i rozmiary.
- Ponowienia respektują Retry-After w sekundach i HTTP-date. 401/403/429 zatrzymują pobieranie. Oczekiwanie przez Event.wait, aby można było zatrzymać operację.

## Walidacja i workflow

- Pełny runner: `python scripts/run_tests.py`; Windows wrapper: `scripts/run_tests.ps1`. Coverage rdzenia/CLI z gałęziami: minimum 85%; GUI jest osobną warstwą.
- Build: `python scripts/build.py`, Windows `scripts/build_windows.ps1 -Destination ...`. Pakować psycopg_binary/libpq i resources SQL. Build usuwa błędnie zebrane root DLL ICU 78 na Windows, bo Qt 6.12 wymaga niesufiksowanego ICU Windows 11.
- Smoke: `python scripts/smoke.py`, Windows `scripts/smoke_windows.ps1`. Używa własnego schematu w bazie testowej; nie wskazywać bazy aplikacji. Nie zatrzymywać EXE użytkownika w celu nadpisania; zbudować do innego folderu.
- Build/smoke Linux nie dowodzi poprawności EXE i DPAPI Windows. Wyniki historycznego odbioru pełnej historii SQLite nie zastępują odbioru PostgreSQL. Szczegóły: [docs/12-running-and-testing.md](docs/12-running-and-testing.md), [schemat](docs/10-postgresql-schema.md).
- Po większych etapach Conventional Commits, jawne listy plików w staging, bez pytania — użytkownik zatwierdził workflow. Push nie jest automatycznie częścią zlecenia.

## Odczyt, eksport i MCP

Lokalny MCP używa oficjalnego `mcp==1.28.0` i transportu `stdio`, bez Qt, sesji Garmin i zapisów do PostgreSQL. `mcp_stdio.py` jest osobnym punktem wejścia, pakowanym jako `GarminDatabaseMCP/GarminDatabaseMCP.exe` obok folderu GUI. Klient uruchamia proces; UI kopiuje konfigurację z bezwzględnymi ścieżkami. Narzędzia to `garmin_catalog`, `get_daily` i `get_period_stats` dla pięciu `MEAN_PARAMETERS`. Kontrakt: [docs/12-running-and-testing.md](docs/12-running-and-testing.md).

`DataAccess.snapshot` zapewnia wspólny katalog, rewizję, wartości i kompletność w jednej transakcji `REPEATABLE READ READ ONLY`. MCP zawsze używa `publish_cache=False`, także przy zimnym odczycie. Wewnętrzny czas pozostaje UTC; dni i prezentacja MCP są w Europe/Warsaw z pełnym offsetem. Eksport v2 zachowuje UTC i precyzję oraz podaje `calendar_timezone` i `timestamp_timezone`. `period_summary` jest wspólnym reduktorem średniej ważonej liczbą poprawnych próbek dni dla eksportu miesięcznego i okresów MCP.

Ustawienia v2 mają niezależne `export_parameters`, `mcp_parameters` i `mcp_enabled`. Puste listy oznaczają brak dostępu; dawny pusty wybór eksportu migruje jednorazowo na jawny katalog. Nowe serie nie włączają się same. GUI, CLI i bezpośredni eksporter respektują wybór. MCP sprawdza zapisaną politykę przy zapytaniu i przed publikacją. Zmiana polityki, rozstrzygniętego połączenia, OID bazy/schematu, rewizji lub restart unieważnia podpisany kursor.

Limit MCP to 16 KiB odpowiedzi, 92 dni strony dziennej i 60 s odczytu. Średnia okresowa obejmuje cały żądany zakres; nie publikować częściowej średniej. Braki są jawne, `wear_pct` nie jest zgadywany. Budżet ustawia PostgreSQL `statement_timeout` i anuluje aktywne zapytanie przez psycopg. Źródłowe nocne podsumowania, aktywności, okna godzinowe, dodatkowe statystyki, HTTP i hub Raspberry Pi są późniejszym zakresem.

Nie opakowywać ponownie buforów stdin/stdout w dodatkowe `TextIOWrapper`. Serwer ustawia UTF-8 na istniejących strumieniach; stdout służy tylko protokołowi. `scripts/smoke_mcp.py` kontroluje również pusty stderr i odcięcie dostępu bez restartu. Sandbox Windows może blokować wewnętrzny `socketpair` asyncio; testy wymagają uprawnień do jego utworzenia, bez dodawania serwera HTTP.

## Logowanie i pakowanie Windows

`LoginDialog` ma własny worker, animację i okno MFA, niezależne od importu i eksportu. MFA nie należy do ogólnego workera operacji. Każda próba tworzy nowego klienta Garmin. `Worker.ask_mfa` zeruje kod i Event przy każdym żądaniu. Kod MFA jest jawny, hasło maskowane. Po zakończeniu wątku zwalniaj funkcję przechwytującą dane logowania; klient usuwa hasło i callback. Anulowanie sprawdza się przed zapisem sesji i czeka na bieżące żądanie; nie niszczyć aktywnego wątku.

Ręczne logowanie pomija zapisane tokeny i nie pozwala SDK zapisać jawnej sesji przez `GARMINTOKENS`. Nie resetować sesji automatycznie. `LoginFailed` udostępnia wyłącznie etap, dozwoloną kategorię i ewentualny strukturalny status HTTP; nigdy treść wyjątku Garmin. Etap `mfa_verify` obejmuje także wymianę tokenów i profil API, więc nie oznacza sam w sobie błędnego kodu. Brak lokalnego pliku w łańcuchu to `LOCAL_RUNTIME`, błąd zapisu sesji to `LOCAL_SESSION`. UI nie interpretuje ponownie nazw wyjątków.

Build warunkowo pakuje sąsiedni `codex-rejected-cas.pem`, jeżeli dostarcza go używany runtime Pythona. Jest wymagany przy tworzeniu kontekstu TLS w tym runtime i trafia do GUI oraz MCP. Nie usuwać polityki certyfikatów ani nie wyłączać weryfikacji TLS. Smoke GUI musi tworzyć prawdziwy kontekst TLS, a nie tylko okno i połączenie PostgreSQL. Źródło ikony to `garmin_database/resources/app-icon.svg`; `scripts/generate_app_icon.py` odtwarza PNG i ICO, używane przez Qt i oba EXE.

## Zasoby lokalnego środowiska

Lokalny PostgreSQL 16.15 nasłuchuje wyłącznie na `127.0.0.1:5432`. Programy są w ignorowanym `private/postgresql-runtime/pgsql`, trwały klaster w `private/postgresql-runtime/data`, a hasła w chronionym ACL `private/postgresql-runtime/pgpass.conf`. **Nie usuwać `private/postgresql-runtime` przy sprzątaniu plików roboczych.** Baza aplikacji `garmin` i testowa `garmin_tests` mają oddzielne role bez uprawnień administracyjnych. DSN testów jest w `private/postgresql-runtime/test-dsn.txt`; nie wypisywać jego treści.

`private/Uruchom-GarminDatabase.cmd` i `private/start-garmin.ps1` uruchamiają PostgreSQL w razie potrzeby oraz wybraną lokalną paczkę. Instrukcja obsługi jest w `private/README-local.md`; te zasoby pozostają poza Git. Nie zainstalowano usługi ani automatycznego startu przy logowaniu. Lokalny start `pg_ctl` używa `Start-Process -WindowStyle Hidden -PassThru` i `WaitForExit()`; nie używać `Start-Process -Wait`, które czeka też na proces serwera.

Zakończone jednorazowe resety danych nie są procedurą utrzymania. Nie usuwać oryginalnych ZIP, sesji, ustawień, eksportów ani bazy PostgreSQL bez osobnego zlecenia użytkownika. Realnego logowania, importu historii ani odbioru Raspberry Pi nie zakładać na podstawie samych atrap i wyników innych platform.

## Git

Główna gałąź to `main`; nie tworzyć `master`. GitHub blokuje dokładnie `refs/heads/master` regułą Prevent accidental master branch. Używać Conventional Commits i jawnych list stagingu; push wymaga osobnego zlecenia.
