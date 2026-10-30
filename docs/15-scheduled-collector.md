# Kolektor cykliczny — uzgodniony zakres i projekt techniczny

Status: specyfikacja funkcji do realizacji, ustalona w QA 2026-10-30. Harmonogram, polecenia kolektora i magazyn sesji Linux opisane poniżej nie są jeszcze zaimplementowane. Dostępny mechanizm pobierania opisuje [synchronizacja](04-synchronization.md).

## Cel i decyzje

Cyklicznie aktualizować PostgreSQL danymi z obecnego eksportu dobrostanu Garmin Connect, bez otwartego GUI i bez zalogowanego użytkownika systemowego. Lokalny Windows służy pierwszym testom; docelowo kolektor działa na dedykowanej maszynie. Położenie PostgreSQL jest niezależne od położenia kolektora.

| Obszar | Ustalenie |
| --- | --- |
| Źródło | Obecne `garminconnect` i dzienny eksport wellness z Garmin Connect; endpoint jest nieoficjalny |
| Uruchamianie | Jednorazowy proces przez Windows Task Scheduler lub `systemd.timer` + `systemd.service` |
| Systemy | Windows 11 x64, Raspberry Pi OS 64-bit, Debian/Ubuntu 64-bit z systemd |
| Cykl | Konfigurowalny, minimum 15 minut; początkowo 120 minut |
| Terminy | Stałe, niezależne od długości poprzedniej synchronizacji |
| Restart i przestój | Najbliższy przyszły termin, bez natychmiastowego pobierania i odtwarzania pominiętych uruchomień |
| Zakres danych | Dokładnie obecne „Pobierz nowe dane”, bez dodatkowego okna ostatnich N dni |
| GUI | Ręczne pobieranie niezależne od kolektora; wspólna logika i blokady |
| Zajęta blokada | Automat zapisuje informację we własnym logu i czeka do następnego zwykłego terminu; bez powiadamiania użytkownika |
| Błąd przejściowy | Obecne próby wewnątrz synchronizacji, później następny zwykły termin |
| Konfiguracja | Ustawienia lokalnego GUI Windows; plik i CLI na maszynie bez GUI |
| Konta | Dedykowane konto kolektora; również do testów Windows, gdzie główne konto korzysta z Hello/PIN |
| PostgreSQL | Początkowo przy kolektorze; obsługiwany także zdalny serwer przez DSN/libpq |
| Dystrybucja | Windows: osobny EXE; Linux/Pi: Python 3.12+ i venv; kolektor bez Qt |
| Diagnostyka | Trwały status i log lokalny, odczytywane przez CLI i lokalne Ustawienia Windows |

Zdalne sterowanie kolektorem z aplikacji Windows, hub HTTP, zdalny MCP, powiadomienia zewnętrzne, automatyczny eksport i nowe źródła danych pozostają poza zakresem. Administrowanie maszyną Linux/Pi odbywa się lokalnie lub przez SSH.

## Punkt wyjścia i konieczne zmiany

Istniejący `application/use_cases/synchronize.py` obsługuje pobieranie, próby, import, deduplikację, anulowanie i `SyncSummary`. `bootstrap/dependencies.py` składa ten sam przypadek użycia dla GUI i CLI. `ImportDays.download_days` realizuje wybór dni. Nie tworzyć drugiej implementacji tych reguł dla harmonogramu.

Przyrostowy zakres zaczyna się od ostatniego dnia zarejestrowanego archiwum włącznie, do dzisiaj Europe/Warsaw, z dotychczasową obsługą wcześniejszych błędów i nieukończonych importów. Przy pustej bazie obowiązuje dotychczasowy początek zakresu 2024-01-01. Znane `not_found_unverified` pozostają nierozstrzygnięte i są pomijane bez ponownego żądania, tak jak dziś. Nie włączać `refresh_all` w automacie. FIT pozostają deduplikowane po SHA-256, a nowe sieciowe ZIP są przetwarzane w pamięci.

