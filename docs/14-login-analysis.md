# Analiza problemu logowania Garmin — 2026-10-24

Użytkownik potwierdził poprawne logowanie w produkcyjnej paczce `dist/tls-fix`. Przyczyną awarii był brak zasobu wymaganego przez runtime TLS Pythona w EXE. Poniższe ustalenia wynikają z porównania zachowanych paczek i kontrolowanego odtworzenia błędu; nie są hipotezą o danych konta.

## Co dokładnie nie działało

Logowanie składa się z kilku kroków, a sukces MFA nie kończy całego procesu:

1. Garmin sprawdza login i hasło, a aplikacja otrzymuje żądanie MFA.
2. Garmin przyjmuje nowy kod MFA — zarejestrowano `SUCCESSFUL` i HTTP 200.
3. Biblioteka wymienia potwierdzenie SSO na token aplikacji — HTTP 200.
4. Aplikacja pobiera profil i ustawienia, aby potwierdzić dostęp i przygotować klienta.
5. Dopiero po zakończeniu tych kroków zapisuje sesję w DPAPI.

W wadliwym EXE problem pojawiał się w kroku 4. Połączenia SSO i wymiany tokenu korzystały z `curl_cffi`, natomiast odczyt API korzystał z `requests` i modułu `ssl` Pythona. Ten drugi transport nie mógł utworzyć kontekstu TLS, więc żądanie profilu nie docierało do Garmin.

## Przyczyna techniczna

Używany zarządzany runtime Pythona zawiera modyfikację `ssl.SSLContext.__new__`, która wczytuje sąsiedni publiczny plik polityki certyfikatów `codex-rejected-cas.pem`. PyInstaller spakował zmodyfikowany `ssl.py`, ale nie dołączył pliku PEM.

Próba utworzenia kontekstu TLS kończyła się `FileNotFoundError`. Błąd przechodził przez transport jako `ProtocolError` i `ConnectionError`, po czym biblioteka Garmin opakowywała nieudane pobranie profilu w `GarminConnectAuthenticationError`. UI otrzymywał więc typ sugerujący odmowę uwierzytelnienia, mimo że hasło i MFA zostały już przyjęte.

Również wynik pomocniczej weryfikacji tokenu wymagał ostrożnej interpretacji: SDK dopuszcza kontynuację przy nierozstrzygniętym błędzie transportu. Sam znacznik `API_VERIFY:OK` nie dowodził udanego żądania. Potwierdzeniem dostępu były dopiero odpowiedzi HTTP 200 z profilu i ustawień.

## Dowód i różnica względem pierwszych wersji

Ta sama sesja DPAPI pozwalała pobrać profil w Pythonie, ale w EXE powtarzalnie kończyła się brakiem pliku w konstruktorze TLS. Do tej samej kopii EXE dołączono wyłącznie brakujący PEM. Bez zmiany kodu, tokenu i bez nowego MFA profil oraz ustawienia zwróciły HTTP 200.

Starsze zachowane paczki `dist/GarminDatabase` i `dist/summary-export` zawierały standardowy moduł `ssl`, bez wymagania tego zasobu. Nowsze paczki od `dist/postgresql-release` miały już zmieniony moduł i brakujący plik. Dlatego pierwsze wersje mogły działać, a późniejsze nie, mimo podobnego kodu logowania.

Nie potwierdzono związku tej awarii z cache, hasłem, kodem MFA ani PostgreSQL. Ręczne logowanie tworzy nowego klienta i jawnie pomija zapisane tokeny. Wcześniejsza aktualizacja `garminconnect` naprawiała osobny problem przygotowania sesji mobilnej, ale nie usuwała braku zasobu TLS. Także wcześniejszy błąd ponawiania MFA, naprawiony przez zerowanie stanu oczekiwania na kod, był oddzielnym problemem i nie wyjaśniał tej odmowy po poprawnym MFA.

## Co naprawiono i dlaczego testy wcześniej przepuszczały EXE

