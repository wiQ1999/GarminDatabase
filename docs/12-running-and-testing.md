# Uruchamianie aplikacji, build i testy

Aplikacja Windows i rdzeń bez UI używają wyłącznie PostgreSQL 16+. Ten sam typ bazy obowiązuje lokalnie i na serwerze. Najpierw [zainstaluj PostgreSQL, utwórz bazę i skonfiguruj połączenie](13-postgresql-setup.md). Python: 3.12 lub nowszy, zależności: `requirements-dev.txt` dla dewelopera, `requirements-app.txt` dla aplikacji.

## Uruchomienie

Windows: `.venv/Scripts/python.exe -m garmin_database` lub `dist/GarminDatabase/GarminDatabase.exe`. Zachowaj cały folder dystrybucji z `_internal`. PostgreSQL działa jako osobna usługa. Hasło PostgreSQL pobierane jest z pgpass lub środowiska, a hasło Garmin służy wyłącznie logowaniu i nie jest zapisywane. Sesja Garmin tej wersji nadal wymaga Windows DPAPI.

Przed pierwszymi testami lokalnymi zamknij starą aplikację i usuń `garmin.sqlite3` oraz jego `-wal`, `-shm`, `-journal` z rzeczywistego katalogu danych. Nie usuwaj oryginalnych ZIP ani eksportów. Nie implementujemy migracji danych SQLite; historię zapisujemy od nowa w PostgreSQL.

1. W Ustawieniach sprawdź folder archiwów i połączenie PostgreSQL. Nie podawaj hasła w polu połączenia; ustawienia je odrzucą.
2. Zaloguj się do Garmin, jeśli chcesz pobierać nowe dni. Import lokalnych ZIP nie wymaga sesji.
3. „Pobierz dane” nadrabia dni do wczoraj Europe/Warsaw i importuje do PostgreSQL. „Przetwórz ponownie” wymienia wyniki dekodowania atomowo.
4. Dane pokazują szczegóły dnia, źródłowe podsumowania Garmin lub oznaczone średnie pięciu obsługiwanych parametrów. Wykres odświeża się automatycznie. Trend jest wyłącznie warstwą prezentacji.
5. Eksport tworzy nowy folder z historią podsumowań, szczegółami i manifestem. Zachowuje wcześniejsze pakiety.

## Testy

Skonfiguruj `GARMIN_TEST_DATABASE_DSN` na osobną bazę testową PostgreSQL. Fixture tworzą osobny schemat per test i usuwają go po zakończeniu. Korzystają tylko z syntetycznych FIT/ZIP. Nie ma zamiennika SQLite ani pomijania testów z powodu braku serwera.

Windows PowerShell:

```powershell
uv pip install --cache-dir .uv-cache --python .venv/Scripts/python.exe -r requirements-dev.txt
$env:GARMIN_TEST_DATABASE_DSN = 'host=localhost port=5432 dbname=garmin_tests user=garmin_test'
powershell -NoProfile -File scripts/run_tests.ps1
```

Linux/Raspberry Pi OS:

```sh
uv pip install --cache-dir .uv-cache --python .venv/bin/python -r requirements-dev.txt
export GARMIN_TEST_DATABASE_DSN='host=localhost port=5432 dbname=garmin_tests user=garmin_test'
.venv/bin/python scripts/run_tests.py
```

`run_tests.py` jest wspólnym runnerem; PowerShell wywołuje ten sam kod. Wymaga co najmniej 85% coverage rdzenia i CLI z gałęziami. Raporty: `test-results/results.xml` i `test-results/coverage/index.html`. Qt/rysowanie/UI mają osobne testy i nie są wliczane do progu coverage.