Istniejąca blokada PostgreSQL chroni wspólną bazę/schemat także między hostami. Lokalny plik blokady chroni katalog danych. Potrzebne są dodatkowo: rozpoznawalny typ zajętości blokady, ochrona magazynu tokenów podczas logowania/odświeżania oraz lokalna blokada pojedynczej instancji kolektora. Nie rozpoznawać zajętości przez treść komunikatu wyjątku.

`Services.prepare()` uzyskuje obecnie blokadę zapisu i inicjalizuje bazę przy tworzeniu usług. Trzeba rozdzielić sprawdzenie gotowości schematu do odczytu od inicjalizacji/migracji pod blokadą. Otwarcie GUI przy działającym kolektorze ma pozwalać przeglądać zatwierdzone dane. Inicjalizacja nie może oznaczać aktywnego importu innego procesu jako przerwanego.

Obecny `SessionStore` obsługuje wyłącznie DPAPI, nie ma CLI logowania, trwałego statusu kolektora ani rejestracji harmonogramu. `SyncSummary` wymaga uzupełnienia o bezpieczny, strukturalny powód zatrzymania i termin ponownej próby. Obecne zależności pakietu instalują Qt również dla CLI; wariant kolektora musi mieć oddzielny zestaw zależności.

## Podział kodu

Pozostają Python 3.12+, PostgreSQL 16+ i Clean Architecture. Nowe elementy mają być małe i niezależnie składane. Poniższe nazwy są projektem wykonawczym; nie oznaczają dostępnych już modułów ani poleceń.

| Warstwa | Odpowiedzialność |
| --- | --- |
| `domain/schedule.py` | Czyste wyznaczanie terminów, pomijanie zaległych terminów, walidacja interwału |
| `application/collector_models.py` | Konfiguracja, wynik uruchomienia i bezpieczne stany kolektora |
| `application/use_cases/run_collector.py` | Jedno wykonanie: konfiguracja, blokady, sprawdzenie terminu/pauzy, wspólny Sync, zapis wyniku |
| `application/ports.py` | Kontrakty zegara, harmonogramu systemowego, konfiguracji, stanu, blokad i sesji |
| `adapters/inbound/collector/commands.py` | CLI kolektora i wejście wywoływane przez system |
| `adapters/outbound/scheduler/` | Rejestracja, aktualizacja i odczyt zadania Windows lub jednostek systemd |
| `adapters/outbound/security/` | DPAPI oraz szyfrowany magazyn Linux; kontrola dostępu i zapis tokenów |
| `adapters/outbound/filesystem/` | Oddzielna konfiguracja kolektora, atomowy status i rotowane logi |
| `bootstrap/collector.py` | Składanie wyłącznie zależności potrzebnych dla wybranego polecenia |
| Istniejące GUI/bootstrap/build | Ustawienia automatyzacji, bezpieczny start odczytów, osobna dystrybucja kolektora |

Domain i application używają wyłącznie biblioteki standardowej. Qt, psycopg, Garmin SDK, systemd, Windows API i kryptografia pozostają w adapterach. MCP zachowuje odrębny proces tylko do odczytu i dotychczasowe granice zależności. Nie dodawać stałego demona ani serwera HTTP.

## Kontrakt harmonogramu

Konfiguracja określa interwał w pełnych minutach, co najmniej 15, i początek harmonogramu. Terminy wynikają z początku i interwału, a nie z końca poprzedniej operacji. Domyślny interwał to 120 minut. Włączenie lub zmiana konfiguracji wyznacza pierwszy przyszły termin.

Proponowana reprezentacja wykonawcza: jednoznaczna kotwica UTC i terminy `anchor_at + k * interval_minutes`. Data pobierania i prezentacja godzin pozostają Europe/Warsaw. Taki interwał oznacza rzeczywisty upływ czasu; przy DST lokalna godzina może zmienić się o godzinę. Nie przesuwać kotwicy przy zakończeniu operacji, restarcie lub błędzie. Model nie zawiera osobnego edytora cron.

