# Kolektor cykliczny

Kolektor aktualizuje PostgreSQL danymi z dotychczasowego eksportu dobrostanu Garmin Connect. Działa jako jednorazowy proces bez Qt: Windows Task Scheduler lub systemd uruchamia go niezależnie od GUI i zalogowania użytkownika. PostgreSQL może działać na tej samej maszynie albo na innym hoście.

## Kontrakt działania

| Obszar | Reguła |
| --- | --- |
| Źródło | Istniejące `garminconnect` i nieoficjalny endpoint dziennego eksportu wellness |
| Cykl | Pełne minuty, minimum 15; domyślnie 120 minut |
| Terminy | Kotwica UTC plus kolejne wielokrotności interwału; czas zakończenia nie przesuwa terminów |
| Prezentacja i zakres dnia | Europe/Warsaw; przy zmianie DST lokalna godzina terminu może się przesunąć |
| Restart / przestój | Najbliższy przyszły termin, bez automatycznego odtwarzania zaległych uruchomień |
| Zakres danych | Dokładnie „Pobierz nowe dane”, bez dodatkowego okna ostatnich N dni |
| Zajęty writer lub sesja | Informacja wyłącznie w logu automatu; następny zwykły termin |
| Błąd przejściowy | Dotychczasowe próby Sync, następnie kolejny zwykły termin |
| HTTP 429 | Trwała granica `not_before` z Retry-After; kolejne pobranie dopiero w dozwolonym zwykłym terminie |
| Brak / wygaśnięcie sesji | Trwały `auth_required`, bez prób sieciowych do nowego logowania kolektora |
| PostgreSQL niedostępny | Lokalny status i log; brak pobierania Garmin przed uzyskaniem blokady SQL |
| Konfiguracja | Lokalna zakładka Ustawienia Windows albo plik i CLI/SSH na maszynie kolektora |
| Dystrybucja | Windows: EXE onedir; Linux/Pi: Python 3.12+ i venv bez Qt/MCP |

Proces używa obecnego `Sync`: od ostatniego zarejestrowanego dnia włącznie do dzisiaj, z dotychczasową obsługą wcześniejszych błędów i nieukończonych importów. Przy pustej bazie obowiązuje początek 2024-01-01. Znane `not_found_unverified` pozostają nierozstrzygnięte i nie są ponawiane w tym trybie. Kolektor nie ustawia `refresh_all`. Kompletne FIT są deduplikowane po SHA-256, nowe ZIP pozostają w pamięci. Szczegóły: [synchronizacja](04-synchronization.md).

Nie ma stałego demona, kolejki poleceń, HTTP/API ani zdalnego sterowania kolektorem z GUI Windows. Eksport, MCP, powiadomienia zewnętrzne i nowe źródła danych pozostają osobnymi funkcjami. Ręczne GUI pobiera niezależnie, przez te same reguły i wspólne blokady. Odłożenie automatu nie wywołuje komunikatu ani wpisu w dzienniku ręcznych operacji.

## Architektura

| Element | Odpowiedzialność |
| --- | --- |
| `domain/schedule.py` | Stałe terminy UTC, następny przyszły termin i pomijanie spóźnionych uruchomień |
| `application/collector_models.py` | Wersjonowana konfiguracja, rewizja i stan kolektora |
| `application/use_cases/run_collector.py` | Jedno wykonanie, blokady, pauzy, wspólny Sync i trwały wynik |
| `application/ports.py` | Port runtime kolektora oraz istniejące porty importu |
| `adapters/inbound/collector/commands.py` | CLI i wejście harmonogramu |
| `adapters/outbound/collector_runtime.py` | Zegar, czas rozruchu, pliki stanu i bezpieczna klasyfikacja błędów |
| `adapters/outbound/scheduler/` | Rejestracja i odczyt Task Scheduler/systemd, pomocnik uprawnień Windows |
| `adapters/outbound/security/` | DPAPI Windows, szyfrowana sesja Linux, blokada magazynu |
| `adapters/outbound/filesystem/collector_files.py` | Konfiguracja, atomowy status, rotowane logi |
| `bootstrap/collector.py` | Składanie komend i zależności dopiero przy ich użyciu |
| `adapters/inbound/desktop/collector.py` | Lokalna konfiguracja i odczyty przez worker GUI |

Domain i application nadal używają tylko biblioteki standardowej. Status i obsługa harmonogramu nie ładują Qt, SDK Garmin, FIT ani MCP. Samo wejście poza terminem nie otwiera SQL, sesji ani logu. `Services.prepare()` sprawdza bieżący schemat przez odczyt; inicjalizacja i odzyskiwanie importu wymagają writera. GUI może otworzyć się i czytać zatwierdzone dane podczas pracy kolektora.

