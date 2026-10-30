# Uruchamianie aplikacji, build i testy

Aplikacja Windows i rdzeń bez UI używają wyłącznie PostgreSQL 16+. Ten sam typ bazy obowiązuje lokalnie i na serwerze. Najpierw [zainstaluj PostgreSQL, utwórz bazę i skonfiguruj połączenie](13-postgresql-setup.md). Python: 3.12 lub nowszy, zależności: `requirements-dev.txt` dla dewelopera, `requirements-app.txt` dla aplikacji.

## Uruchomienie

Projekt ma układ `src/`. Przed uruchomieniem źródeł, testów lub budowania zainstaluj pakiet w środowisku: `python -m pip install -e '.[desktop,mcp,collector]'` (albo odpowiednik uv dla wybranego interpretera). Samo dodanie katalogu projektu do `PYTHONPATH` nie zastępuje instalacji. Punkty wejścia to `garmin-database`, `garmin-db`, `garmin-db-mcp` i `garmin-db-collector`; działają także moduły `garmin_database.bootstrap.desktop`, `.cli`, `.mcp` i `.collector`. Sam kolektor wymaga dodatku `[collector]`, bez Qt/MCP, lub `requirements-collector.txt` i instalacji pakietu.

Windows: `.venv/Scripts/python.exe -m garmin_database` lub `dist/GarminDatabase/GarminDatabase.exe` po standardowym buildzie. Ścieżka paczki przy własnym `--destination` ma ten sam układ we wskazanym folderze. Zachowaj cały folder dystrybucji z `_internal`. PostgreSQL działa niezależnie od EXE. Hasło PostgreSQL pobierane jest z pgpass lub środowiska, a hasło Garmin służy wyłącznie logowaniu i nie jest zapisywane. GUI i kolektor Windows używają DPAPI właściwego konta. [Kolektor Linux/Pi](15-scheduled-collector.md) ma szyfrowany magazyn z kluczem systemd.

1. W Ustawieniach sprawdź folder archiwów i połączenie PostgreSQL. Nie podawaj hasła w polu połączenia; ustawienia je odrzucą.
2. Zaloguj się do Garmin, jeśli chcesz pobierać nowe dni. Import lokalnych ZIP nie wymaga sesji.
3. „Pobierz nowe dane” odświeża ostatni pobrany dzień i nadrabia dane do dzisiaj Europe/Warsaw wraz z wcześniejszymi nieukończonymi importami. „Pobierz wszystko” pobiera cały zakres. Nowe ZIP nie są zapisywane na dysku; FIT są deduplikowane po SHA-256 w SQL.
4. Dane pokazują szczegóły dnia, źródłowe podsumowania Garmin lub oznaczone średnie pięciu obsługiwanych parametrów. Wykres odświeża się automatycznie. Trend jest wyłącznie warstwą prezentacji.
5. Eksport tworzy nowy folder z historią podsumowań, szczegółami i manifestem. Zachowuje wcześniejsze pakiety.

## Testy

Skonfiguruj `GARMIN_TEST_DATABASE_DSN` na osobną bazę testową PostgreSQL. Fixture tworzą osobny schemat per test i usuwają go po zakończeniu. Korzystają tylko z syntetycznych FIT/ZIP. Nie ma zamiennika SQLite ani pomijania testów z powodu braku serwera.

Windows PowerShell:

```powershell
uv pip install --cache-dir .uv-cache --python .venv/Scripts/python.exe -r requirements-dev.txt -e .
$env:GARMIN_TEST_DATABASE_DSN = 'host=localhost port=5432 dbname=garmin_tests user=garmin_test'
powershell -NoProfile -File scripts/run_tests.ps1
```

Linux/Raspberry Pi OS:

```sh
uv pip install --cache-dir .uv-cache --python .venv/bin/python -r requirements-dev.txt -e .
export GARMIN_TEST_DATABASE_DSN='host=localhost port=5432 dbname=garmin_tests user=garmin_test'
.venv/bin/python scripts/run_tests.py
```

`run_tests.py` jest wspólnym runnerem; PowerShell wywołuje ten sam kod. Wymaga co najmniej 85% coverage rdzenia i CLI z gałęziami. Raporty: `test-results/results.xml` i `test-results/coverage/index.html`. Qt/rysowanie/UI mają osobne testy i nie są wliczane do progu coverage.