Nie odtwarzać pominiętych uruchomień. W systemd wyłączyć `Persistent`; w Windows wyłączyć uruchamianie zaległego zadania przy odzyskaniu dostępności. Nie dodawać wyzwalacza pobierania przy rozruchu lub logowaniu. Wyłączyć systemowe dodatkowe próby po błędzie; ponowienia HTTP pozostają w istniejącym Sync. Termin przypadający podczas dłuższej pracy jest pomijany, bez kolejki i bez wykonania zaraz po jej zakończeniu.

Windows używa powtarzalnego wyzwalacza i polityki ignorowania nowego uruchomienia przy aktywnej instancji. systemd uruchamia usługę `Type=oneshot` pod dedykowanym użytkownikiem. Nieaktywne zadanie nie utrzymuje procesu Pythona. Wyłączenie harmonogramu zatrzymuje przyszłe uruchomienia; rozpoczęta transakcja kończy się lub jest osobno bezpiecznie anulowana.

Interwał dotyczy faktycznej synchronizacji. Dla interwałów niewyrażalnych bezpośrednio w kalendarzu systemd adapter może uruchamiać krótką kontrolę terminu częściej. Kontrola kończy się bez SQL, Garmin, odczytu sekretów i zapisu dziennika, jeżeli nie przypada termin. Nie ograniczać konfiguracji po cichu do dzielników doby ani nie skracać odstępu przy północy. Kontrola terminu jest jednorazowym procesem, bez pętli oczekującej w tle.

Przed wykonaniem pod lokalną blokadą atomowo oznaczyć termin jako podjęty. Kolejne wywołanie tego samego terminu nie może powtórzyć pobierania. Po restarcie, długim uśpieniu i zmianie zegara pominięte terminy nie są nadrabiane. Tolerancję opóźnienia wyzwalacza oraz inicjalizację po rozruchu trzeba sprawdzić na obu adapterach; nie mogą powodować pobierania natychmiast po starcie maszyny.

## Konfiguracja i trwały stan

Kolektor ma wersjonowany plik konfiguracji niezależny od `settings.json` preferencji GUI. Minimalne pola: identyfikator instancji, włączenie, interwał, kotwica, bezwzględny katalog danych, parametry połączenia PostgreSQL bez hasła oraz lokalizacje sesji i stanu. Parametry połączenia stosują dotychczasową kolejność: niepusty DSN, `GARMIN_DATABASE_DSN`, libpq. Sekrety nie trafiają do JSON; hasło PostgreSQL dostarcza pgpass/PGPASSFILE lub środowisko właściwego konta.

Na Windows proponowaną lokalizacją konfiguracji i statusu jest wydzielony katalog instancji pod `%PROGRAMDATA%/GarminDatabase/collector/`. Sesja DPAPI należy do konta zadania. Na Linux konfiguracja należy do administratora pod `/etc/garmin-database/`, stan i zaszyfrowana sesja do konta kolektora pod `/var/lib/garmin-database/`, a logi mają osobny katalog pod `/var/log/garmin-database/`. Wszystkie ścieżki uruchomienia są bezwzględne. Katalog roboczy procesu nie wpływa na wybór bazy ani plików.

GUI może edytować dozwoloną konfigurację i czytać bezpieczny status; nie otrzymuje prawa do odczytu sesji dedykowanego konta. ACL/uprawnienia muszą umożliwiać odpowiednim procesom korzystanie z lokalnej blokady katalogu danych. Nie kopiować tokenów ani pgpass między kontami przy zapisie ustawień.

Zapis konfiguracji i zastosowanie harmonogramu mają osobne wyniki. Sam zapis JSON nie może być prezentowany jako skuteczna zmiana zadania. Przechowywać rewizję konfiguracji zastosowanej przez adapter; błąd rejestracji pozostawia jawny stan „niezastosowane”. Zmiana konta lub połączenia SQL wymaga osobnego sprawdzenia dostępu tego konta, bez testowego importu. Polecenie odczytu statusu nie tworzy `Services`, nie inicjalizuje bazy i nie wymaga jej dostępności.