| Warstwa | Zakres |
| --- | --- |
| Jednostkowe | Typy FIT, precyzja, timestampy, strefa/DST, reguły podsumowań, HTTP, ustawienia i odrzucanie haseł w DSN |
| Integracyjne | Prawdziwy PostgreSQL, DDL i ograniczenia, atomowe migracje i SHA, import/rollback/CRC, idempotencja, advisory lock między katalogami, spójne snapshoty, cache i anulowanie, eksport i kursory serwerowe, brak fallbacku przy niedostępnej bazie |
| UI | Nawigacja, zakresy i daty, spinner, nieaktualne odpowiedzi, trend, eksport, ustawienia PostgreSQL, zatrzymanie, MFA |

Dwa istniejące testy integracji Windows DPAPI są pomijane na innych systemach, z jawnym powodem; muszą zostać uruchomione na Windows. Sam backend PostgreSQL nie wymaga Windows.

Kontrola statyczna:

```sh
python -m ruff check garmin_database tests desktop.py scripts/build.py scripts/run_tests.py scripts/smoke.py
python -m ruff format --check garmin_database tests desktop.py scripts/build.py scripts/run_tests.py scripts/smoke.py
```

## Build i smoke

Windows:

```powershell
powershell -NoProfile -File scripts/build_windows.ps1
powershell -NoProfile -File scripts/smoke_windows.ps1
```

Linux:

```sh
.venv/bin/python scripts/build.py
.venv/bin/python scripts/smoke.py
```

`build.py` pakuje bibliotekę psycopg_binary razem z libpq i migracjami SQL. Windows wrapper zachowuje parametry `-Python` i `-Destination`. Nie zatrzymuj aplikacji użytkownika, aby nadpisać otwartą dystrybucję; wskaż inny folder. Na Windows skrypt usuwa błędnie zebrane DLL ICU 78 kolidujące z Qt 6.12.

`smoke.py` uruchamia zbudowaną aplikację w oddzielnym schemacie bazy testowej, zapisuje syntetyczny zrzut i usuwa schemat także po błędzie. Nie używa ustawień ani bazy użytkownika. Przyjmuje opcjonalną ścieżkę do programu. Windows EXE wymaga buildu i uruchomienia na Windows; wynik paczki Linux tego nie zastępuje.

Pakiet Pythona można zbudować poleceniem `python -m build`; zarówno wheel, jak i sdist muszą zawierać migracje `garmin_database/resources/*.sql`.

## Operacje bez UI

```sh
python -m garmin_database.cli status --data-dir data
python -m garmin_database.cli import-local --data-dir data
python -m garmin_database.cli reprocess --data-dir data --from 2026-09-01
python -m garmin_database.cli export --data-dir data --parameters monitoring.heart_rate --from 2026-09-01 --to 2026-09-30 --recent-days 30 --summary-period day --output exports
```

CLI i UI czytają ten sam `database_dsn`, `GARMIN_DATABASE_DSN` i konfigurację libpq. Opcjonalne `--settings-file` wskazuje osobne ustawienia. `sync` nadal wymaga sesji Windows; ochrona sesji Linux pozostaje osobnym zakresem.

## Wznowienie i utrzymanie

Ponowne odwiedzenie kompletnego ZIP nie tworzy fikcyjnego przebiegu importu. Wymuszona wymiana FIT zachowuje poprzedni wynik po błędzie lub anulowaniu. PostgreSQL MVCC i odczyt `REPEATABLE READ READ ONLY` zapewniają spójność eksportu podczas nowego importu. Cache nie publikuje nieaktualnego wyniku i nie blokuje eksportu, gdy writer jest zajęty.

Rozmiar w Start to `pg_database_size` całej wskazanej bazy. MVCC może pozostawiać martwe wersje wierszy; utrzymaniem zajmuje się PostgreSQL autovacuum. Aplikacja nie wykonuje automatycznie `VACUUM FULL`. Długie eksporty utrzymują snapshot do końca operacji; nie pozostawiaj otwartych transakcji bez potrzeby.

