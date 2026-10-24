# PostgreSQL: konfiguracja i ochrona danych

Od 2026-10-23 jedynym silnikiem aplikacji jest darmowy PostgreSQL Community 16 lub nowszy. Instalacja lokalna i docelowy serwer używają identycznego schematu i sterownika psycopg 3. Nie ma automatycznego powrotu do SQLite ani migracji jego danych.

## Instalacja serwera

Windows: zainstaluj PostgreSQL Community z [oficjalnej strony](https://www.postgresql.org/download/windows/), razem z narzędziami wiersza poleceń. Uruchom usługę PostgreSQL. Narzędzia poniżej znajdują się w `C:/Program Files/PostgreSQL/<wersja>/bin`; dodaj ten katalog do PATH. pgAdmin jest opcjonalny. Serwer pozostaje osobną usługą, nie jest dołączany do EXE aplikacji.

Debian/Ubuntu/Raspberry Pi OS 64-bit:

```sh
sudo apt update
sudo apt install postgresql postgresql-client
sudo systemctl enable --now postgresql
psql --version
```

Pakiet dystrybucji musi mieć wersję co najmniej 16; jeśli udostępnia starszą, skorzystaj z właściwego [repozytorium PostgreSQL](https://www.postgresql.org/download/linux/). Inne dystrybucje: równoważne pakiety i usługa z ich menedżera pakietów. Raspberry Pi powinno korzystać z systemu 64-bitowego i trwałego nośnika o odpowiedniej wydajności.

## Konto i baza aplikacji

Wykonaj jako administrator PostgreSQL. Hasła wprowadź interaktywnie, nie umieszczaj ich w poleceniach ani repozytorium.

Windows PowerShell:

```powershell
createuser -U postgres --pwprompt --no-superuser --no-createdb --no-createrole garmin
createdb -U postgres --owner=garmin --encoding=UTF8 garmin
```

Linux/Raspberry Pi OS:

```sh
sudo -u postgres createuser --pwprompt --no-superuser --no-createdb --no-createrole garmin
sudo -u postgres createdb --owner=garmin --encoding=UTF8 garmin
```

Konto `garmin` nie potrzebuje uprawnień superuser ani tworzenia baz/ról. Jako właściciel bazy tworzy i aktualizuje własny schemat. W psql jako administrator ogranicz dostęp innych ról:

```sql
REVOKE ALL ON DATABASE garmin FROM PUBLIC;
\connect garmin
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

Nie otwieraj portu 5432 publicznie. Przy pracy na jednym urządzeniu pozostaw nasłuch na localhost, a w `pg_hba.conf` stosuj SCRAM-SHA-256. Przy oddzielnym serwerze dopuść tylko wymagane adresy aplikacji i połączenia `hostssl`; skonfiguruj certyfikat serwera i zaporę.

## Połączenie aplikacji

Wybór połączenia, od najwyższego priorytetu:

1. Niepusty `database_dsn` w ustawieniach (UI: „Połączenie PostgreSQL”).
2. `GARMIN_DATABASE_DSN` w środowisku procesu.
3. Parametry libpq, m.in. `PGHOST`, `PGPORT`, `PGUSER`, `PGSERVICE`; domyślna nazwa bazy to `garmin`.

Przed pierwszym uruchomieniem ustaw połączenie w środowisku lub w pliku ustawień. Dzięki temu UI uruchomi się z działającą bazą. Przykład lokalny PowerShell:

```powershell
$env:GARMIN_DATABASE_DSN = 'host=localhost port=5432 dbname=garmin user=garmin'
.\.venv\Scripts\python.exe -m garmin_database.cli status --data-dir data
.\.venv\Scripts\python.exe -m garmin_database
```

Linux/Raspberry Pi OS:

```sh
export GARMIN_DATABASE_DSN='host=localhost port=5432 dbname=garmin user=garmin'
.venv/bin/python -m garmin_database.cli status --data-dir data
```

Zapisane ustawienia mogą zawierać np. `"database_dsn": "host=localhost port=5432 dbname=garmin user=garmin"`. Dane logowania Garmin i PostgreSQL są niezależne.

Hasło PostgreSQL umieść w pliku libpq: `%APPDATA%/postgresql/pgpass.conf` na Windows lub `~/.pgpass` z uprawnieniami `0600` na Linux. Format pojedynczego wpisu: `host:port:baza:użytkownik:hasło`. Ogranicz uprawnienia pliku Windows do konta uruchamiającego aplikację. Możesz wskazać inną ścieżkę przez `PGPASSFILE`. `PGPASSWORD` jest alternatywą procesową dla automatyzacji; nie zapisuj jej w repozytorium ani logach. Ustawienia aplikacji odrzucają DSN zawierający `password`, również w URI.

Na zdalnym serwerze użyj np. `host=db.example.internal port=5432 dbname=garmin user=garmin sslmode=verify-full sslrootcert=/ścieżka/ca.crt`. Certyfikat musi pasować do nazwy hosta. Samo `sslmode=prefer` może dopuścić połączenie nieszyfrowane i nie jest ustawieniem docelowym dla przesyłania danych medycznych.

`status` tworzy pusty schemat i weryfikuje jego wersje/sumy kontrolne. Brak serwera lub bazy kończy operację bez utworzenia pliku SQLite. UI/CLI prezentują typ błędu bez treści wyjątku sterownika i danych połączenia.

## Usunięcie starego SQLite przed testami lokalnymi

Zatrzymaj starą aplikację i procesy importu. W rzeczywistym katalogu `data_dir` usuń wyłącznie `garmin.sqlite3` i istniejące pliki pomocnicze `garmin.sqlite3-wal`, `garmin.sqlite3-shm`, `garmin.sqlite3-journal`. To świadoma rezygnacja z poprzedniej bazy: użytkownik zdecydował ponownie pobrać historię, bez migracji danych. Nie usuwaj ZIP z `raw/`, sesji, ustawień, eksportów ani nowej bazy PostgreSQL.

Po skonfigurowaniu połączenia uruchom aplikację i „Pobierz dane”. Istniejące poprawne archiwa można również ponownie zaimportować. `data_dir` wskazuje teraz archiwa i metadane lokalne, a nie plik SQL. Przeniesienie samego folderu `data/` nie przenosi PostgreSQL; do przenoszenia nowej bazy służą narzędzia PostgreSQL.

## Ochrona danych na dysku

PostgreSQL nie szyfruje automatycznie swoich plików. Serwer, jego WAL i kopie zapasowe muszą znajdować się na zabezpieczonym nośniku: np. LUKS na Linux/Raspberry Pi OS i VeraCrypt na Windows. Ten sam wymóg dotyczy oryginalnych ZIP i eksportów JSON, które nadal są plikami z danymi medycznymi. Klucze szyfrowania i hasła przechowuj oddzielnie od danych. Nie dodano automatycznych kopii zapasowych ani własnego szyfrowania pól.

## Oddzielna baza testowa

Utwórz osobną rolę `garmin_test` bez superuser/createdb/createrole oraz bazę `garmin_tests`, analogicznie do konta aplikacji. Zapisz jej hasło w oddzielnym wpisie pgpass. Nie wskazuj produkcyjnej bazy ani rzeczywistych danych pacjenta.

PowerShell:

```powershell
$env:GARMIN_TEST_DATABASE_DSN = 'host=localhost port=5432 dbname=garmin_tests user=garmin_test'
powershell -NoProfile -File scripts/run_tests.ps1
```

Linux:

```sh
export GARMIN_TEST_DATABASE_DSN='host=localhost port=5432 dbname=garmin_tests user=garmin_test'
.venv/bin/python scripts/run_tests.py
```

Każdy test integracyjny/UI tworzy unikatowy schemat, a po teście go usuwa. To samo robi smoke paczki. Rola testowa potrzebuje CREATE w swojej bazie, bez superuser. Brak konfiguracji kończy pełny zestaw błędem zamiast pomijania testów bazy lub zastępowania jej SQLite. Testy jednostkowe można uruchomić bez serwera przez `pytest -m 'unit and not integration and not ui'`.

## Przygotowana instalacja lokalna Windows — 2026-10-23

W checkoutcie `D:/Projects/GarminDatabase` przygotowano PostgreSQL 16.15 z [oficjalnej paczki binarnej EDB](https://www.enterprisedb.com/download-postgresql-binaries). Serwer jest niezależnym procesem i nasłuchuje wyłącznie na `127.0.0.1:5432`. Programy są w `private/postgresql-runtime/pgsql`, a trwałe dane serwera w `private/postgresql-runtime/data`. Baza aplikacji `garmin` i baza testów `garmin_tests` mają osobne role bez uprawnień administracyjnych. Losowe hasła są w pliku `private/postgresql-runtime/pgpass.conf`; katalog ma ACL ograniczony do użytkownika, SYSTEM i administratorów. Ustawienia wskazują `passfile`, bez hasła.

Uruchom lokalny `private/Uruchom-GarminDatabase.cmd`. Plik włącza PostgreSQL, jeśli jest zatrzymany, a potem aktualną paczkę GUI z `dist/auth-update`. Nie utworzono usługi systemowej ani automatycznego startu przy logowaniu, dlatego po restarcie komputera należy użyć tego pliku. Lokalne szczegóły obsługi są w `private/README-local.md`; te pliki i serwer pozostają poza Git. Nie usuwać `private/postgresql-runtime` w ramach sprzątania katalogów roboczych, ponieważ zawiera nową bazę i jej dane dostępowe. Nie skonfigurowano szyfrowania nośnika ani automatycznych kopii zapasowych.

Na wyraźne zlecenie i po dodatkowym potwierdzeniu użytkownika jednorazowo usunięto stary SQLite, jego pliki WAL/SHM, 845 archiwów w rzeczywistym `data/raw` oraz `collection.json` i `fit_inventory.json`. Sesję Garmin, ustawienia i eksporty zachowano. To wyjątek dotyczący tego resetu, nie ogólna instrukcja usuwania oryginalnych ZIP. Nowa baza jest pusta; pobieranie historii nie zostało rozpoczęte. Ustawienia zachowują początek 2024-01-01, a pusty `history_to` oznacza automatycznie wczoraj w Warszawie. Stan technicznego odbioru opisuje [instrukcja testów](12-running-and-testing.md#lokalny-odbiór-windows--2026-10-23).
