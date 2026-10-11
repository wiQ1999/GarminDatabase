# Eksport JSON

## Uzgodniony zakres

Eksport wykonywany ręcznie, dla Claude i ChatGPT. Jeden plik na parametr, bez automatycznego podziału według miesięcy lub rozmiaru. Podział można rozważyć dopiero po sprawdzeniu rzeczywistej wielkości eksportu.

Domyślny pakiet:

- `{parameter}.json`: historia dostępnych podsumowań dziennych danego parametru, tylko gdy takie wartości istnieją w źródle Garmin.
- `recent.json`: szczegółowe pomiary wybranych parametrów z ostatnich 90 zakończonych dni.

Jeśli podsumowania dzienne parametru nie istnieją w źródle, aplikacja ich nie oblicza. Nie tworzy pustego pliku udającego historię; wpis w metadanych `recent.json` informuje o braku takiej reprezentacji. Pełne starsze próbki są dostępne w eksporcie okresu wskazanego przez użytkownika, po jednym pliku na parametr.

`recent.json` jest plikiem z danymi, nie instrukcją dla modelu. „Krótki” oznacza ograniczenie zakresu czasu, a nie obcięcie próbek: szczegółowe 90 dni może nadal dać duży plik. Po zmierzeniu objętości użytkownik może zawęzić okres lub parametry. Bez automatycznej utraty szczegółów.

## Zasady formatu

- UTF-8, poprawny JSON, pola po angielsku, krótkie stabilne nazwy.
- Tylko dane i konieczne etykiety: wersja formatu, parametr, jednostka, zakres, czas, status dostępności i pochodzenie.
- Bez promptów, zaleceń, interpretacji, tekstu o tym jak AI ma analizować dane i własnych wskaźników.
- Kolejność pomiarów deterministyczna. Nie pomijać rekordów o identycznym czasie, jeśli reprezentują różne wiadomości źródłowe.
- Usuwać wyłącznie potwierdzone duplikaty źródłowe; nie łączyć różnych wartości przez średnią ani wybór „najlepszej”.
- Opisy i jednostki podać raz dla serii, zamiast powtarzać przy każdej próbce.
- Czas jednoznaczny w ISO 8601 z przesunięciem lub UTC; lokalny czas bez znanej strefy oznaczony jawnie.
- Zachować wartości źródłowe; brak/nieprawidłowość nie staje się zerem. Nie emitować niedozwolonych w JSON `NaN` lub `Infinity`.
- Wskazać brakujące dni, niepełne dekodowanie i faktyczny zakres dostępnych danych; nie wypełniać luk sztucznymi rekordami.
- Nierozpoznane pola opisać identyfikatorem źródłowym, bez przypisywania niepotwierdzonej metryki.

## Przykład struktury — dane demonstracyjne, nie odczyt próbki

```json
{
  "schema_version": 1,
  "parameter": "heart_rate",
  "unit": "bpm",
  "representation": "samples",
  "from": "2026-10-09",
  "to": "2026-10-09",
  "columns": ["time", "value", "source"],
  "sources": {"s1": "2026-10-09.zip/example_WELLNESS.fit"},
  "data": [["2026-10-09T05:00:00Z", 62, "s1"]],
  "missing_days": [],
  "decode_status": "complete"
}
```

Wykryte nazwy i identyfikatory pól są w [katalogu pełnej historii](09-fit-field-catalog.md). Pole nieznane nie może być eksportowane pod zgadywaną nazwą metryki zdrowotnej. Katalog pól nie jest jeszcze finalnym katalogiem parametrów dla AI: trzeba wybrać reprezentacje źródłowe i rozróżnić metadane, próbki, przedziały oraz podsumowania. Przy wartościach o różnej semantyce, np. parametr dzienny i chwilowy, zachować osobne reprezentacje. Nie używać podpisu „daily_summary”, jeżeli Garmin nie dostarczył takiej wartości.

## Planowane polecenia — jeszcze niezaimplementowane

```text
garmin-db export --recent-days 90 --output exports/current
garmin-db export --from 2026-09-01 --to 2026-09-30 --parameters heart_rate,sleep --output exports/selected
```

Domyślnie koniec okresu to wczoraj; 90 dni obejmuje wczoraj i poprzednie 89 dat. Eksport na żądanie wskazanego okresu zawiera wszystkie dostępne próbki wybranych parametrów. Przed zapisem podać planowaną objętość lub po zapisie raportować rozmiar plików. Nie obiecywać zgodności z konkretnym limitem kontekstu modeli.

Eksporty są odtwarzalne z SQLite. Nie przechowywać ich jako dodatkowego stałego archiwum. Użytkownik zaakceptował zastępowanie poprzednich plików eksportu: kolejne generowanie zastępuje wyniki aplikacji w wybranym folderze, bez tworzenia kolejnych kopii i bez usuwania obcych plików. Zapis pliku powinien być atomowy, aby błąd nie pozostawił uciętego JSON. Jeżeli zmienia się zestaw parametrów, usuwać nieaktualne wyniki wyłącznie na podstawie ewidencji plików wygenerowanych przez aplikację.

W UI można wybrać parametry, zakres historii, okres szczegółowy (domyślnie 90 dni) i folder docelowy. Ostatnie ustawienia są zapisywane w `%LOCALAPPDATA%/GarminDatabase/settings.json`. Po eksporcie dostępny jest przycisk „Otwórz folder eksportu”. Ograniczenia zakresu wykresów nie ograniczają szczegółowego eksportu wskazanego okresu. Zobacz [specyfikację UI](11-desktop-ui.md).