Historyczne wyniki odbioru pełnej historii z 2026-10-11 dotyczyły SQLite. Nie są dowodem walidacji tych danych w PostgreSQL. Przy tej zmianie sprawdzamy dane syntetyczne; rzeczywiste dane zostaną ponownie pobrane przez użytkownika.

## Odbiór zmiany PostgreSQL — 2026-10-23

Sprawdzono w środowisku Linux x86_64, Python 3.12.14, rzeczywisty PostgreSQL 16.2, rola testowa bez superuser:

- Pełny runner: **217 zaliczonych, 2 pominięte** (wyłącznie Windows DPAPI), bez błędów; coverage rdzenia/CLI z gałęziami **92,83%**, warstwa storage **100%**.
- Jednostkowe bez serwera: 121 zaliczonych, 1 pominięty DPAPI, 97 odrzuconych przez wybór warstwy.
- Ruff i kontrola formatowania: poprawne.
- Build PyInstaller Linux, wheel i sdist: poprawne; porównano zawartość wszystkich trzech migracji z zasobami każdego artefaktu.
- Smoke zbudowanej aplikacji: poprawny, własny schemat PostgreSQL usunięty po próbie.
- Starego pliku SQLite w tym checkoutcie nie było. Rzeczywiste dane użytkownika nie były importowane ani zmieniane.

**Odbiór Windows pozostaje do wykonania:** pełny runner z dwoma testami DPAPI oraz build i smoke EXE. Brak środowiska Windows w tym zleceniu uniemożliwił ich wykonanie; powyższy wynik Linux nie oznacza pełnego odbioru wszystkich platform.

## Lokalny MCP — konfiguracja i uruchomienie

Budowanie tworzy dwa sąsiednie foldery: `GarminDatabase/` z okienkowym EXE i `GarminDatabaseMCP/` z serwerem mającym standardowe strumienie. Zachowaj oba foldery wraz z ich `_internal`. `build_windows.ps1 -Destination ...` buduje oba we wskazanym miejscu. Nie zatrzymuj wcześniejszej aplikacji użytkownika w celu nadpisania plików.

1. Przygotuj bazę przez aplikację. MCP nie pobiera, nie importuje i nie migruje danych; nie wymaga logowania Garmin.
2. W Ustawieniach włącz „Zezwalaj na odczyt przez lokalny MCP”, wybierz metryki w kolumnie MCP i zapisz ustawienia.
3. Skopiuj konfigurację klienta przyciskiem w tej sekcji i wklej ją do klienta obsługującego lokalne `stdio` i `mcpServers`. Klient wymagający wyłącznie URL/HTTP wymaga innej integracji, poza tym wydaniem.
4. Klient uruchomi proces. Wywołaj `garmin_catalog`, a następnie metodę odczytu. Okno GarminDatabase może być zamknięte. Wyłączenie dostępu w zapisanych ustawieniach działa także dla już uruchomionego klienta.

Przykład standardowej dystrybucji (przy innym `-Destination` użyj ścieżek skopiowanych z tej paczki):

```json
{
  "mcpServers": {
    "garmin_database": {
      "command": "D:/Projects/GarminDatabase/dist/GarminDatabaseMCP/GarminDatabaseMCP.exe",
      "args": ["--settings-file", "C:/Users/wikto/AppData/Local/GarminDatabase/settings.json"]
    }
  }
}
```

W źródłach odpowiednikiem jest `.venv/Scripts/python.exe mcp_stdio.py --settings-file ŚCIEŻKA`. Serwer czeka na protokół na standardowym wejściu; nie jest interaktywną konsolą. Konfiguracja z UI wskazuje bezwzględny skrypt i działa również z innego katalogu. Dla instalacji pakietu dostępne jest `garmin-db-mcp`.

### Narzędzia MCP v1

