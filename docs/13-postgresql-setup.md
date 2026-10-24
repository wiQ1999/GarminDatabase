# PostgreSQL: konfiguracja i ochrona danych

Jedynym silnikiem aplikacji jest darmowy PostgreSQL Community 16 lub nowszy. Instalacja lokalna i docelowy serwer używają identycznego schematu i sterownika psycopg 3. Nie ma automatycznego powrotu do SQLite ani migracji jego danych.

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

Na Windows narzędzie uruchomione w kontekście pakietu MSIX może przekierować nowy plik AppData do prywatnego `LocalCache`, mimo użycia standardowej ścieżki. Przy konfiguracji pliku dla innej aplikacji potwierdź jego fizyczną lokalizację przez `GetFinalPathNameByHandle` i sprawdź odczyt ze zwykłego procesu użytkownika. Samo `Test-Path`, porównanie sum lub udane połączenie z tego samego kontekstu MSIX nie wystarcza. Plik `pgpass` musi być widoczny dla normalnie uruchamianego EXE. Zasady: [przekierowanie AppData w MSIX](https://learn.microsoft.com/en-us/windows/uwp/porting/desktop-to-uwp-behind-the-scenes).

Na zdalnym serwerze użyj np. `host=db.example.internal port=5432 dbname=garmin user=garmin sslmode=verify-full sslrootcert=/ścieżka/ca.crt`. Certyfikat musi pasować do nazwy hosta. Samo `sslmode=prefer` może dopuścić połączenie nieszyfrowane i nie jest ustawieniem docelowym dla przesyłania danych medycznych.

`status` tworzy pusty schemat i weryfikuje jego wersje/sumy kontrolne. Brak serwera lub bazy kończy operację bez utworzenia pliku SQLite. UI/CLI prezentują typ błędu bez treści wyjątku sterownika i danych połączenia.

## Dane ze starszych wersji

Aplikacja nie migruje danych SQLite. Pustą bazę PostgreSQL zasila ponowne pobranie lub import zachowanych ZIP. `data_dir` wskazuje archiwa i metadane lokalne, nie plik SQL. Przeniesienie folderu `data/` nie przenosi bazy; do przenoszenia PostgreSQL służą jego narzędzia administracyjne. Usuwanie danych użytkownika nie jest częścią konfiguracji nowej bazy ani testów.

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

## Lokalna instalacja projektu na Windows

Lokalna instalacja PostgreSQL 16.15 korzysta z [oficjalnej paczki binarnej EDB](https://www.enterprisedb.com/download-postgresql-binaries) i znajduje się poza checkoutem. Wszystkie lokalne silniki SQL, instancje, dane i paczki instalacyjne są przechowywane pod `E:/Databases`; nie odtwarzać ich na `D:`. Serwer jest niezależnym procesem i nasłuchuje wyłącznie na `127.0.0.1:5432`. Programy są w `E:/Databases/PostgreSQL/16/pgsql`, a trwałe dane serwera w `E:/Databases/PostgreSQL/16/data`. Baza aplikacji `garmin` i baza testów `garmin_tests` mają osobne role bez uprawnień administracyjnych.

Hasła kont `garmin_admin`, `garmin` i `garmin_test` są w standardowym pliku klienta `%APPDATA%/postgresql/pgpass.conf`, poza katalogiem instancji. Plik ma ACL ograniczony do użytkownika, SYSTEM i administratorów. Ustawienia aplikacji i lokalny DSN testów jawnie wskazują tę samą standardową ścieżkę przez `passfile`, bez hasła. Nie przechowywać drugiej kopii haseł przy silniku. DSN testów znajduje się w `E:/Databases/PostgreSQL/16/test-dsn.txt` i nie należy wypisywać jego treści.

Uruchom lokalny `private/Uruchom-GarminDatabase.cmd`. Plik włącza PostgreSQL na E:, jeśli jest zatrzymany, a potem paczkę GUI wskazaną w `private/start-garmin.ps1`. Nie utworzono usługi systemowej ani automatycznego startu przy logowaniu, dlatego po restarcie komputera należy użyć tego pliku. Lokalne szczegóły obsługi są w `private/README-local.md`; pliki lokalne i serwer pozostają poza Git. Nie usuwać `E:/Databases` w ramach sprzątania katalogów roboczych. Zmiana lokalizacji SQL nie zmienia folderu surowych archiwów Garmin wybieranego przez `data_dir`. Nie skonfigurowano szyfrowania nośnika ani automatycznych kopii zapasowych.

Launcher wskazuje katalog klastra przez `pg_ctl -D E:/Databases/PostgreSQL/16/data`. Nowe bazy w domyślnej przestrzeni `pg_default` zapisują pliki pod `data/base`, w technicznych podfolderach zarządzanych przez PostgreSQL; nie podaje się osobnej ścieżki przy każdym `CREATE DATABASE`. Inne lokalizacje wymagają świadomego użycia [przestrzeni tabel](https://www.postgresql.org/docs/16/manage-ag-tablespaces.html).
