# Kolektor cykliczny

Kolektor aktualizuje PostgreSQL danymi z dotychczasowego eksportu dobrostanu Garmin Connect. Działa jako jednorazowy proces bez Qt, uruchamiany przez Windows Task Scheduler lub systemd niezależnie od GUI. W domyślnym trybie Windows użytkownik pozostaje zalogowany; blokada ekranu jest dozwolona. PostgreSQL może działać na tej samej maszynie albo na innym hoście.

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

Proces używa obecnego `Sync`: od ostatniego zarejestrowanego dnia włącznie do dzisiaj, w granicach zapisanego początku pobierania, z dotychczasową obsługą wcześniejszych błędów i nieukończonych importów. Przy pustej bazie obowiązuje `download_from`, domyślnie 2024-01-01. Jest to ustawienie wspólne z ręcznym pobieraniem, niezależne od zakresu eksportu i początku harmonogramu. Znane `not_found_unverified` pozostają nierozstrzygnięte i nie są ponawiane w tym trybie. Kolektor nie ustawia `refresh_all`. Kompletne FIT są deduplikowane po SHA-256, nowe ZIP pozostają w pamięci. Szczegóły: [synchronizacja](04-synchronization.md).

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

Windows używa TimeTrigger z powtarzaniem, bez BootTrigger/LogonTrigger, z `IgnoreNew`, wyłączonym `StartWhenAvailable`, bez wybudzania maszyny i bez limitu 72 godzin na długi import. Proces ma najmniejsze uprawnienia. Dostępne są dwa tryby:

- `windows_logon: "interactive"` — domyślny dla nowych konfiguracji Windows. Bieżące konto, bez hasła Windows i bez prawa logowania wsadowego. Działa po zalogowaniu, również przy blokadzie ekranu; zakończenie sesji użytkownika uniemożliwia kolejne uruchomienia. Korzysta z szyfrowanej sesji Garmin aplikacji i wspólnej blokady pliku, bez kopiowania tokenów. Samo GUI może być zamknięte.
- `windows_logon: "password"` — praca także po wylogowaniu. Konto może być bieżące albo osobne; rejestracja wymaga jego rzeczywistego hasła Windows. PIN/Hello nie wystarcza. Sesja Garmin jest prywatna dla tego profilu kolektora. S4U nie zastępuje tego trybu z powodu ograniczeń dostępu do sieci i zaszyfrowanych plików.

Harmonogram uruchamia `GarminDatabaseCollectorTask.exe`, plik bez konsoli w folderze kolektora. `GarminDatabaseCollector.exe` pozostaje konsolowym CLI do logowania i ręcznych poleceń. Źródła Windows używają `pythonw.exe` dla zadania. Zwykła instalacja bieżącego konta nie podnosi uprawnień. Nadpisanie starszego zadania należącego do administratorów może jednorazowo wymagać UAC; nie wymaga hasła konta zadania w trybie `interactive`.

Semantyka trybów: [Microsoft TASK_LOGON_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type).

Linux używa `Type=oneshot`, `Persistent=false`, braku dodatkowych ponowień systemowych i minutowego wywołania kontrolnego. Taki wyzwalacz pozwala obsługiwać dowolny interwał, również 17 lub 90 minut, bez skracania go przy północy. Poza właściwym terminem proces od razu kończy pracę. Windows stosuje podobną kontrolę dla interwałów przekraczających natywny limit powtarzania zadania wynoszący 31 dni.

Kontrola odrzuca terminy sprzed rozruchu i opóźnienie wynoszące co najmniej minutę. Nie tworzy kolejki terminów przypadających podczas długiej operacji. Przed pracą termin i rewizja konfiguracji są atomowo oznaczane jako podjęte, aby nie wykonać tego samego cyklu ponownie. Zmiana konfiguracji bez zastosowania zadania powoduje bezpieczne `config_error`, bez pobierania.