| Narzędzie | Argumenty | Wynik |
| --- | --- | --- |
| `garmin_catalog` | opcjonalny `cursor`; katalog v1 mieści pięć metryk w jednej odpowiedzi | Włączone metryki, etykiety, jednostki, dostępny zakres rozpoznanych czasów, precyzja i limity |
| `get_daily` | `date_from`, `date_to`, wymagane `metrics`, opcjonalny `cursor` | Dzienne średnie, min/max, liczniki jakości i pierwszy/ostatni czas; do 92 dni na stronę |
| `get_period_stats` | `date_from`, `date_to`, wymagane `metrics` | Jeden wiersz całego okresu na metrykę, średnia ważona próbkami, min/max, liczby próbek i dni |

Wymagany jest wybór 1–5 różnych kluczy z katalogu: `monitoring.heart_rate`, `hrv_value.value`, `respiration_rate.respiration_rate`, `spo2_data.reading_spo2`, `stress_level.stress_level_value`, jeśli są obecne i włączone. Są to średnie próbek dni, bez zgadywania znaczenia nocnego HRV czy tętna spoczynkowego. Zakres katalogu nie gwarantuje ciągłości ani pełnego pokrycia doby.

Przykładowe argumenty metod odczytu:

```json
{"date_from":"2026-09-01","date_to":"2026-09-30","metrics":["monitoring.heart_rate","hrv_value.value"]}
```

Zakres obejmuje obie daty w Warszawie i kończy się najpóźniej wczoraj. Wynik jest w `structuredContent.series`; seria podaje `parameter`, `unit`, `aggregation`, `precision`, `columns` i tablicę wierszy `data`. Krótka część tekstowa nie powiela JSON. Czas jest lokalny z pełną datą i offsetem, np. `2026-10-22T13:30:00+02:00`. Dni zmiany czasu mają rzeczywiste granice 23/25 godzin; PostgreSQL i eksport v2 zachowują momenty UTC.

Kolumny dzienne to `day`, `mean`, `minimum`, `maximum`, `valid_count`, `invalid_count`, `excluded_count`, `untimed_count`, `first_time`, `last_time`, `day_basis`. W okresie zamiast `day` są `period_from` i `period_to`, a dodatkowo `valid_days` i `requested_days`. Średnia okresowa używa niezaokrąglonych średnich dziennych z wagą liczby poprawnych próbek, tak jak eksport miesięczny. Nie jest średnią ważoną czasem ani nieważoną średnią dni. Zakres dłuższy niż 92 dni jest przetwarzany wewnętrznymi odcinkami na jednym obrazie PostgreSQL; klient dostaje wynik całego okresu. Brak poprawnych próbek daje `null`.

### Limity, kompletność i błędy

Wynik narzędzia ma najwyżej 16 KiB wraz z blokami treści i metadanymi. Nie jest to obietnica stałej liczby tokenów dowolnego modelu. Odczyt ma budżet 60 s i reaguje na anulowanie, również przez anulowanie zapytania sterownika i `statement_timeout`. Nie zwraca częściowej średniej jako pełnej. Dane i kompletność jednej odpowiedzi odnoszą się do tej samej `data_revision`, także podczas importu.

`get_daily` może zmniejszyć stronę poniżej 92 dni, aby zmieścić wynik. Podaje żądany i faktyczny zakres, `truncated` oraz `next_cursor`; kontynuacja powtarza pierwotne daty i metryki z kursorem. Strony przesuwają się również przez puste dni. Zmiana bazy, rewizji, polityki lub restart procesu unieważnia kursor i wymaga rozpoczęcia zapytania od nowa.

`gaps` odróżnia `missing_archive`, `partial_decode` i `no_valid_samples` konkretnej metryki. Dzienny `gaps_format: date_ranges` grupuje daty; okresowy `gaps_format: day_counts` podaje liczby dni według przyczyn. Dokładne daty można odczytać przez `get_daily`. Przyczyny mogą się pokrywać i nie są rozłącznym bilansem dni. Braki nie są zerami, a `wear_pct` nie jest zgadywany z liczby próbek.

