# Instalacja i codzienna obsługa

## Windows — aplikacja

1. Przygotuj PostgreSQL 16+ zgodnie z [instrukcją bazy](13-postgresql-setup.md). Serwer jest instalowany osobno.
2. Wypakuj całą paczkę. Zachowaj sąsiadujące foldery `GarminDatabase`, `GarminDatabaseCollector` i `GarminDatabaseMCP`.
3. Uruchom `GarminDatabase/GarminDatabase.exe`. W Ustawieniach wpisz połączenie PostgreSQL bez hasła i początek pobierania, następnie „Zapisz ustawienia”. Hasło bazy umieść w pgpass.
4. Zaloguj Garmin, wybierając sesję aplikacji. „Pobierz nowe dane” uzupełnia archiwum, „Dane” pokazuje wykresy, „Eksport” tworzy JSON.

„Otwórz folder konfiguracji” otwiera lokalizację wspólnego `settings.json`. Interwał odświeżania stanu nie zmienia cyklu pobierania.

## Windows — kolektor

1. W Ustawieniach → Automatyczne pobieranie wybierz konto, cykl i początek harmonogramu. Domyślnie jest to aktualne konto Windows. Konto musi już istnieć i mieć hasło; PIN/Hello nie wystarcza.
2. Kliknij „Zainstaluj / zaktualizuj kolektor”. Przycisk zapisuje formularz, przygotowuje uprawnienia i rejestruje zadanie. Potwierdź UAC oraz hasło konta Windows. Nie wpisuj tutaj hasła Garmin.
3. Dla aktualnego konta Windows w formularzu logowania Garmin wybierz „Kolektor — aktualne konto Windows” i zaloguj się. Sesja kolektora jest niezależna od sesji aplikacji. Dla innego konta uruchom terminal przez `runas /user:KOMPUTER\konto powershell.exe`, a w nim polecenie `login` poniżej. Konto potrzebuje własnego pgpass i dostępu do paczki.
4. Włącz „Włącz cykliczne pobieranie” i ponownie zainstaluj/zaktualizuj kolektor. Zakładka „Kolektor” pokazuje stan, terminy i log. Przycisk instalacji nie wykonuje pobrania; automat czeka na następny termin.

Równoważna instalacja z terminala (wstaw własne ścieżki i konto):

```powershell
$collector = 'C:\Apps\GarminDatabaseCollector\GarminDatabaseCollector.exe'
$config = "$env:LOCALAPPDATA\GarminDatabase\settings.json"
& $collector --config $config install --account 'KOMPUTER\konto' --interval 120
& $collector --config $config login
& $collector --config $config schedule enable
& $collector --config $config status --json
& $collector --config $config logs
```

`login` wykonuj jako konto zadania, wskazując pełną ścieżkę wspólnego pliku operatora. `install` tworzy brakującą sekcję kolektora, zachowuje pozostałe ustawienia i przygotowuje harmonogram. Zmiana konta wymaga przygotowania jego sesji i dostępu do bazy.

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

| Program | Polecenia |
| --- | --- |
| `garmin-db` (pakiet Python) | `status`, `sync`, `sync-all`, `import-local`, `reprocess`, `export`; opcje przez `--help` |
| `GarminDatabaseCollector.exe` / `garmin-db-collector` | `init`, `install`, `login`, `run`, `status --json`, `logs`, `schedule install/apply/enable/disable/status`, Linux: `prepare-key` |
| `GarminDatabaseMCP.exe` / `garmin-db-mcp` | `--settings-file ŚCIEŻKA`; protokół stdio obsługuje klient MCP |

Globalne `--config ŚCIEŻKA` kolektora podawaj przed poleceniem. `run` wykonuje ręczne pobranie; `run --scheduled` respektuje termin i włączenie harmonogramu. `schedule disable` zatrzymuje przyszłe uruchomienia. Kody kolektora: `0` sukces/pominięcie, `2` problemy/pauza, `1` błąd konfiguracji lub polecenia. Hasła Garmin, MFA i bazy nie należą do argumentów ani JSON.