Wyłączenie harmonogramu zatrzymuje przyszłe uruchomienia. Rozpoczęta operacja może się dokończyć. SIGINT/SIGTERM ustawiają sygnał anulowania wspólnego pipeline; bieżące HTTP może wymagać oczekiwania do timeoutu. Import zachowuje transakcję per FIT i ukończone wcześniejsze wyniki.

## Konfiguracja, stan i logi

Aplikacja, MCP i kolektor używają jednego `settings.json`. Parametry połączenia `database_dsn`, początku pobierania `download_from` oraz `data_dir` są wspólne, bez kopii w sekcji `collector`. Dla osobnego serwera kolektora przygotuj lokalny `settings.json` z jego połączeniem i ścieżkami. Hasło PostgreSQL pozostaje w pgpass, poza JSON.

Sekcja `collector` zawiera: `enabled`, `interval_minutes` (minimum 15), `anchor_at` (pełna minuta UTC), `run_as`, `windows_logon`, `instance`, `state_dir`, `session_path`, `credential_path` (Linux) i `status_reader` (Windows). Wersja konfiguracji 2 dodaje wybór trybu; pliki wersji 1 pozostają czytelne i zachowują `password` oraz dotychczasowe ścieżki. Zmiana konta lub trybu przez UI/CLI wybiera osobny katalog stanu, zachowując stare pliki. Stan i sesja nie należą do pliku ustawień. Zapisy ustawień globalnych zachowują nowszą sekcję kolektora; zapisy kolektora zachowują ustawienia globalne. Zapis jest atomowy z blokadą pliku i zachowaniem ACL.

Odczyt Harmonogramu Zadań nie otwiera konsoli PowerShell. Odmowa dostępu do zadania jest odrębnym stanem od braku zadania; lokalny wynik i dziennik kolektora nadal są dostępne. Instalacja/aktualizacja nadaje operatorowi prawo odczytu definicji zadania, także gdy utworzono je z podwyższonymi uprawnieniami. Nazwa `GarminDatabase-default` oznacza domyślną instancję, a nie konto Windows.

Aktualizacja istniejącego zadania wymaga osobnego sprawdzenia jego deskryptora: `RegisterTask` zachowuje dotychczasowe uprawnienia. Instalator porównuje skuteczne wpisy użytkownika i operatora, w razie potrzeby wywołuje `SetSecurityDescriptor`, odczytuje wynik ponownie i potwierdza dostęp do definicji. Po zakończeniu pomocnika UAC zwykły proces aplikacji musi potwierdzić obecność oraz zgodność zadania; sam kod wyjścia pomocnika nie oznacza udanej instalacji. Dokumentacja interfejsu: [IRegisteredTask.SetSecurityDescriptor](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/nf-taskschd-iregisteredtask-setsecuritydescriptor).

Windows: `%LOCALAPPDATA%/GarminDatabase/settings.json`; Linux: `/etc/garmin-database/settings.json`. GUI otwiera folder przyciskiem „Otwórz folder konfiguracji”. Pole `refresh_seconds` (5–3600, domyślnie 15) steruje częstotliwością odświeżania statusów, nie pobierania z Garmin. Początek harmonogramu wyznacza terminy, a `download_from` zakres danych.

Starsze samodzielne pliki kolektora są nadal czytelne przez CLI. Pierwszy zapis formularza może przenieść ustawienia sąsiedniego `collector.json` do wspólnej konfiguracji, bez usuwania oryginału. Następnie należy zastosować harmonogram, aby zadanie wskazywało nowy plik. Stare niestandardowe ścieżki nie są automatycznie usuwane.

W `state_dir` znajdują się `status.json`, `collector.lock` i `logs/collector.log`. Plik statusu przechowuje m.in. ostatni wynik, terminy, ostatni sukces, bezpieczne liczniki, pauzę sesji, `not_before` i zastosowaną rewizję. Status/log można odczytać bez PostgreSQL. Log ma limit 5 MiB i pięć kopii rotacji. Nie zawiera pomiarów, tokenów, haseł, MFA, odpowiedzi dostawcy, pełnych wyjątków ani DSN.