Nieznana/wyłączona metryka, zły zakres, uszkodzone ustawienia, brak obsługiwanej bazy i nieaktualny kursor dają zwięzły `isError`. Nie są udanym pustym wynikiem. MCP sprawdza politykę również przed publikacją, nie czyta sesji Garmin, nie zapisuje cache i nie udostępnia SQL, FIT, eksportu na dysk ani metod zapisu. Szczegóły: [architektura](03-architecture.md), [eksport](05-export.md), [ustawienia](11-desktop-ui.md).

### Smoke test procesu i dystrybucji

```powershell
.venv/Scripts/python.exe scripts/smoke_mcp.py
.venv/Scripts/python.exe scripts/smoke_mcp.py --executable dist/GarminDatabaseMCP/GarminDatabaseMCP.exe
```

Skrypt wymaga `GARMIN_TEST_DATABASE_DSN`, tworzy i sprząta osobny schemat PostgreSQL oraz zapisuje syntetyczne pliki i ustawienia w `test-results/mcp-smoke`, uruchamia rzeczywisty proces klientem SDK i sprawdza inicjalizację, trzy narzędzia, limit rozmiaru, średnią dwuletniego okresu oraz odcięcie dostępu bez restartu. Weryfikuje również 10 pytań z `tests/mcp_evaluation.xml`: średnie, rozpiętość, liczniki, brak danych, rok przestępny, lokalny czas i stronicowanie. Raport zawiera wyłącznie status i liczniki. Dodatkowo wykonaj `scripts/smoke_windows.ps1` dla GUI. Sandbox Windows może blokować wewnętrzne `socketpair` pętli asyncio; w tym środowisku testy protokołu wymagają uruchomienia z uprawnieniami pozwalającymi na utworzenie tej pętli. Nie oznacza to otwierania serwera HTTP.


## Historyczny odbiór MCP przed połączeniem z PostgreSQL — 2026-10-22

Pełny zestaw: **244 testy**, coverage rdzenia i CLI z gałęziami **93,43%**. Nowe testy obejmują migrację wyboru, niezależne listy kanałów, walidację eksportu GUI/CLI/bezpośrednio, zgodność średnich okresowych z eksportem, brak połączeń zapisujących z MCP, zakres dwóch lat bez cache, DST, anulowanie, limit bajtów, puste dni, zmianę rewizji i odcięcie dostępu przed odpowiedzią. Test protokołu uruchamia osobny proces z innego katalogu roboczego i wywołuje trzy narzędzia klientem SDK. Wszystkie ustawienia testów są izolowane od profilu użytkownika.

Paczki odbiorowe są w `dist/mcp-release/GarminDatabase/` oraz `dist/mcp-release/GarminDatabaseMCP/`. Build obu paczek, smoke GUI oraz źródeł i EXE MCP zakończyły się poprawnie; oba warianty MCP przeszły 10 ewaluacji i kontrolę pustego stderr. Serwer korzysta z istniejących strumieni Python z ustawionym UTF-8; dodatkowe opakowanie tego samego bufora zamykało go przed flush przy kończeniu PyInstaller. Raporty lokalne: `test-results/results.xml`, `test-results/coverage/index.html`, `test-results/mcp-source-verified/mcp-smoke.json`, `test-results/mcp-packaged-verified/mcp-smoke.json` i `test-results/mcp-build-final.log`. Dane, raporty i paczki pozostają poza Git.

Pomiar złożoności Radon przed i po wydzieleniu odpowiedzialności:

| Funkcja | Przed | Po |
| --- | ---: | ---: |
| `monthly_summaries` | 19 | 2 |
| `Exporter.history` | 11 | 7 |
| `Exporter.generate` | 11 | 8 |
| `Settings.validate` | 12 | 9 |
| `cli.main` | 15 | 3 |
| `Window.refresh` | 14 | 2 |