Stan wykonania jest lokalnym, atomowo zapisywanym plikiem: identyfikator uruchomienia i terminu, rewizja konfiguracji, początek/koniec UTC, ostatni właściwy wynik synchronizacji, ostatni sukces, bezpieczne liczniki i kod błędu, następny termin, ewentualna pauza autoryzacji i `not_before`. Termin następny trzeba zestawiać z faktycznym stanem zadania systemowego; sama obecność JSON nie dowodzi rejestracji zadania.

Zajętość blokady jest zdarzeniem informacyjnym w logu kolektora. Nie wywołuje powiadomienia, komunikatu w dzienniku ręcznych operacji ani błędu na głównym ekranie GUI. Nie zastępuje wyniku ostatniej faktycznej synchronizacji pozorną awarią. Awaria procesu pozostawia rozpoznawalny niedokończony przebieg, a system zwalnia blokady; następny zwykły cykl korzysta z obecnego wznowienia importu.

## Sesje i konta

Windows: zadanie działa także bez zalogowanego użytkownika, pod lokalnym kontem z hasłem. Główne konto Hello/PIN nie jest podstawą bezobsługowego zadania. Windows obsługuje poświadczenia rejestracji; aplikacja nie zapisuje hasła konta w konfiguracji, poleceniu ani logu. Nie używać trybu S4U jako zamiennika, ponieważ ma ograniczenia dostępu do sieci i zaszyfrowanych plików. Nie uruchamiać kolektora jako SYSTEM.

Pierwsze logowanie Garmin wykonuje się interaktywnie pod kontem kolektora, z MFA. DPAPI użytkownika pozostaje mechanizmem szyfrowania sesji Windows. Sesja GUI głównego użytkownika i sesja dedykowanego konta kolektora są oddzielne. Logowanie w zwykłym GUI nie odnawia automatycznie sesji innego konta. Przeniesienie maszyny/konta wymaga nowego logowania, a nie kopiowania `session.bin`.

Linux/Pi: proponowany magazyn to uwierzytelnione szyfrowanie sesji z losowym kluczem, np. AES-GCM przez adapter `cryptography`. Klucz jest trwale zabezpieczony przez `systemd-creds`, a `LoadCredentialEncrypted` przekazuje go uruchomionemu procesowi. Klucz i tokeny nie są wartościami zmiennych środowiskowych ani argumentami procesu. Sesja jest odrębnym szyfrowanym plikiem zapisywalnym przez kolektor; nie umieszczać odświeżanych tokenów w tylko do odczytu katalogu poświadczeń systemd. Wymagana jest wersja systemd obsługująca ten mechanizm; brak wsparcia kończy przygotowanie czytelnym błędem, bez jawnego fallbacku.

Administrator przygotowuje chroniony klucz i uruchamia jednorazowe logowanie CLI z tym samym kontem i mechanizmem poświadczeń co zadanie, także przez SSH. Samo przełączenie użytkownika bez udostępnienia poświadczenia nie wystarcza. Podczas odświeżania sesja jest zapisywana atomowo, z właściwym właścicielem, uprawnieniami i kontrolą współbieżności. Nie wymaga odblokowywania graficznego keyringu ani ręcznego odblokowania po restarcie. Mechanizm nie zastępuje ochrony nośnika i nie chroni przed administratorem przejętej maszyny.

Hasło Garmin i MFA są używane tylko w interaktywnej operacji logowania. Zaplanowany proces nigdy nie oczekuje na wpisanie kodu. Wygaśnięcie sesji oznacza trwały `auth_required`; kolejne terminy mogą sprawdzić stan lokalnie, ale nie ponawiają logowania sieciowego do czasu zapisania nowej sesji kolektora.

## Współbieżność, wyniki i błędy

Ręczne GUI i kolektor wywołują wspólny Sync bez kanału zlecania operacji ani kolejki poleceń. Ochrona musi objąć cały okres korzystania z tej samej sesji Garmin, w tym logowanie i zapis odświeżonych tokenów, oraz dotychczasową blokadę writera. Ustalić jeden porządek pozyskiwania blokad dla wszystkich wejść i zwalniać je także przy anulowaniu. Nie wykonywać żądania Garmin po nieudanym uzyskaniu wymaganej blokady.

