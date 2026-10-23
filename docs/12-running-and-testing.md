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