Wydzielono reduktor okresów, wspólny opis podsumowań, walidację udostępniania oraz obsługę poleceń i elementów UI. Zgodność zachowania potwierdza pełny zestaw testów, w tym miesięczny odczyt nieuporządkowanych dni. Nowe funkcje MCP mają złożoność najwyżej 8. Raport jest w ignorowanym `test-results/mcp-complexity.json`.

## Odbiór po scaleniu PostgreSQL i MCP — 2026-10-23

Połączony zestaw na Linux/Python 3.12/PostgreSQL 16.2: **269 zaliczonych, 2 pominięte** (Windows DPAPI), coverage rdzenia i CLI z gałęziami **92,99%**. Przeszły Ruff i formatowanie, build GUI oraz MCP, wheel/sdist, smoke zbudowanego GUI i rzeczywistego protokołu MCP ze źródeł oraz z paczki. Oba testy MCP zaliczyły 10 ewaluacji i kontrolę pustego stderr.

MCP korzysta z tego samego `database_dsn` co UI/CLI. Odczyt sprawdza `schema_migrations`, używa `REPEATABLE READ READ ONLY` i pozostawia cache bez zmian. Anulowanie przerywa aktywne zapytanie PostgreSQL, a budżet ogranicza je również przez `statement_timeout`. Kursory wiążą się z rzeczywistym połączeniem i OID bazy/schematu zamiast pliku SQLite. Nowe testy obejmują zmianę DSN, anulowanie aktywnego SQL i przekroczenie czasu katalogu. Pełny odbiór Windows nadal wymaga odpowiedniego środowiska.

## Lokalny odbiór Windows — 2026-10-23

Po przygotowaniu pustej lokalnej bazy PostgreSQL 16.15 i osobnej bazy `garmin_tests` wykonano pełny runner na Windows/Python 3.12.14: **271 testów zaliczonych, bez pominięć i błędów**, w 255,87 s. Oba testy rzeczywistego DPAPI zostały wykonane. Coverage rdzenia i CLI z gałęziami wyniósł **94,07%**, przy wymaganym progu 85%. Wszystkie testy korzystały z syntetycznych danych i izolowanych schematów w bazie testowej.

Zbudowano GUI oraz MCP do `dist/postgresql-release`. Smoke GUI z nowego EXE przeszedł; sprawdzono także zrzut pustego ekranu Start. Źródłowy i zbudowany serwer MCP zaliczyły po 10 ewaluacji trzech narzędzi i kontrolę pustego stderr. Raporty lokalne są w `test-results/postgresql-windows-tests.log`, `test-results/results.xml`, `test-results/coverage`, `test-results/postgresql-build.log`, `test-results/postgresql-mcp-source-smoke/mcp-smoke.json` i `test-results/postgresql-mcp-smoke/mcp-smoke.json`.

Sprawdzono również zatrzymanie lokalnego PostgreSQL i ponowne włączenie go przez plik startowy, w tym przez systemowy Windows PowerShell używany przez CMD. Serwer pozostał uruchomiony i gotowy do połączeń. Plik startowy czeka wyłącznie na zakończenie `pg_ctl`; oczekiwanie na całe drzewo procesów blokowałoby start GUI przez czas działania serwera.

