# GarminDatabase — pamięć implementacji

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

Odbiór zmiany 2026-10-23 w cloud Linux/Python 3.12.14/PostgreSQL 16.2: 217 testów zaliczonych, 2 jawnie pominięte Windows DPAPI, coverage z gałęziami 92,83%, storage 100%; Ruff, build PyInstaller Linux, wheel/sdist i smoke paczki poprawne. Jednostkowe bez serwera: 121 zaliczonych i 1 skip DPAPI. **Nie uznawać pełnego odbioru Windows za wykonany:** wymagane testy DPAPI, build oraz smoke EXE na Windows. Nie ma potwierdzenia testów na Raspberry Pi ani importu rzeczywistej historii do PostgreSQL.