Blokady obejmują lokalną instancję kolektora, plik sesji i dotychczasowy writer SQL. PostgreSQL advisory lock chroni tę samą bazę/schemat również między hostami o różnych folderach danych. Logowanie i cały sieciowy Sync korzystający z tego samego magazynu sesji nie zachodzą na siebie. Blokady zwalnia system także po awarii procesu. Nie usuwać plików blokad w celu odblokowania aktywnej operacji.

## Harmonogram systemowy

Windows używa TimeTrigger z powtarzaniem, bez BootTrigger/LogonTrigger, z `IgnoreNew`, wyłączonym `StartWhenAvailable`, bez wybudzania maszyny i bez limitu 72 godzin na długi import. Proces działa pod dedykowanym kontem z logowaniem Password i najmniejszymi uprawnieniami. S4U nie zastępuje go ze względu na ograniczenia dostępu do sieci i zaszyfrowanych plików.

Linux używa `Type=oneshot`, `Persistent=false`, braku dodatkowych ponowień systemowych i minutowego wywołania kontrolnego. Taki wyzwalacz pozwala obsługiwać dowolny interwał, również 17 lub 90 minut, bez skracania go przy północy. Poza właściwym terminem proces od razu kończy pracę. Windows stosuje podobną kontrolę dla interwałów przekraczających natywny limit powtarzania zadania wynoszący 31 dni.

Kontrola odrzuca terminy sprzed rozruchu i opóźnienie wynoszące co najmniej minutę. Nie tworzy kolejki terminów przypadających podczas długiej operacji. Przed pracą termin i rewizja konfiguracji są atomowo oznaczane jako podjęte, aby nie wykonać tego samego cyklu ponownie. Zmiana konfiguracji bez zastosowania zadania powoduje bezpieczne `config_error`, bez pobierania.

Wyłączenie harmonogramu zatrzymuje przyszłe uruchomienia. Rozpoczęta operacja może się dokończyć. SIGINT/SIGTERM ustawiają sygnał anulowania wspólnego pipeline; bieżące HTTP może wymagać oczekiwania do timeoutu. Import zachowuje transakcję per FIT i ukończone wcześniejsze wyniki.

## Konfiguracja, stan i logi

Konfiguracja kolektora jest oddzielna od preferencji GUI. Schemat JSON ma wersję 1. `init` tworzy konfigurację wyłączoną, z interwałem 120 minut. Ustawienia obejmują:

- `data_dir`, `state_dir`, `session_path`: bezwzględne ścieżki; używać wydzielonych katalogów aplikacji.
- `database_dsn`: parametry PostgreSQL bez hasła. Kolejność wyboru: niepusty DSN, GARMIN_DATABASE_DSN, libpq. Hasło przez pgpass/PGPASSFILE albo środowisko konta zadania.
- `instance`, `enabled`, `interval_minutes`, `anchor_at`: identyfikator instancji, włączenie i terminy. Kotwica ma pełną minutę i jawny offset lub Z.
- `run_as`: dedykowane konto systemowe; Linux nie uruchamia kolektora jako root.
- `credential_path`: ścieżka zaszyfrowanego klucza systemd na Linux/Pi.
- `status_reader`: konto Windows uprawnione do konfiguracji i odczytu statusu, ustalane przy zastosowaniu zadania.

Windows domyślnie używa `%PROGRAMDATA%/GarminDatabase/collector/default/collector.json`. Linux: `/etc/garmin-database/collector.json`, z domyślnym stanem pod `/var/lib/garmin-database/collector/default/`. Ścieżki są niezależne od katalogu roboczego procesu. GUI może zapamiętać własną ścieżkę konfiguracji przez „Zapisz ustawienia”.

W `state_dir` znajdują się `status.json`, `collector.lock` i `logs/collector.log`. Plik statusu przechowuje m.in. ostatni wynik, terminy, ostatni sukces, bezpieczne liczniki, pauzę sesji, `not_before` i zastosowaną rewizję. Status/log można odczytać bez PostgreSQL. Log ma limit 5 MiB i pięć kopii rotacji. Nie zawiera pomiarów, tokenów, haseł, MFA, odpowiedzi dostawcy, pełnych wyjątków ani DSN.

Zapis konfiguracji i zastosowanie zadania to osobne operacje. Po zapisie wybierz „Zastosuj harmonogram” albo `schedule apply`. Rejestracja wymaga uprawnień systemowych. Błąd rejestracji nie jest prezentowany jako sukces; status porównuje zapisany plik z rzeczywistą definicją zadania. Zwykłe GUI działa bez podniesionych uprawnień, a rejestracja Windows ma osobny pomocnik UAC. Pomocnik przyznaje wyłącznie kontu zadania wymagane `SeBatchLogonRight` przez LSA, bez zastępowania listy pozostałych uprawnień i bez członkostwa w Administratorach. Wyłączenie zadania nie odbiera kontu tego prawa. Nadrzędna zasada odmowy logowania wsadowego musi zostać rozstrzygnięta przez administratora systemu.

