# Pobranie surowej historii do analizy

`scripts/download_history.py` jest skryptem przygotowawczym. Pobiera wyłącznie oryginalne dzienne ZIP-y z potwierdzonego endpointu dobrostanu. Nie pobiera osobnych treningów, nie dekoduje FIT, nie buduje jeszcze SQLite i nie analizuje zdrowia.

## Uruchomienie na Windows

Zależności są już w `.venv`. W PowerShell:

```powershell
cd D:\Projects\GarminDatabase
.\.venv\Scripts\python.exe .\scripts\download_history.py
```

Domyślnie zakres zaczyna się 2024-01-01 i kończy na wczoraj według `Europe/Warsaw`, ustalonym przy uruchomieniu. Cały bieżący dzień pozostaje wykluczony zgodnie z wymaganiami. Podczas długiego zadania koniec zakresu nie przesuwa się automatycznie.

Pierwsze uruchomienie pyta lokalnie o login, hasło i ewentualny kod MFA. Sesja jest zapisywana do `private/garmin-session/`, aby kolejne uruchomienia mogły ją wykorzystać. Hasło nie jest zapisywane przez skrypt. Nie przesyłać sekretów do czatu. Dane, raport i sesja są wykluczone z Git.

## Pliki wynikowe

- `data/raw/YYYY-MM-DD.zip`: oryginalny rezultat Garmin; bez ponownego pakowania i rozpakowanej kopii.
- `data/collection.json`: raport metadanych i postępu. Dla dnia: status, liczba prób, czas kontroli, rozmiar ZIP, hash ZIP, liczba wpisów, nazwy, rozmiary i hashe ich zawartości. Raport nie kopiuje wartości zdrowotnych z FIT.
- `data/collection.lock`: blokada aktywnego procesu, usuwana przy zwykłym zakończeniu lub Ctrl+C.

Raport obejmuje pierwszą i ostatnią datę niepustego archiwum, łączne rozmiary ZIP i rozpakowanej zawartości oraz liczbę plików według kategorii nazw. To metadane kolekcji, nie nowe wskaźniki zdrowotne. Pierwsza data archiwum nie musi być pierwszą datą pomiaru. Dokładne parametry i pokrycie parsera zostaną ustalone przez późniejsze dekodowanie zebranych FIT.

## Wznowienie i błędy

Można przerwać Ctrl+C i uruchomić to samo polecenie. Istniejące ZIP-y są lokalnie weryfikowane, nie nadpisywane ani ponownie pobierane. Błąd lokalnego ZIP zatrzymuje zadanie i zachowuje plik do wyjaśnienia. Jeśli awaria nastąpiła po zapisaniu ZIP przed raportem, kolejne uruchomienie odzyska stan z lokalnego pliku.

Każdy dzień jest sprawdzany; brak archiwum na początku historii nie kończy poszukiwania. Odpowiedź 404 zapisuje się jako `not_found_unverified`, nie jako potwierdzony brak danych. Pusty, poprawny ZIP zostaje zapisany jako `empty_zip`; jego znaczenie również wymaga analizy. Dni nieodwiedzone po zatrzymaniu nie mają jeszcze rekordu w raporcie.

Domyślnie znane 404 są pomijane przy wznowieniu, aby nie powtarzać całej pustej części historii. Można je ponowić:

```powershell
.\.venv\Scripts\python.exe .\scripts\download_history.py --retry-unresolved
```

Inne błędy nie mają statusu zakończonego dnia. Przejściowe błędy są ponawiane ograniczoną liczbę razy. Uwierzytelnianie, odmowa dostępu, limit 429 lub pięć kolejnych nieudanych dni zatrzymują kolekcję z zapisanym postępem. Nie drukujemy treści odpowiedzi ani pełnych wyjątków mogących zawierać sekrety. Kod zakończenia 2 oznacza zatrzymanie lub nierozstrzygnięte dni; 130 oznacza Ctrl+C.

Skrypt robi domyślnie przerwę 3 sekundy przed próbą pobrania. To ostrożny parametr lokalny, nie zadeklarowany limit Garmin. Biblioteka może również stosować własne ponowienie. Przy 429 skrypt kończy pracę; przed wznowieniem trzeba odczekać. Nie automatyzuje obchodzenia limitów.

Po wymuszonym zakończeniu procesu może pozostać blokada. Usunąć `data/collection.lock` ręcznie dopiero po upewnieniu się, że żaden kolektor nie działa. Uszkodzonego raportu nie usuwać pochopnie: jego utrata spowoduje ponowne sprawdzanie dni z 404, chociaż poprawne ZIP-y zostaną odzyskane lokalnie.

## Parametry

```powershell
# Krótka próba przed pełnym zakresem
.\.venv\Scripts\python.exe .\scripts\download_history.py --from 2024-01-01 --to 2024-01-07

# Inny zakres i dłuższa przerwa między próbami
.\.venv\Scripts\python.exe .\scripts\download_history.py --from 2024-01-01 --delay 5
```

`--data-dir` zmienia katalog archiwów i raportu; `--session-dir` lokalizację sesji. Przy własnych katalogach wewnątrz repozytorium należy zapewnić ich ignorowanie przez Git. `--attempts` określa liczbę prób na dzień, a `--max-failures` próg kolejnych błędów zatrzymujących kolekcję. Pełna lista: `--help`.

Przed pełnym pobraniem warto obserwować pierwsze dni. Duża liczba 404 pozostaje materiałem do analizy, nie dowodem poprawnego rozpoznania braku danych.

## Sprawdzenia skryptu

Testy bez połączenia z Garmin: pobranie i wznowienie, ponowienie przejściowego błędu, zatrzymanie przy 429, zachowanie 404, ponowienie nierozstrzygniętej daty, pusty ZIP, odzyskanie stanu po błędzie raportu i zachowanie uszkodzonego lokalnego pliku.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
