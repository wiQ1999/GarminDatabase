# GarminDatabase — pamięć implementacji

- Projekt roboczy: `D:/Projects/GarminDatabase`; wcześniejszy katalog C: nie jest głównym checkoutem.
- Python 3.12, SQLite STRICT/JSON1. Zachowujemy fizyczne pola FIT raz, oryginalne ZIP bez zmian i wersjonowaną semantykę publicznego profilu. Nie zgadujemy prywatnych metryk.
- Pierwszy produkt: polskie UI Windows 11, PySide6 Essentials/Qt Widgets, własny wykres QPainter, dystrybucja PyInstaller onedir bez konsoli. Rdzeń nie importuje Qt.
- UI: Start/Dane/Eksport/Ustawienia; ciemny motyw. „Pobierz dane” pobiera tylko do wczoraj Europe/Warsaw i importuje. Szczegóły wykresu tylko dla dnia; dłuższe okresy tylko podsumowania Garmin. Zero własnych agregatów zdrowotnych.
- Sesja: DPAPI użytkownika, `%LOCALAPPDATA%/GarminDatabase/auth/session.bin`, bez hasła/MFA. Ustawienia JSON obok. Nie logować surowych wyjątków Garmin, tokenów ani pomiarów.
- Dane, eksporty, logi, build/dist i raporty testów są ignorowane w Git. Testy używają syntetycznych FIT/ZIP, nigdy prywatnych fixture.
- Testy: `.venv/Scripts/python.exe -m pytest`; piramida: wiele jednostkowych, mniej integracyjnych, kilka UI/smoke. Realne archiwa sprawdzamy lokalnie, raportując wyłącznie liczniki i błędy.
- Import jest idempotentny i transakcyjny; równoległy odczyt przez WAL, jeden writer chroniony blokadą OS; stop wycofuje nieukończony FIT. Nie nadpisywać oryginalnych archiwów.
- `Importer` czyta FIT strumieniowo z ZIP, zapisuje raw_value i cache opisów zależny od referencji subpola. Błędy CRC wycofują cały FIT. `Queries` nie mnoży rekordów przez wystąpienia FIT w różnych ZIP. Czasy skrócone rekonstruowane wyłącznie z kontekstu FIT.
- Nieznany czas pozostaje NULL; źródłowy dzień żądania jest osobnym metadanym, również w eksporcie. Nietimestampowane podsumowania mogą być rysowane z wyraźnym podpisem dnia archiwum.
- Eksport strumieniowy, atomowy per plik, z `.garmin-export.json` ewidencjonującym własność wyników. Obce pliki nie są nadpisywane ani usuwane.
- Pułapka pakowania w tym środowisku: ICU 78 z runtime Pythona na PATH ma eksporty z sufiksem `_78`, a Qt 6.12 wymaga niesufiksowanego ICU systemu Windows 11. Skrypt build usuwa błędnie zebrane `icuuc.dll`/`icudt78.dll` z root `_internal`. Testować zbudowany EXE, nie tylko kod Python.
- Cache opisów FIT musi używać współrzędnych semantycznych (globalna wiadomość, pole, namespace/indeks, typ, wariant i referencje subpola), nigdy `id(field_def)`: Python odzyskuje adresy obiektów po redefinicjach lokalnych. Regresja: test 300 redefinicji; walidacja pełnej bazy porównuje `field_catalog.message_num/field_num` z fizycznymi definicjami.
- Docelowe polecenia: `scripts/run_tests.ps1` (coverage rdzenia i CLI, z gałęziami, próg 85%) oraz `scripts/build_windows.ps1`. Testy GUI są osobną warstwą, bez sztucznego wliczania frameworka Qt do coverage rdzenia.
- Po większych etapach Conventional Commits, jawne listy plików w staging, bez pytania — użytkownik zatwierdził taki workflow. Push nie jest automatycznie częścią kolejnych zleceń.
- Raspberry Pi: późniejszy automat/hub bez UI. Protokół dostępu i ochrona sesji Linux wymagają osobnego projektu.

Migracja 002 podnosi `user_version` do 2. Indeks `fit_fields(field_definition_id, message_definition_id)` jest konieczny dla wydajnego sprawdzania klucza obcego podczas zastępowania dekodowania. Bez niego pojedyncza wymiana FIT skanuje miliony pól. Pliki SQL w `schema/` i `garmin_database/resources/` muszą mieć identyczną treść, aby kod i paczka wykonywały te same migracje.

Metadane kompletności eksportu muszą używać tego samego połączenia i transakcji odczytu co wartości; nowe połączenie mogłoby opisać stan importu nowszy niż eksportowane dane. Regresję sprawdza test z równoległym zatwierdzeniem zapisu w trybie WAL.

Ponowienia błędów przejściowych respektują `Retry-After` w sekundach i formacie daty HTTP. 401/403/429 nadal zatrzymują pobieranie, zamiast uruchamiać kolejną próbę. Oczekiwanie korzysta z `Event.wait`, dzięki czemu użytkownik może je zatrzymać.

Odbiór 2026-10-11: 139 testów (102 jednostkowe, 32 integracyjne, 5 UI), 92,36% coverage rdzenia i CLI z gałęziami. Pełna baza: 844 ZIP, 10 994 ukończone FIT, 8 307 429 wiadomości, 20 841 953 pola, 737 nieznanych wariantów; 56 serii/właściwości w UI. SQLite quick_check, klucze obce, kontekst katalogu i hashe oryginalnych ZIP — poprawne. Nie utrzymywać dodatkowych kopii prywatnych danych utworzonych do testów.

## Dokumentacja procesu

Użytkowanie, budowanie paczki, piramida testów i odbiór rzeczywistej historii są w [docs/12-running-and-testing.md](docs/12-running-and-testing.md). Punktem wejścia dystrybucji jest `desktop.py`; operacje bez okna korzystają z `garmin_database/cli.py`. Specyfikacja UI pozostaje w `docs/11-desktop-ui.md`, a model danych i migracje opisuje `docs/10-sqlite-schema.md`.