## CLI

W źródłach używaj `python -m garmin_database.bootstrap.collector`, po instalacji pakietu `garmin-db-collector`, a w paczce Windows `GarminDatabaseCollector.exe`. Globalne `--config` podaje się przed poleceniem.

```text
garmin-db-collector --config /etc/garmin-database/collector.json init
garmin-db-collector --config /etc/garmin-database/collector.json prepare-key
garmin-db-collector --config /etc/garmin-database/collector.json login
garmin-db-collector --config /etc/garmin-database/collector.json status --json
garmin-db-collector --config /etc/garmin-database/collector.json logs
garmin-db-collector --config /etc/garmin-database/collector.json schedule install
garmin-db-collector --config /etc/garmin-database/collector.json schedule enable
garmin-db-collector --config /etc/garmin-database/collector.json schedule disable
garmin-db-collector --config /etc/garmin-database/collector.json schedule apply
garmin-db-collector --config /etc/garmin-database/collector.json schedule status
garmin-db-collector --config /etc/garmin-database/collector.json run --scheduled
```

`init` i `prepare-key` odmawiają nadpisania istniejącego pliku. `run --scheduled` respektuje włączenie, termin i zastosowaną rewizję. Samo `run` jest jawnym ręcznym uruchomieniem i nadal respektuje pauzę sesji oraz Retry-After. Kody wyjścia: 0 dla sukcesu i zwykłego pominięcia, 2 dla wyniku z problemami/pauzy, 1 dla błędu konfiguracji lub wykonania polecenia. System nie wykonuje dodatkowego restartu zadania po kodzie 1/2.

## Windows — przygotowanie konta i pierwsze uruchomienie

1. Przygotuj PostgreSQL 16+ z automatycznym startem lub dostęp do zdalnego serwera. Zobacz [konfigurację PostgreSQL](13-postgresql-setup.md). Serwer nie jest częścią EXE.
2. Zachowaj cały folder onedir `GarminDatabaseCollector` i sąsiedni folder GUI. Wybierz stabilną lokalizację dostępną do odczytu przez konto zadania.
3. Utwórz dedykowane lokalne konto z hasłem. Hello/PIN głównego użytkownika nie wystarcza do nieinteraktywnego zadania. Konto otrzymuje dostęp do wskazanego folderu danych, własnego pgpass i prywatnej sesji. Nie używaj SYSTEM.
4. W Ustawieniach aplikacji skonfiguruj konto, połączenie, folder i cykl. Zapisz konfigurację. Zastosuj harmonogram; Windows poprosi o potwierdzenie administracyjne i poświadczenia konta zadania. Hasło przechodzi wyłącznie przez pamięć/dialog systemowy, nie przez argumenty procesu ani plik konfiguracji.
5. Wykonaj `login` w konsoli uruchomionej pod kontem kolektora, np. przez systemowe `runas`. E-mail, hasło Garmin i MFA wpisuje się interaktywnie. Nie podawaj ich w argumentach.
6. Sprawdź `status --json`, log i kolejne zwykłe uruchomienie, także po wylogowaniu głównego użytkownika. W razie potrzeby włącz harmonogram po przygotowaniu sesji.

Przykład polecenia wewnątrz konsoli właściwego konta:

```powershell
C:\Apps\GarminDatabaseCollector\GarminDatabaseCollector.exe --config C:\ProgramData\GarminDatabase\collector\default\collector.json login
```

DPAPI wiąże sesję z kontem i komputerem. Logowanie w GUI głównego użytkownika nie odnawia sesji dedykowanego konta. Po przeniesieniu konta/maszyny potrzebne jest nowe logowanie. Nie kopiować ani automatycznie usuwać cudzej sesji, pgpass, ustawień, ZIP i eksportów.

## Linux i Raspberry Pi OS — instalacja bez GUI

Wymagane są Python 3.12+, system 64-bit i systemd obsługujący `LoadCredentialEncrypted` oraz `systemd-creds` (250+). Biblioteki muszą mieć binarne zależności dla platformy. Raspberry Pi OS Bookworm domyślnie dostarcza starszego Pythona; przygotuj interpreter 3.12+ osobno. PostgreSQL 16+ może działać na innym hoście.

Przykładowy układ po utworzeniu dedykowanego konta `garmin-collector` z własnym katalogiem domowym:

```sh
sudo python3.12 -m venv /opt/garmin-database/.venv
sudo /opt/garmin-database/.venv/bin/python -m pip install '.[collector]'
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/collector.json init
```

Instalację pakietu wykonuj z katalogu źródeł; na dedykowanej maszynie dopuszczalna jest również instalacja zbudowanego wheel z dodatkiem `[collector]`. Interpreter i pakiet muszą być czytelne/wykonywalne dla użytkownika usługi. Qt i SDK MCP nie należą do zależności kolektora.

Edytuj konfigurację: ustaw `run_as`, DSN bez hasła, katalogi, interwał i kotwicę. Przygotuj `.pgpass` konta kolektora z trybem 0600. Następnie jako administrator:

```sh
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/collector.json prepare-key
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/collector.json schedule install
```

Instalacja tworzy jednostki `garmin-database-default.service` i `.timer` pod `/etc/systemd/system`, przydziela katalogi kontu usługi i nie pobiera historii. Domyślnie harmonogram pozostaje wyłączony. Klucz AES jest generowany w pamięci i przekazywany przez pipe do systemd-creds. Nie nadpisuj istniejącego poświadczenia.

Pierwsze logowanie uruchom z tym samym kontem i poświadczeniem co jednostka systemowa:

```sh
sudo systemd-run --wait --collect --pty \
  --property=User=garmin-collector \
  --property=LoadCredentialEncrypted=garmin-session-key:/etc/garmin-database/session-key.cred \
  /opt/garmin-database/.venv/bin/garmin-db-collector \
  --config /etc/garmin-database/collector.json login
```

Po logowaniu włącz harmonogram:

```sh
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/collector.json schedule enable
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/collector.json status --json
```

Sesja jest zapisywana jako osobny, uwierzytelniony szyfrogram AES-GCM z losowym nonce. systemd przekazuje klucz przez chroniony katalog poświadczeń, a nie jako wartość zmiennej środowiskowej. Tokeny są odświeżane w szyfrowanym pliku z trybem 0600, nie w tylko do odczytu katalogu poświadczeń. Nie ma jawnego fallbacku ani potrzeby odblokowania graficznego keyringu. Ochrona ta nie zastępuje szyfrowania nośnika i kopii zapasowych.

## Budowanie i odbiór

Pełny build: `python scripts/build.py`, Windows: `scripts/build_windows.ps1`. Powstają trzy osobne foldery: GUI, MCP i Collector. `python scripts/build.py --only collector` buduje sam kolektor w środowisku bez Qt/MCP. Smoke kolektora: `python scripts/smoke_collector.py dist/GarminDatabaseCollector/GarminDatabaseCollector` (na Windows z rozszerzeniem `.exe`).

Testy i smoke GUI/MCP wymagają osobnej bazy wskazanej przez GARMIN_TEST_DATABASE_DSN. Kolektor ma testy terminów, pauz, blokad, szyfrowania, konfiguracji, adapterów systemowych i GUI. Test integracyjny używa rzeczywistego PostgreSQL i syntetycznego FIT, sprawdza wspólne przyrostowe pobieranie, deduplikację i ciche pominięcie przy zajętym writerze. CI uruchamia build Windows z testami i smoke oraz niezależny build kolektora ARM64 bez Qt/MCP.

`scripts/smoke_scheduler.py` jest testem odbioru natywnego harmonogramu na jednorazowym runnerze CI, z uprawnieniami administratora/root i osobną bazą testową. Tworzy własne tymczasowe konto, zadanie/jednostki i schemat SQL. Sprawdza szyfrowany zapis/odczyt syntetycznej sesji pod kontem zadania oraz uruchomienie zbudowanego kolektora przez rzeczywisty harmonogram. Bez sesji Garmin kolektor kończy się przewidywalnym `auth_required`, bez żądania sieciowego. Test usuwa wyłącznie utworzone przez siebie zasoby. Nie uruchamiać go na instalacji użytkownika.

Odbiór instalacji docelowej obejmuje rzeczywiste logowanie Garmin, działanie pod wybranym kontem bez zalogowanego użytkownika, restart, dostęp do lokalnego/zdalnego PostgreSQL, uprawnienia i stan po wygaśnięciu sesji. Testy syntetyczne i Ubuntu ARM64 nie zastępują takiego odbioru na fizycznym Raspberry Pi OS. Paczka binarna ARM64 z CI jest związana z systemem użytym do buildu; standardową dystrybucją Linux/Pi jest pakiet Python w venv.

## Źródła systemowe

- [Windows: typy logowania zadania](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type).
- [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).
- [systemd.exec: poświadczenia procesu](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).