| Wynik | Zachowanie kolektora |
| --- | --- |
| Sukces | Zapis podsumowania, następny zwykły termin |
| Zajęta blokada | Informacja tylko w logu automatu, następny zwykły termin |
| Brak internetu / błąd przejściowy | Obecne próby Sync, potem następny zwykły termin |
| Niedostępny PostgreSQL | Lokalny status i log, bez pobierania Garmin, następny zwykły termin |
| Brak/wygasła sesja, HTTP 401 | `auth_required`, wymagane interaktywne logowanie kolektora |
| HTTP 403 | Przerwanie bieżącego pobierania, bezpieczny status odmowy dostępu; bez uznawania go automatycznie za błędne hasło |
| HTTP 429 | Przerwanie, trwały najwcześniejszy termin ponowienia z `Retry-After`; ponowienie tylko w zwykłym terminie nie wcześniejszym niż ta granica |
| HTTP 404 | Dotychczasowy nierozstrzygnięty dzień, pozostałe dni według obecnego Sync |
| Błąd FIT / archiwum | Dotychczasowe transakcje i wznowienie, wynik częściowy z osobnymi licznikami |
| Zatrzymanie / awaria procesu | Zachowane ukończone FIT, rollback nieukończonego FIT, wznowienie w następnym zwykłym terminie |

`Retry-After` w sekundach i HTTP-date jest przeliczany na jednoznaczne UTC i utrzymywany pomiędzy procesami. Brak nagłówka nie powoduje dodatkowych prób pomiędzy cyklami. Nie parsować tekstu postępu w celu odtworzenia wyniku. Rozszerzony wynik aplikacyjny przekazuje do kolektora wyłącznie dozwolone kategorie, status HTTP i datę ponowienia. Zapamiętana pauza nie znika przy restarcie.

Logi zawierają datę, identyfikator uruchomienia, etap, bezpieczne kategorie i liczniki. Nie zawierają wartości zdrowotnych, tokenów, haseł, kodów MFA, treści odpowiedzi, pełnych wyjątków Garmin/psycopg ani DSN. Proponowany domyślny limit to plik 5 MiB i pięć kopii rotacji. Logi i status nie trafiają do Git. Zwykłe kontrolne wywołanie poza terminem nie produkuje wpisu.

## GUI, CLI i instalacja

Nowa sekcja Ustawień Windows: włączenie automatyzacji, interwał i początek harmonogramu, wskazanie konfiguracji kolektora/połączenia SQL, konto uruchomienia, zapis i osobne zastosowanie zadania, stan rejestracji, następny termin, ostatnia synchronizacja, stan sesji kolektora i dostęp do jego logu. Operacje plikowe, systemowe i SQL działają poza wątkiem Qt. Status sesji GUI i kolektora nie może sugerować, że logowanie jednego konta naprawiło drugie.

Zmiany wymagające uprawnień systemowych korzystają z ograniczonej operacji administracyjnej. Zwykłe odczyty i cała aplikacja nie wymagają uruchamiania jako administrator. Nie dodawać powiadomień zewnętrznych ani zdalnego API. Na Linux/Pi obowiązują plik konfiguracyjny i CLI/SSH; Windows GUI nie zarządza nimi przez sieć.

Proponowane polecenia przyszłego `garmin-db-collector`: `run --scheduled`, `login`, `status --json`, `logs` oraz `schedule install|apply|enable|disable|status`, ze wspólnym `--config` wskazującym bezwzględną ścieżkę. To projekt kontraktu CLI, nie instrukcja dla obecnej wersji. Polecenia administracyjne sprawdzają wynik i rejestrację w systemie; nie przekazują sekretów w argumentach. Instalacja zadania nie tworzy konta systemowego ani nie uruchamia importu historii.