Build warunkowo pakuje wymagany PEM obok modułu runtime dla GUI i MCP. Standardowy Python, który tego pliku nie dostarcza, nie otrzymuje dodatkowego argumentu. Zachowano politykę certyfikatów i weryfikację TLS.

Testy transportu z atrapami nie tworzyły prawdziwego kontekstu TLS, a początkowy smoke EXE sprawdzał uruchomienie Qt i PostgreSQL. Sama obecność modułów, DLL i metadanych również nie uruchamiała konstruktora SSL. To był brakujący element odbioru paczki.

Obecny smoke tworzy rzeczywisty kontekst TLS. Kontrola negatywna potwierdziła, że brak PEM powoduje odrzucenie paczki, a jego przywrócenie pozwala zaliczyć smoke. `LoginFailed` rozpoznaje brak lokalnego pliku w łańcuchu błędów i pokazuje `LOCAL_RUNTIME`, zamiast sugerować błędne dane konta. Zaliczone wcześniej 291 testów, coverage 94,23%, build i smoke obu EXE dokumentuje [odbiór poprawki](12-running-and-testing.md#potwierdzona-przyczyna-i-poprawka-pakowania-tls--2026-10-24). Następnie użytkownik potwierdził udane logowanie w normalnej aplikacji.

## Przegląd kodu po zakończeniu diagnozy

Usunięto starą obsługę MFA z `Window.mfa` i jej połączenie z workerem importu/eksportu. Tę rolę od modernizacji ustawień pełni wyłącznie `LoginDialog`; stara ścieżka była utrzymywana już tylko przez test dawnego rozwiązania. Usunięto również ten test, zachowując testy właściwego dialogu, kolejnych kodów, anulowania i ponawiania logowania.

Usunięto też wyszukiwanie nazw wyjątków Garmin w treści komunikatu dialogu. Rdzeń i `Worker` dostarczają już bezpieczny opis albo ogólny kod błędu; UI tylko go wyświetla. Ogranicza to podwójną interpretację i ryzyko ponownego nadpisania właściwej diagnozy.

Zachowano nowego klienta na każdą próbę, zerowanie zdarzenia MFA, anulowanie przed zapisem sesji, usuwanie hasła i callbacku po zakończeniu oraz bezpieczne etapy i kody. To potrzebne mechanizmy, a nie pozostałości diagnostyczne. Tymczasowe obserwatory SDK i skrypty odtwarzania błędu były wyłącznie w ignorowanych folderach `test-results/` i diagnostycznych dystrybucjach; nie są częścią produkcyjnego kodu logowania.

Po porządkowaniu 34 testy logowania i UI przeszły; przed zmianą przechodziło 35, w tym jeden test usuniętej, nieużywanej ścieżki. Ruff i formatowanie poprawne. Rdzeń uwierzytelniania i poprawka pakowania TLS nie zostały zmienione podczas tego przeglądu.

Uporządkowana paczka GUI i MCP znajduje się w `dist/login-cleanup`; lokalny launcher wskazuje tę wersję. Build i smoke obu programów przeszły, w tym rzeczywisty konstruktor TLS, 10 ewaluacji MCP i kontrola pustego stderr. Raport budowania: `test-results/login-cleanup-build.log`, raport MCP: `test-results/login-cleanup-mcp-smoke/mcp-smoke.json`. Nie powtarzano pełnego runnera rdzenia po zmianach dotyczących wyłącznie UI. Interaktywnego logowania po tym porządkowaniu nie wykonywano; potwierdzenie użytkownika dotyczy poprawki TLS w poprzedniej paczce, z zachowanym tutaj rdzeniem i sposobem pakowania.

| Funkcja | Złożoność przed | Złożoność po |
| --- | ---: | ---: |
| `LoginDialog.failed` | 3 | 1 |
| `Window.mfa` | 2 | usunięta |

Kod: `garmin_database/auth.py`, `garmin_database/login_dialog.py`, `garmin_database/ui.py` i `scripts/build.py`. Szczegółowe bezpieczne zapisy diagnozy i wyniki odbioru opisuje [instrukcja testów](12-running-and-testing.md).