| Warstwa | Zakres |
| --- | --- |
| Architektury | Kierunek importów między warstwami, brak bibliotek dostawców w rdzeniu i niezależny proces MCP |
| Jednostkowe | Typy FIT, precyzja, timestampy, strefa/DST, reguły podsumowań, HTTP, ustawienia i odrzucanie haseł w DSN |
| Integracyjne | Prawdziwy PostgreSQL, DDL i ograniczenia, atomowe migracje i SHA, import/rollback/CRC, idempotencja, advisory lock między katalogami, spójne snapshoty, cache i anulowanie, eksport i kursory serwerowe, brak fallbacku przy niedostępnej bazie |
| UI | Nawigacja, zakresy i daty, spinner, nieaktualne odpowiedzi, trend, eksport, ustawienia PostgreSQL, zatrzymanie, MFA |

Testy prawdziwego Windows DPAPI są pomijane na innych systemach, z jawnym powodem; muszą zostać uruchomione na Windows. Testy specyficznych uprawnień Linux/systemd mają odpowiednie oznaczenie platformy. Sam backend PostgreSQL nie wymaga Windows. Testy protokołu MCP sprawdzają także dostępność transportu, politykę udostępniania, limity i anulowanie. Coverage używa `source_pkgs` dla pakietu `garmin_database`, aby katalog o tej samej nazwie poza `src/` nie przesłaniał źródeł.

Kontrola statyczna:

Testy `tests/ui/test_responsiveness.py` zatrzymują odczyt stanu, zapis, przygotowanie eksportu i otwieranie zasobów na barierach w tle. Sprawdzają obsługę zdarzeń Qt, ruch wskaźnika, nawigację, brak kolejki powtórzonych odświeżeń, cykle odczytu i zamknięcie bez `wait()` w wątku GUI. Regresje obejmują publikację liczników przed wolnym katalogiem, zachowanie stanu przy błędzie katalogu, odstęp ponowień i zastępowanie komunikatów także przed pierwszym poprawnym odczytem. Dziennik sprawdzany jest przed operacją, podczas jej trwania i po zakończeniu, z limitem 500 wierszy oraz bez przycisku szczegółów. Testy PostgreSQL sprawdzają snapshoty i anulowanie rzeczywistego `pg_sleep` przez deadline i Event. `test_catalog_query.py` weryfikuje katalog z wieloma nieobserwowanymi wariantami w ograniczonym czasie SQL oraz źródła interpretacji, brak duplikatów i odrzucenie nieaktywnych dekodowań. Używają wyłącznie osobnej bazy testowej i syntetycznych archiwów.