„Zapisz konfigurację” zapisuje bez rejestracji. „Zainstaluj / zaktualizuj kolektor” zapisuje formularz i stosuje zadanie w jednej operacji. CLI `install` przygotowuje brakującą konfigurację i klucz Linux oraz stosuje harmonogram. Po zapisie wybierz przycisk instalacji albo `schedule apply`. Błąd rejestracji nie jest prezentowany jako sukces; status porównuje plik z rzeczywistą definicją zadania. GUI działa bez podniesionych uprawnień. Bieżące konto `interactive` nie zmienia praw systemowych; UAC pojawia się tylko przy naprawie braku dostępu do istniejącego zadania. Dla `password` pomocnik UAC przyznaje wyłącznie kontu zadania wymagane `SeBatchLogonRight` przez LSA, bez zastępowania listy pozostałych uprawnień i bez dodawania konta do Administratorów. Wyłączenie zadania nie odbiera tego prawa. Nadrzędna zasada odmowy logowania wsadowego wymaga rozstrzygnięcia przez administratora.

## CLI

W źródłach używaj `python -m garmin_database.bootstrap.collector`, po instalacji pakietu `garmin-db-collector`, a w paczce Windows `GarminDatabaseCollector.exe`. Globalne `--config` podaje się przed poleceniem.

```text
garmin-db-collector --config /etc/garmin-database/settings.json init
garmin-db-collector --config /etc/garmin-database/settings.json prepare-key
garmin-db-collector --config /etc/garmin-database/settings.json login
garmin-db-collector --config /etc/garmin-database/settings.json status --json
garmin-db-collector --config /etc/garmin-database/settings.json logs
garmin-db-collector --config /etc/garmin-database/settings.json schedule install
garmin-db-collector --config /etc/garmin-database/settings.json schedule enable
garmin-db-collector --config /etc/garmin-database/settings.json schedule disable
garmin-db-collector --config /etc/garmin-database/settings.json schedule apply
garmin-db-collector --config /etc/garmin-database/settings.json schedule status
garmin-db-collector --config /etc/garmin-database/settings.json run --scheduled
```

`init` i `prepare-key` odmawiają nadpisania istniejącego pliku. `run --scheduled` respektuje włączenie, termin i zastosowaną rewizję. Samo `run` jest jawnym ręcznym uruchomieniem i nadal respektuje pauzę sesji oraz Retry-After. Kody wyjścia: 0 dla sukcesu i zwykłego pominięcia, 2 dla wyniku z problemami/pauzy, 1 dla błędu konfiguracji lub wykonania polecenia. System nie wykonuje dodatkowego restartu zadania po kodzie 1/2.

## Windows — przygotowanie konta i pierwsze uruchomienie

1. Przygotuj PostgreSQL 16+ z automatycznym startem lub dostęp do zdalnego serwera. Zobacz [konfigurację PostgreSQL](13-postgresql-setup.md). Serwer nie jest częścią EXE.
2. Zachowaj cały folder onedir `GarminDatabaseCollector` i sąsiedni folder GUI. Wybierz stabilną lokalizację dostępną do odczytu przez konto zadania.
3. Domyślnie użyj „Bieżące konto — bez hasła Windows”. Dla pracy po wylogowaniu wybierz drugi tryb i konto z hasłem; może być osobne. Nie używaj SYSTEM. Osobne konto dostaje odczyt tylko pliku konfiguracji, bez dostępu do folderu sesji GUI. Atomowy zapis zachowuje ACL Windows.
4. Ustaw połączenie, katalog danych i początek pobierania w ogólnych ustawieniach aplikacji, a tryb i cykl w sekcji automatu. Włącz pobieranie i kliknij „Zainstaluj / zaktualizuj kolektor”. W trybie bieżącego konta nie ma monitu hasła Windows. W trybie po wylogowaniu hasło przechodzi wyłącznie przez pamięć/dialog systemowy, nie przez argumenty ani plik.
5. Bieżące konto korzysta z sesji Garmin aplikacji. W trybie `password` przygotuj prywatną sesję: dla aktualnego konta przez formularz Garmin z celem „Kolektor”, a dla innego konta przez `login` w jego konsoli, np. przez systemowe `runas`. E-mail, hasło Garmin i MFA wpisuj interaktywnie.
6. Sprawdź zakładkę Kolektor lub `status --json`, log i następny termin. Samo zainstalowanie nie wykonuje pobrania. Odbiór po wylogowaniu dotyczy wyłącznie trybu `password`.