Windows otrzymuje osobną dystrybucję PyInstaller onedir `GarminDatabaseCollector`, bez Qt, z bibliotekami Garmin, FIT, PostgreSQL, strefami i SQL. Ścieżka EXE jest stabilna i zadanie nie zależy od otwartego GUI ani aktywnego venv. Linux/Pi otrzymuje pakiet kolektora i venv Pythona 3.12+, bez Qt i bez SDK MCP jako obowiązkowych zależności. Dostępność binarnych zależności i mechanizmu systemd wymaga odbioru na ARM64 oraz x86-64.

PostgreSQL pozostaje osobnym serwerem. Lokalnie połączenie jest na localhost; przy oddzielnym hoście obowiązują jawne parametry sieciowe i TLS `verify-full` zgodnie z [instrukcją PostgreSQL](13-postgresql-setup.md). Konto zadania ma własny dostęp do pgpass/libpq. Nie zakładać, że konfiguracja środowiska lub pgpass użytkownika GUI jest dostępna dla zadania. Nie współdzielić pliku bazy ani nie dodawać lokalnego fallbacku SQL.

## Zakres realizacji i odbiór

1. Kontrakty konfiguracji, terminów i wyników, porty, typ zajętej blokady oraz oddzielenie inicjalizacji od odczytu. Zachować wspólną semantykę synchronizacji.
2. Jednorazowy kolektor i lokalny stan/logi; strukturalne powody zatrzymania, trwałe pauzy i ochrona sesji. Wynik dostępny także bez PostgreSQL.
3. CLI logowania i magazyny sesji Windows/Linux, z przygotowaniem dedykowanego konta i uprawnień.
4. Adaptery Task Scheduler i systemd, zastosowanie i kontrola rewizji harmonogramu, restart bez nadrabiania uruchomień.
5. Ustawienia Windows, oddzielne statusy sesji, operacje w workerach i rozdzielone zależności pakietów.
6. Build Windows i instalacja Linux/ARM64, instrukcje wdrożenia oraz testy odbiorowe na docelowych systemach.

Minimalny odbiór obejmuje:

- Domyślne 120 minut, odrzucenie wartości poniżej 15, stałe terminy mimo długości pracy; również interwały 17 i 90 minut, północ, DST i zmianę zegara.
- Restart i uśpienie: brak natychmiastowego pobrania, brak kolejki zaległych wywołań, poprawne dane nadrobione przez następny zwykły Sync.
- GUI i automat: brak równoległego zapisu, ciche odłożenie automatu i tylko jego log; GUI otwiera się i odczytuje dane podczas importu.
- Dwa hosty do jednego PostgreSQL: działająca blokada serwerowa; konfiguracja kolektora obsługuje lokalny i zdalny DSN.
- Brak SQL/internetu, 401/403/429/404, `Retry-After` po restarcie, rozdzielenie nierozstrzygniętych dni od błędów FIT i pełnego sukcesu.
- Anulowanie i awaria: rollback nieukończonego FIT, zachowane wcześniejsze dane, zwolnione blokady, bezpieczne wznowienie.
- Poprawny właściciel i atomowy zapis sesji, wykluczenie wycieku sekretów, brak odświeżenia sesji kolektora przez login innego konta.
- Windows: osobny EXE, rzeczywiste DPAPI i pobranie pod dedykowanym kontem przy wylogowanym głównym użytkowniku.
- Linux x86-64 i Raspberry Pi OS ARM64: instalacja bez Qt, szyfrowana sesja, timer, restart bez interakcji i rzeczywisty dostęp do Garmin.
- Zapis kontra zastosowanie konfiguracji, błąd rejestracji, włączanie/wyłączanie, odczyt statusu i logów bez PostgreSQL.
- Regresja istniejącego importu, deduplikacji, GUI, eksportu, MCP i granic architektury na syntetycznych danych.

Testy automatyczne korzystają z syntetycznych FIT i osobnej bazy PostgreSQL. Testy rzeczywistych sesji i harmonogramów wymagają właściwej platformy; wynik cloud Linux nie dowodzi działania DPAPI Windows ani Raspberry Pi. Ten dokument nie jest raportem wykonanych testów ani potwierdzeniem instalacji.

## Materiały techniczne

- [Windows: typy logowania zadania](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type).
- [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).
- [systemd.exec: poświadczenia procesu](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).