```sh
python -m ruff check src tests scripts/entrypoints scripts/build.py scripts/run_tests.py scripts/smoke.py
python -m ruff format --check src tests scripts/entrypoints scripts/build.py scripts/run_tests.py scripts/smoke.py
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

`smoke.py` uruchamia zbudowaną aplikację w oddzielnym schemacie bazy testowej. Przygotowuje dwa syntetyczne ZIP po 600 wiadomości, zleca EXE import lokalny i wznowienie, sprawdza 1200 wiadomości/4800 pól oraz brak dodatkowych decode_runs, zapisuje zrzut okna i usuwa schemat także po błędzie. Przed zrzutem EXE czeka na poprawny pierwszy stan i katalog, brak komunikatu błędu oraz zakończenie odczytu wykresu, potwierdzając gotowość osobnym plikiem `.ui.json`; błąd lub przekroczenie czasu kończy smoke niepowodzeniem. Sprawdza więc rzeczywisty importer partii/COPY i asynchroniczny start GUI w paczce. Nie używa ustawień ani bazy użytkownika. Przyjmuje opcjonalną ścieżkę do programu. Windows EXE wymaga buildu i uruchomienia na Windows; wynik paczki Linux tego nie zastępuje.

Pakiet Pythona można zbudować poleceniem `uv build --python .venv/Scripts/python.exe --out-dir dist/python`; zarówno wheel, jak i sdist muszą zawierać migracje `garmin_database/resources/*.sql` wewnątrz pakietu.

### Zasoby TLS i kryteria paczki

Build dołącza SQL, zasoby UI, ikonę, biblioteki psycopg/libpq i dane stref czasowych. Jeśli używany runtime Pythona dostarcza sąsiedni plik `codex-rejected-cas.pem`, skrypt pakuje go obok modułu `ssl` w obu EXE; standardowy Python nie wymaga tego zasobu. Zachować politykę certyfikatów i weryfikację TLS.

Smoke GUI tworzy rzeczywisty kontekst TLS przed otwarciem okna, a następnie sprawdza uruchomienie na syntetycznej bazie. Sam import bibliotek lub pojawienie się okna nie wystarcza. Testy SDK z atrapą transportu nie zastępują tej kontroli. Rzeczywiste logowanie do konta i pobieranie historii są osobnymi czynnościami odbiorowymi, wykonywanymi przez użytkownika.

Raporty testów, coverage, wyniki smoke i notatki odbioru pozostają w ignorowanych `test-results/` lub `local-notes/`. W dokumentacji utrzymuje się procedurę i wymagania, nie historię kolejnych wyników.

## Pomiar wydajności importu

`scripts/benchmark_import.py` porównuje aktualny importer z zaufaną rewizją Git w osobnych, usuwanych schematach bazy wskazanej przez `GARMIN_TEST_DATABASE_DSN`. Wymaga zainstalowanego pakietu, zależności deweloperskich i dostępnej historii Git. Rewizja musi zawierać zgodny importer PostgreSQL i używać tej samej semantyki FIT; nie porównywać w ten sposób różnych silników lub algorytmów interpretacji.

```powershell
.venv/Scripts/python.exe scripts/benchmark_import.py --baseline-ref 210dfa6 --messages 3000 12000 --repeats 3 --min-speedup 2
```

Pomiary obejmują pełny import dwóch syntetycznych ZIP: blokadę, rejestrację, dekodowanie, zapis i commity. Tworzenie schematu, generowanie źródeł i późniejsze porównanie danych pozostają poza czasem. Każdy wariant wykonuje się co najmniej trzy razy, naprzemiennie, w świeżym schemacie. Porównuje się mediany dla obu rozmiarów; kod wyjścia jest niezerowy, jeśli którykolwiek wynik nie osiąga zadanego progu lub zmieniły się dane.

Fingerprint porównuje wszystkie zachowane wartości, typy, ważność, definicje, indeksy, czasy i metadane profilu, po kluczach źródłowych zamiast technicznych ID. Sama liczność rekordów nie wystarcza. Wynik trafia do ignorowanego `test-results/import-benchmark.json`. Pomiar wykonywać bez równoległych testów, buildu i innych obciążeń; używa wyłącznie syntetycznych danych. Nie uruchamiać go na bazie aplikacji ani prywatnych fixture.

Próg 2× w tym odbiorze dotyczy pełnego importu lokalnego w porównywalnym środowisku. Nie oznacza dwukrotnie szybszej odpowiedzi serwera Garmin ani gwarancji dla każdego pojedynczego małego FIT. Nakładanie HTTP na import ma odrębne testy synchronizacji z barierami zdarzeń: jeden request naraz, najwyżej jeden dzień wyprzedzenia, zachowana kolejność SQL, zatrzymanie po 401/403/429, Retry-After, anulowanie i wznowienie. Testy partii obejmują późne CRC, anulowanie po flush, reprocess, odwróconą kolejność RETURNING, tablice/null/UTF-8/uint64 i poprawną kompletność dnia.

## Operacje bez UI

```sh
python -m garmin_database.bootstrap.cli status --data-dir data
python -m garmin_database.bootstrap.cli import-local --data-dir data
python -m garmin_database.bootstrap.cli reprocess --data-dir data --from 2026-09-01
python -m garmin_database.bootstrap.cli export --data-dir data --parameters monitoring.heart_rate --from 2026-09-01 --to 2026-09-30 --recent-days 30 --summary-period day --output exports
```

CLI i UI czytają ten sam `database_dsn`, `GARMIN_DATABASE_DSN` i konfigurację libpq. Opcjonalne `--settings-file` wskazuje osobne ustawienia. Dotychczasowy `garmin-db sync` używa sesji GUI Windows. Do sieciowego pobierania na Linux/Pi służy `garmin-db-collector` z oddzielną konfiguracją i sesją, opisany w [instrukcji kolektora](15-scheduled-collector.md).

## Wznowienie i utrzymanie

Ponowne odwiedzenie kompletnego ZIP nie tworzy fikcyjnego przebiegu importu. Wymuszona wymiana FIT zachowuje poprzedni wynik po błędzie lub anulowaniu. PostgreSQL MVCC i odczyt `REPEATABLE READ READ ONLY` zapewniają spójność eksportu podczas nowego importu. Cache nie publikuje nieaktualnego wyniku i nie blokuje eksportu, gdy writer jest zajęty.

Rozmiar w Start to `pg_database_size` całej wskazanej bazy. MVCC może pozostawiać martwe wersje wierszy; utrzymaniem zajmuje się PostgreSQL autovacuum. Aplikacja nie wykonuje automatycznie `VACUUM FULL`. Długie eksporty utrzymują snapshot do końca operacji; nie pozostawiaj otwartych transakcji bez potrzeby.

Odbiór danych rzeczywistych jest oddzielny od testów syntetycznych. Nie zastępuj walidacji importu PostgreSQL wynikiem uzyskanym na innym silniku ani samą próbą logowania.

## Lokalny MCP — konfiguracja i uruchomienie

Budowanie tworzy trzy sąsiednie foldery: `GarminDatabase/` z okienkowym EXE, `GarminDatabaseMCP/` z serwerem stdio i `GarminDatabaseCollector/` z kolektorem. Zachowaj foldery wraz z ich `_internal`. `build_windows.ps1 -Destination ...` buduje wszystkie we wskazanym miejscu. `build.py --only collector` działa w środowisku bez Qt/MCP. Nie zatrzymuj wcześniejszej aplikacji użytkownika w celu nadpisania plików.

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
      "args": ["--settings-file", "C:/Users/UZYTKOWNIK/AppData/Local/GarminDatabase/settings.json"]
    }
  }
}
```

W źródłach odpowiednikiem jest `.venv/Scripts/python.exe scripts/entrypoints/mcp_stdio.py --settings-file ŚCIEŻKA`. Serwer czeka na protokół na standardowym wejściu; nie jest interaktywną konsolą. Konfiguracja z UI wskazuje bezwzględny `bootstrap/mcp.py` wewnątrz zainstalowanego pakietu i działa również z innego katalogu. Dla instalacji pakietu dostępne jest `garmin-db-mcp`.

### Narzędzia MCP v1

| Narzędzie | Argumenty | Wynik |
| --- | --- | --- |
| `garmin_catalog` | opcjonalny `cursor`; katalog v1 mieści pięć metryk w jednej odpowiedzi | Włączone metryki, etykiety, jednostki, dostępny zakres rozpoznanych czasów, precyzja, limity i objaśnienie pomiaru ze źródłami Garmin |
| `get_daily` | `date_from`, `date_to`, wymagane `metrics`, opcjonalny `cursor` | Dzienne średnie, min/max, liczniki jakości i pierwszy/ostatni czas; do 92 dni na stronę; objaśnienie każdej metryki |
| `get_period_stats` | `date_from`, `date_to`, wymagane `metrics` | Jeden wiersz całego okresu na metrykę, średnia ważona próbkami, min/max, liczby próbek i dni; objaśnienie każdej metryki |

Wymagany jest wybór 1–5 różnych kluczy z katalogu: `monitoring.heart_rate`, `hrv_value.value`, `respiration_rate.respiration_rate`, `spo2_data.reading_spo2`, `stress_level.stress_level_value`, jeśli są obecne i włączone. Są to średnie próbek dni, bez zgadywania znaczenia nocnego HRV czy tętna spoczynkowego. Zakres katalogu nie gwarantuje ciągłości ani pełnego pokrycia doby.

Przykładowe argumenty metod odczytu:

```json
{"date_from":"2026-09-01","date_to":"2026-09-30","metrics":["monitoring.heart_rate","hrv_value.value"]}
```

Zakres obejmuje obie daty w Warszawie i kończy się najpóźniej dzisiaj. Wynik jest w `structuredContent.series`; seria podaje `parameter`, `unit`, `description`, `aggregation`, `precision`, `columns` i tablicę wierszy `data`. Krótka część tekstowa nie powiela JSON. Czas jest lokalny z pełną datą i offsetem, np. `2026-10-22T13:30:00+02:00`. Dni zmiany czasu mają rzeczywiste granice 23/25 godzin; PostgreSQL i eksport v2 zachowują momenty UTC.

`description` występuje zarówno w `metrics[]` katalogu, jak i `series[]` obu metod odczytu. Ma `version`, `language`, `reviewed_on`, `meaning`, `measurement`, `limitations`, `presentation`, `evidence` i `sources[]` (`title`, `url`). To lokalnie przechowywana polska parafraza publicznych materiałów Garmin, a nie tekst pobierany z internetu podczas zapytania. `manufacturer_explanation` oznacza opis funkcji przez producenta; `fit_profile_only` ograniczony opis pola; `not_documented` brak zweryfikowanej interpretacji. Wersja opisu jest niezależna od rewizji danych i algorytmu agregacji. Dodanie tego pola jest rozszerzeniem odpowiedzi v1 i nie zmienia wartości ani kolumn. [Katalog objaśnień i zasady porównania z Garmin Connect](14-parameter-descriptions.md).

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

Proces MCP używa istniejących strumieni stdin/stdout z UTF-8. Nie należy tworzyć dodatkowych `TextIOWrapper` na współdzielonych buforach; standardowe wyjście służy wyłącznie protokołowi.