Przykład polecenia wewnątrz konsoli właściwego konta:

```powershell
C:\Apps\GarminDatabaseCollector\GarminDatabaseCollector.exe --config C:\Users\operator\AppData\Local\GarminDatabase\settings.json login
```

DPAPI wiąże sesję z kontem i komputerem. Logowanie w GUI głównego użytkownika nie odnawia sesji dedykowanego konta. Po przeniesieniu konta/maszyny potrzebne jest nowe logowanie. Nie kopiować ani automatycznie usuwać cudzej sesji, pgpass, ustawień, ZIP i eksportów.

## Linux i Raspberry Pi OS — instalacja bez GUI

Wymagane są Python 3.12+, system 64-bit i systemd obsługujący `LoadCredentialEncrypted` oraz `systemd-creds` (250+). Biblioteki muszą mieć binarne zależności dla platformy. Raspberry Pi OS Bookworm domyślnie dostarcza starszego Pythona; przygotuj interpreter 3.12+ osobno. PostgreSQL 16+ może działać na innym hoście.

Przykładowy układ po utworzeniu dedykowanego konta `garmin-collector` z własnym katalogiem domowym:

```sh
sudo python3.12 -m venv /opt/garmin-database/.venv
sudo /opt/garmin-database/.venv/bin/python -m pip install '.[collector]'
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/settings.json init
```

Instalację pakietu wykonuj z katalogu źródeł; na dedykowanej maszynie dopuszczalna jest również instalacja zbudowanego wheel z dodatkiem `[collector]`. Interpreter i pakiet muszą być czytelne/wykonywalne dla użytkownika usługi. Qt i SDK MCP nie należą do zależności kolektora.

Edytuj konfigurację: ustaw `run_as`, DSN bez hasła, katalogi, interwał i kotwicę. Przygotuj `.pgpass` konta kolektora z trybem 0600. Następnie jako administrator:

```sh
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/settings.json prepare-key
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/settings.json schedule install
```

Instalacja tworzy jednostki `garmin-database-default.service` i `.timer` pod `/etc/systemd/system`, przydziela katalogi kontu usługi i nie pobiera historii. Domyślnie harmonogram pozostaje wyłączony. Klucz AES jest generowany w pamięci i przekazywany przez pipe do systemd-creds. Nie nadpisuj istniejącego poświadczenia.

Pierwsze logowanie uruchom z tym samym kontem i poświadczeniem co jednostka systemowa:

```sh
sudo systemd-run --wait --collect --pty \
  --property=User=garmin-collector \
  --property=LoadCredentialEncrypted=garmin-session-key:/etc/garmin-database/session-key.cred \
  /opt/garmin-database/.venv/bin/garmin-db-collector \
  --config /etc/garmin-database/settings.json login
```

Po logowaniu włącz harmonogram:

```sh
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/settings.json schedule enable
sudo /opt/garmin-database/.venv/bin/garmin-db-collector --config /etc/garmin-database/settings.json status --json
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

Atomowy zapis Windows zachowuje ACL przez [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew). Przejściowe blokady 32, 33 i 1175 są ponawiane przez maksymalnie 0,77 s; inne błędy pozostają błędami zapisu. Nie ma fallbacku zmieniającego uprawnienia. Starsza sąsiednia konfiguracja jest odczytywana także przed pierwszym zapisem, aby zachować widoczne konto i cykl; dopiero zapis przenosi ją do sekcji `collector`.