Lokalna instalacja i plik startowy są opisane w [konfiguracji PostgreSQL](13-postgresql-setup.md#przygotowana-instalacja-lokalna-windows--2026-10-23). Usunięto stary SQLite i, po osobnym potwierdzeniu użytkownika, stare archiwa oraz indeksy pobierania. Zachowano eksporty, ustawienia i sesję Garmin; jej lokalne odszyfrowanie jest poprawne. Baza aplikacji jest pusta i gotowa na pobranie od 2024-01-01 do wczoraj. Nie uruchomiono pobierania ani importu rzeczywistej historii i nie sprawdzano ważności sesji przez sieć Garmin. Ten odbiór techniczny uzupełnia wcześniejsze wyniki Linux; nie oznacza odbioru rzeczywistej historii w PostgreSQL ani testów Raspberry Pi.

## Modernizacja ustawień i ponawianie logowania — 2026-10-23

Sekcje formularza, wybór folderu w wierszu ścieżki i osobne okno postępu opisuje [specyfikacja UI](11-desktop-ui.md#ustawienia-sesja-i-lokalizacje). Test regresyjny odtworzył problem: kolejne żądanie MFA nie czekało na nowy kod, ponieważ Event poprzedniego potwierdzenia pozostawał ustawiony. Obecnie każda próba logowania ma osobnego workera i klienta; kolejne żądania kodu zerują stan, a anulowana próba nie zapisuje sesji.

Pełny runner Windows przeszedł bez błędów i pominięć; coverage rdzenia/CLI z gałęziami wyniósł **94,08%**. Regresje obejmują błąd danych logowania i połączenia, kolejną próbę bez restartu, anulowanie, powrót po anulowaniu MFA, kolejne kody w tej samej próbie, zwalnianie przechwyconych danych oraz zamknięcie aplikacji podczas logowania. Użyto wyłącznie atrap Garmin i izolowanych schematów PostgreSQL; nie wykonywano prawdziwego logowania. Ruff i formatowanie całego projektu przeszły. Moduł `login_dialog.py` jest warstwą Qt i, podobnie jak pozostałe UI, nie wchodzi do coverage rdzenia.

Build GUI/MCP jest w `dist/settings-refresh`; smoke GUI oraz zbudowanego MCP przeszedł, MCP zaliczył 10 ewaluacji i kontrolę pustego stderr. Sprawdzono wizualnie formularz i okno logowania; podglądy są w `test-results/settings-preview`. Wyniki: `test-results/settings-before.log` (odtworzony błąd), `test-results/settings-focused.log`, `test-results/settings-full-tests.log`, `test-results/settings-build.log` i `test-results/settings-mcp-smoke/mcp-smoke.json`.

Radon: `Window.build_settings` ma złożoność 3 → 1, `Window.closeEvent` 7 → 5; `Window.login` 3 → 5 po dodaniu zabezpieczeń aktywnej próby. Nowe metody `LoginDialog` mają najwyżej 4. Raport: `test-results/settings-refactor.md`. Podział formularza i życia dialogu jest opisany nazwami metod; nie zwiększa zależności rdzenia od Qt.

## Jawny kod MFA i ikona aplikacji — 2026-10-23

Kod MFA jest widoczny podczas wpisywania w obu oknach kodu, natomiast hasło jest nadal maskowane. Na zlecenie użytkownika usunięto zapisaną sesję DPAPI przy zamkniętej aplikacji; ustawienia i dane pozostały na miejscu. Nie wykonywano prawdziwego logowania ani nie potwierdzono, że stara sesja była przyczyną niepowodzenia. Procedura resetu jest w [specyfikacji UI](11-desktop-ui.md#ustawienia-sesja-i-lokalizacje).

Autorska ikona ma źródło w `garmin_database/resources/app-icon.svg`. Polecenie `.venv/Scripts/python.exe scripts/generate_app_icon.py` generuje PNG dla Qt i ICO z dziewięcioma rozmiarami 16–256 px. Wygenerowane pliki są wersjonowane; zwykły build nie wymaga ponownej generacji. `scripts/build.py` przekazuje ICO do obu programów i pakuje wszystkie zasoby ikony.

Zaliczone 24 testy UI, Ruff i kontrola formatowania. Sprawdzono wizualnie ikonę w nagłówku i niezamaskowany syntetyczny kod MFA. Build GUI i MCP jest w `dist/app-icon`; smoke obu paczek poprawny, MCP zaliczył 10 ewaluacji i kontrolę pustego stderr. Oba EXE mają grupę ikon PE z dziewięcioma rozdzielczościami; PNG/ICO/SVG paczki GUI są identyczne ze źródłami. Raporty i podglądy: `test-results/app-icon-ui.log`, `test-results/app-icon-build.log`, `test-results/app-icon-preview` i `test-results/app-icon-mcp-smoke/mcp-smoke.json`. Pełnego runnera rdzenia nie powtarzano po tej zmianie UI i zasobów; jego poprzedni wynik opisano wyżej.

## Aktualizacja klienta Garmin i diagnostyka MFA — 2026-10-24

Użytkownik zgłosił ponowne niepowodzenie po podaniu kodu, przy poprawnym logowaniu w przeglądarce. Poprzedni komunikat nie odróżniał odmowy dostępu API od błędnych danych logowania. Zaktualizowano przypiętą bibliotekę z `garminconnect==0.3.17` do `0.3.20`. [Wydanie upstream](https://github.com/cyberjunky/python-garminconnect/releases/tag/0.3.20) naprawia brak pobrania strony i ciasteczek sesji przed wysłaniem danych w mobilnym logowaniu; obsługuje również blokadę HTTP 427 jako ograniczenie prób. To zastosowanie istotnej poprawki biblioteki, nie dowód, że była jedyną przyczyną błędu na koncie użytkownika.

Nowe testy `tests/test_auth_login.py` korzystają z rzeczywistej zainstalowanej biblioteki Garmin. Zastępowany jest wyłącznie transport HTTP i oczekiwanie; żadne żądania nie trafiają do Garmin. Obie ścieżki mobilne (`curl_cffi` i `requests`) przechodzą przygotowanie sesji, MFA, wymianę tokenów, potwierdzenie profilu i zapis szyfrowanego magazynu. Odmowa po MFA i odmowa API nie zastępują poprzedniej sesji; kolejna próba używa nowego klienta i może zakończyć się sukcesem. Osobno sprawdzono błąd lokalnego zapisu, usuwanie białych znaków kodu, brak zapisu przez `GARMINTOKENS`, zwolnienie hasła i callbacku oraz bezpieczne komunikaty. UI pokazuje etap i kod diagnostyczny zgodnie ze [specyfikacją](11-desktop-ui.md#ustawienia-sesja-i-lokalizacje).

Pełny runner Windows/Python 3.12.14/PostgreSQL 16.15 zaliczył **283 testy bez pominięć**, z coverage rdzenia/CLI z gałęziami **94,15%**. Po rozszerzeniu testów o drugi transport i test przekazania etapu do dialogu zaliczono również wszystkie 9 testów nowego modułu oraz dodatkowy test UI; łącznie sprawdzono 288 różnych przypadków. Kod aplikacji nie zmienił się po pełnym runnerze. Ruff i formatowanie dla zakresu kontroli z tego dokumentu poprawne. Wizualnie sprawdzono czytelność syntetycznego komunikatu; podgląd: `test-results/auth-diagnostic-preview.png`.

Nowe paczki GUI i MCP są w `dist/auth-update`; lokalny launcher wskazuje nowy EXE. Build i smoke GUI oraz MCP przeszły; MCP zaliczył 10 ewaluacji i kontrolę pustego stderr. Sprawdzono obecność modułów klienta Garmin w archiwum EXE, metadane `0.3.20` i natywny moduł `curl_cffi`. Raporty: `test-results/auth-full.log`, `test-results/auth-build.log`, `test-results/auth-mcp-smoke/mcp-smoke.json`. Nie wykonywano rzeczywistego logowania ani pobierania historii i nie kasowano ponownie zapisanej sesji. Odbiór na koncie wymaga kolejnej próby użytkownika z nowej paczki; ewentualny kod diagnostyczny pozwoli zawęzić przyczynę bez ujawniania sekretów.
