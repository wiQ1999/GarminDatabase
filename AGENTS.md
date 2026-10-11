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
- Po większych etapach Conventional Commits, jawne listy plików w staging, bez pytania — użytkownik zatwierdził taki workflow. Push nie jest automatycznie częścią kolejnych zleceń.
- Raspberry Pi: późniejszy automat/hub bez UI. Protokół dostępu i ochrona sesji Linux wymagają osobnego projektu.
