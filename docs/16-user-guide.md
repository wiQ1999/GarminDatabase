# Instalacja i codzienna obsługa

## Windows — aplikacja

1. Przygotuj PostgreSQL 16+ zgodnie z [instrukcją bazy](13-postgresql-setup.md). Serwer jest instalowany osobno.
2. Wypakuj całą paczkę. Zachowaj sąsiadujące foldery `GarminDatabase`, `GarminDatabaseCollector` i `GarminDatabaseMCP`.
3. Uruchom `GarminDatabase/GarminDatabase.exe`. W Ustawieniach wpisz połączenie PostgreSQL bez hasła i początek pobierania, następnie „Zapisz ustawienia”. Hasło bazy umieść w pgpass.
4. Zaloguj Garmin, wybierając sesję aplikacji. „Pobierz nowe dane” uzupełnia archiwum, „Dane” pokazuje wykresy, „Eksport” tworzy JSON.

„Otwórz folder konfiguracji” otwiera lokalizację wspólnego `settings.json`. Interwał odświeżania stanu nie zmienia cyklu pobierania.

## Windows — kolektor

1. W Ustawieniach → Automatyczne pobieranie wybierz „Bieżące konto — bez hasła Windows”, cykl i początek harmonogramu. Konto jest wskazane automatycznie. Działa także przy blokadzie ekranu, gdy użytkownik pozostaje zalogowany; GUI może być zamknięte.
2. Używana jest istniejąca sesja Garmin aplikacji. Jeśli jej brak, zaloguj Garmin jak przy ręcznym pobieraniu.
3. Zaznacz „Włącz cykliczne pobieranie” i kliknij „Zainstaluj / zaktualizuj kolektor”. Nie podajesz hasła Windows ani nie tworzysz osobnego konta. Naprawa uprawnień starszego zadania może jednorazowo wymagać potwierdzenia UAC.
4. Zakładka „Kolektor” pokazuje stan, następny termin i log. Instalacja nie wykonuje pobrania natychmiast. Nazwa zadania `GarminDatabase-default` oznacza domyślną instancję; ponowna instalacja aktualizuje tę samą instancję.

Równoważna instalacja z terminala (wstaw własne ścieżki):

```powershell
$collector = 'C:\Apps\GarminDatabaseCollector\GarminDatabaseCollector.exe'
$config = "$env:LOCALAPPDATA\GarminDatabase\settings.json"
& $collector --config $config install --logon interactive --interval 120 --enable
& $collector --config $config status --json
& $collector --config $config logs
```

`install` tworzy brakującą sekcję kolektora, zachowuje pozostałe ustawienia i przygotowuje harmonogram, także dla własnej nazwy pliku podanej przez `--config`. Przy instalacji samego kolektora bez sesji GUI wykonaj również `login` na bieżącym koncie.

Praca po wylogowaniu jest opcjonalna: wybierz drugi tryb i istniejące konto z hasłem albo użyj `install --logon password --account 'KOMPUTER\konto'`. Konto potrzebuje własnego pgpass, dostępu do paczki i osobnej sesji Garmin. Dla bieżącego konta wybierz sesję kolektora w formularzu Garmin. Dla innego konta uruchom `runas /user:KOMPUTER\konto powershell.exe` i w jego terminalu wykonaj `$collector --config $config login`. Hasła wpisuj wyłącznie w lokalnych monitach. PIN/Hello nie zastępuje hasła tego trybu. Zmiana konta lub trybu zachowuje poprzednie pliki sesji.

## Linux / Raspberry Pi OS

Potrzebne: system 64-bit, Python 3.12+, systemd 250+, dostęp do PostgreSQL 16+. Utwórz zwykłe konto `garmin-collector` z katalogiem domowym; hasło logowania tego konta nie jest potrzebne systemd.

W katalogu źródeł:

```sh
sudo python3.12 -m venv /opt/garmin-database/.venv
sudo /opt/garmin-database/.venv/bin/pip install '.[collector,mcp]'
sudo /opt/garmin-database/.venv/bin/garmin-db-collector init
```

W `/etc/garmin-database/settings.json` ustaw połączenie, `download_from`, bezwzględny `data_dir` i sekcję kolektora. Przygotuj `.pgpass` konta kolektora (tryb `0600`). Następnie:

```sh
sudo /opt/garmin-database/.venv/bin/garmin-db-collector install --account garmin-collector
sudo systemd-run --wait --collect --pty \
  --property=User=garmin-collector \
  --property=LoadCredentialEncrypted=garmin-session-key:/etc/garmin-database/session-key.cred \
  /opt/garmin-database/.venv/bin/garmin-db-collector login
sudo /opt/garmin-database/.venv/bin/garmin-db-collector schedule enable
```

Instalacja przygotowuje zaszyfrowany klucz, usługę jednorazową i timer; nie wymaga graficznego pulpitu. Więcej: [kolektor](15-scheduled-collector.md).

## MCP dla agenta AI

W Ustawieniach włącz MCP, zaznacz udostępniane parametry i zapisz ustawienia. „Kopiuj konfigurację MCP” tworzy konfigurację klienta z właściwą ścieżką programu oraz `settings.json`. Wklej ją do klienta MCP. Klient sam uruchamia proces `GarminDatabaseMCP.exe` przez stdio; nie uruchamiaj serwera HTTP. Linux: `garmin-db-mcp --settings-file /etc/garmin-database/settings.json`.

MCP ma dostęp tylko do odczytu. `get_samples` pokazuje szczegóły dnia, `get_history` średnie dzienne/miesięczne, `get_period_stats` podsumowanie zakresu, a `get_source_history` gotowe wyniki snu, nocnego HRV i inne wartości źródłowe. Nie sumuj skumulowanych liczników i nie traktuj ocen snu jako czasu faz. Agent rozpoczyna od `garmin_catalog`, a następnie wybiera narzędzie wskazane w katalogu. Wyłączenie udostępniania działa także dla już uruchomionego MCP.

## Polecenia

`garmin-db` używa zapisanej daty początku pobierania. Eksport dziedziczy zapisany zakres historii, liczbę dni szczegółów i okres podsumowań. Opcje `--from`, `--to`, `--recent-days` i `--summary-period` nadpisują odpowiednie wartości dla danego wywołania.

| Program | Polecenia |
| --- | --- |
| `garmin-db` (pakiet Python) | `status`, `sync`, `sync-all`, `import-local`, `reprocess`, `export`; opcje przez `--help` |
| `GarminDatabaseCollector.exe` / `garmin-db-collector` | `init`, `install`, `login`, `run`, `status --json`, `logs`, `schedule install/apply/enable/disable/status`, Linux: `prepare-key` |
| `GarminDatabaseMCP.exe` / `garmin-db-mcp` | `--settings-file ŚCIEŻKA`; protokół stdio obsługuje klient MCP |

Globalne `--config ŚCIEŻKA` kolektora podawaj przed poleceniem. `run` wykonuje ręczne pobranie; `run --scheduled` respektuje termin i włączenie harmonogramu. `schedule disable` zatrzymuje przyszłe uruchomienia. Kody kolektora: `0` sukces/pominięcie, `2` problemy/pauza, `1` błąd konfiguracji lub polecenia. Hasła Garmin, MFA i bazy nie należą do argumentów ani JSON.

Porównywanie danych z zapisanym HTML Garmin: [zasady i polecenie weryfikacji](02-source-validation.md#porównanie-garmin-connect-bazy-wykresu-i-mcp). Dane aplikacji pochodzą z FIT; średnia próbek nie zawsze odpowiada statystyce widocznej w Garmin Connect.
