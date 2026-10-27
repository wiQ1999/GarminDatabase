# Eksport JSON: historia i szczegóły

Eksport jest uruchamiany ręcznie z UI lub CLI. Użytkownik wybiera parametry, zakres historii, liczbę ostatnich dni szczegółowych (domyślnie 90), okres obliczonych podsumowań i folder na eksporty. Dane służą odczytowi przez Claude lub ChatGPT; pliki nie zawierają instrukcji ani interpretacji medycznych.

## Pakiet wynikowy

Każde uruchomienie tworzy nowy folder w wybranej lokalizacji, np.:

```text
exports/
  GarminDatabase_2026-10-11_21-30-45_123456/
    manifest.json
    history/
      hrv_value.value.json
      monitoring_hr_data.current_day_resting_heart_rate.json
    details/
      hrv_value.value.json
      monitoring_hr_data.current_day_resting_heart_rate.json
```

Nazwa ma datę i czas Europe/Warsaw z mikrosekundami. W razie kolizji aplikacja atomowo tworzy folder z kolejnym sufiksem. Nigdy nie używa istniejącego folderu pakietu. Starsze eksporty, także dawne `recent.json` i `.garmin-export.json`, pozostają na miejscu; aplikacja ich nie usuwa. Użytkownik zarządza miejscem na dysku i usuwa zbędne pakiety ręcznie.

`history/{parametr}.json` obejmuje podsumowania całego wybranego zakresu. Nie zawiera pełnej historii próbek parametru bez podsumowań. `details/{parametr}.json` zawiera wszystkie źródłowe rekordy wybranego parametru z ostatnich N dni, bez zmniejszania częstotliwości, uśredniania czy usuwania nieprawidłowych odczytów. Nie powstaje zbiorczy `recent.json` ani opcja dołączania pełnych próbek do historii. Aby otrzymać szczegóły całego zakresu, zwiększ N tak, by objęło ten zakres.

Dla parametru będącego źródłowym podsumowaniem, np. tętna spoczynkowego, szczegóły oznaczają wszystkie oryginalne zapisy tego podsumowania. Aplikacja nie tworzy pomiarów chwilowych, których ta seria nie zawiera. Historia i szczegóły celowo nakładają się okresem; nie należy traktować ich jako rozłącznych zbiorów.

`manifest.json` podaje datę utworzenia, zakres, wybór okresu podsumowań, liczbę dni szczegółowych, listę ukończonych plików i rozmiary. `status` jest `running`, `complete`, `cancelled` albo `failed`. Zapis każdego JSON jest strumieniowy i atomowy. Anulowanie usuwa plik tymczasowy, zachowuje ukończone pliki nowego pakietu i oznacza go jako nieukończony; starsze pakiety nie zmieniają się. Stan `running` pozostawiony po awarii oznacza nieukończone uruchomienie.

## Dobór podsumowań do obecnych danych

Domyślny okres to **dzień**. W historii kilku lat oznacza około tysiąca wierszy na parametr, zamiast setek tysięcy próbek. Zachowuje różnice między dniami, które miesięczna średnia mogłaby ukryć. Opcja **miesiąc** daje mniejszy pakiet dla szerokiego przeglądu; dotyczy tylko obliczonych podsumowań, a nie oryginalnych zapisów Garmin. Nie tworzymy kilku redundantnych plików tego samego podsumowania w jednym pakiecie.

| Rodzaj serii | Historia | Szczegóły |
| --- | --- | --- |
| `source_summary` Garmin | Wszystkie oryginalne podsumowania Garmin; `summary_origin: garmin` | Te same źródłowe rekordy, ograniczone do N dni |
| HRV, tętno chwilowe, oddech, saturacja, stres | Średnia, minimum, maksimum i liczniki jakości dla dnia lub miesiąca; `summary_origin: application` | Wszystkie oryginalne próbki z N dni |
| Kategorie, np. fazy snu lub tryb saturacji | Liczba obserwacji każdego kodu (`value_counts`); bez średniej kodów | Wszystkie rekordy wraz z etykietami kodów |
| Pozostałe liczniki, właściwości i zdarzenia | Ostatnia poprawna obserwacja oraz liczniki rekordów (`last_observed`) | Wszystkie oryginalne rekordy z N dni |

Ostatnia obserwacja kroków, dystansu, kalorii lub czasu ruchu **nie jest dziennym bilansem ani sumą**. Różne rodzaje aktywności mogą mieć odrębne narastające liczniki. Liczności faz snu **nie są czasem trwania faz**. Licznik obserwacji zdarzenia nie potwierdza liczby odrębnych zdarzeń. Te metody nie zgadują znaczenia brakującego podsumowania Garmin.

Średnie mają jawną listę parametrów: `hrv_value.value`, `monitoring.heart_rate`, `respiration_rate.respiration_rate`, `spo2_data.reading_spo2`, `stress_level.stress_level_value`. HRV z próbek zachowuje osobną nazwę od `hrv_status_summary.last_night_average` lub `weekly_average`: średnia próbek w dniu kalendarzowym nie jest średnią nocną Garmin.

## Reguły obliczeń i kompletność

Średnia dzienna jest arytmetyczną średnią poprawnych skończonych skalarnych próbek z rozpoznanym czasem UTC, przypisanych do dnia kalendarzowego Europe/Warsaw. Każda obserwacja ma jednakową wagę; to średnia **dostępnych próbek**, bez domniemania pełnego pokrycia doby i bez ważenia czasem lub interpolacji przez luki. Aplikacja nie zakłada stałej częstotliwości źródła i zachowuje przerwy między odczytami. Dni przy zmianie czasu mają prawidłowe granice lokalne.

Średnia miesięczna jest ważona liczbą poprawnych próbek dni: `sum(mean_day * valid_count_day) / sum(valid_count_day)`. Nie jest nieważoną średnią średnich dziennych. Minimum i maksimum obejmują te same poprawne próbki. Miesięczny rekord podaje `valid_days`, `period_from` i `period_to`, także dla niepełnego miesiąca. Brak jakiejkolwiek poprawnej próbki daje `null`, a nie zero.

`valid_count` oznacza liczbę obserwacji użytych przez daną metodę, `invalid_count` — rekordy nieważne lub błędnie zdekodowane, `excluded_count` — poprawne wg FIT, ale nieprzydatne do średniej (np. tablica lub ujemna wartość stresu), `untimed_count` — rekordy bez rozpoznanego czasu. Te ostatnie nie biorą udziału w obliczeniu; są ewidencjonowane pod dniem żądania archiwum. `day_basis` odróżnia `measurement_time`, `requested_day` i `mixed`. `first_time` i `last_time` dotyczą tylko poprawnych obserwacji użytych w podsumowaniu. Liczniki są rozłączne.

Nie odrzucamy nieprawidłowych rekordów ze szczegółów ani z PostgreSQL. Ujemne wartości stresu nie są dodatnim pomiarem poziomu stresu i nie wchodzą do średniej; zachowujemy je w danych źródłowych. Nie przypisujemy im zgadywanej etykiety medycznej. Deduplikacja nadal dotyczy identycznych FIT po SHA-256, nie samej pary czas–wartość; różne wiadomości źródłowe z tym samym czasem pozostają osobnymi obserwacjami.

Metadane każdego pliku obejmują `missing_days`, `unimported_or_partial_days` i `decode_status` ze spójnego obrazu PostgreSQL. `missing_days` oznacza brak potwierdzonego archiwum, nie pewność braku pomiarów zegarka. `decode_status: complete` nie gwarantuje obecności każdego parametru każdego dnia. Brakujące dni nie są uzupełniane zerem lub sztucznym pomiarem.

Podsumowania dzienne są zapisywane w osobnych tabelach PostgreSQL, z metodą, wersją algorytmu, zakresem i rewizją danych. Powstają na żądanie eksportu lub wykresu. Import i ponowne przetwarzanie unieważniają cache; następny odczyt go odbudowuje. Podsumowania miesięczne są wyliczane z dziennych bez dodatkowej trwałej kopii. Szczegóły: [schemat v3](10-postgresql-schema.md).

## Format JSON v2

UTF-8, poprawny JSON, krótkie angielskie nazwy. Parametr ma nazwę `message_name.variant_name`. Nazwa pliku jest zabezpieczona przed ścieżkami i kolizjami po normalizacji. `schema_version: 2` odróżnia nowy pakiet od dawnego eksportu.

Każda seria ma `parameter`, `unit`, `from`, `to`, `kind` (`history` albo `details`), `representation` i `columns`. Tablica `data` zawiera wiersze w kolejności z `columns`. Jednostka jest podana raz; wartości są już przeskalowane według profilu FIT.

Szczegóły oraz źródłowe podsumowania mają kolumny `[time, value, source, validity]`. Kody `v`, `i`, `p`, `e` rozwija `validity_labels`; źródła `s1`, `s2` rozwija słownik `sources`. Każde źródło podaje ścieżkę FIT w ZIP i `requested_day`, który nie zastępuje czasu pomiaru. Nieznany czas to `null`. Czasy pomiarów są zapisane w UTC ISO 8601, a pole `timezone` określa lokalną granicę dni zestawień. Kody kategorii rozwija `value_labels`.

Historia obliczona ma `representation: computed_summary`, `source_representation`, `summary_origin: application`, `data_revision` i `aggregation` z metodą, okresem i wersją algorytmu. Jej kolumny zależą od metody i są wymienione w pliku. Przykład demonstracyjny fragmentu średniej dziennej:

```json
{
  "parameter": "hrv_value.value",
  "unit": "ms",
  "representation": "computed_summary",
  "summary_origin": "application",
  "aggregation": {"method": "sample_mean", "period": "day", "algorithm_version": 1},
  "columns": ["day", "mean", "minimum", "maximum", "valid_count", "invalid_count", "excluded_count", "untimed_count", "first_time", "last_time", "day_basis"],
  "data": [["2026-10-09", 50, 40, 60, 2, 1, 0, 0, "2026-10-09T01:00:00+00:00", "2026-10-09T01:05:00+00:00", "measurement_time"]]
}
```

To dwa poprawne pomiary o średniej 50 ms, minimum 40 i maksimum 60 oraz jeden nieprawidłowy rekord. Takie dane opisują dostępne obserwacje, a nie interpretację zdrowia.

## Uruchamianie i ograniczanie rozmiaru

```text
python -m garmin_database.bootstrap.cli export --recent-days 90 --output exports
python -m garmin_database.bootstrap.cli export --parameters hrv_value.value --summary-period month --recent-days 30 --output exports
python -m garmin_database.bootstrap.cli export --from 2026-09-01 --to 2026-09-30 --parameters monitoring.heart_rate --recent-days 30 --output exports
```

Opcja `--full-samples` została usunięta. Początek szczegółów to późniejsza z dat: początek historii i koniec minus N−1 dni. Koniec domyślny to dzisiaj Europe/Warsaw; bieżący dzień ma potencjalnie niepełną kompletność. W UI „Podsumowania historii” wybiera dzień lub miesiąc, „Szczegółowe ostatnie dni” wybiera N, a „Folder na eksporty” jest katalogiem nadrzędnym nowych pakietów. „Otwórz folder eksportu” otwiera ostatni ukończony pakiet w bieżącym oknie. Wybory są zapisywane w `%LOCALAPPDATA%/GarminDatabase/settings.json`; dawny `full_samples` jest ignorowany.

Pliki szczegółowe nadal mogą być duże: 90 dni nie oznacza limitu liczby tokenów. Można zawęzić liczbę dni lub parametrów, bez automatycznego obcinania danych. Nie dzielimy pojedynczego parametru na miesiące ani nie obiecujemy zgodności z konkretnym limitem modelu.

Punkt wejścia: `Exporter.generate` w `src/garmin_database/application/use_cases/export_data.py`; czyste obliczenia: `src/garmin_database/domain/aggregation.py`; cache: `src/garmin_database/adapters/outbound/postgres/summaries.py`; zapis JSON: `src/garmin_database/adapters/outbound/filesystem/json_export.py`. Eksport nie korzysta z dodatkowej usługi sieciowej.

## Wspólne reguły z MCP i wybór parametrów

Lista `export_parameters` w zapisanych Ustawieniach określa dostępność w plikach. Ekran Eksport i `--parameters` wybierają jej podzbiór. CLI bez `--parameters` używa tej listy; bezpośrednie wywołanie `Exporter` także ją sprawdza i ponownie pobiera kanoniczne opisy parametrów. Pusta lista niczego nie udostępnia. Migracja ustawień sprzed wersji 2 zamienia dawny pusty wybór „wszystko” jednorazowo na jawne klucze aktualnego katalogu. Nowe parametry nie włączają się automatycznie. MCP ma osobną listę i przełącznik, opisane w [UI](11-desktop-ui.md).

Wszystkie pliki v2 zachowują dotychczasowe kolumny i precyzję. Nagłówki mają dodatkowo `calendar_timezone: Europe/Warsaw` oraz `timestamp_timezone: UTC`; dawne `timezone` nadal oznacza granice dni. Rozpoznane momenty, również `first_time` i `last_time`, pozostają w UTC. MCP pokazuje te same momenty w Warszawie z pełną datą i offsetem i zaokrągla wyłącznie prezentację: HRV/tętno do liczb całkowitych, oddech/saturację/stres do jednego miejsca. Nie zmienia PostgreSQL ani cache.

Średnia okresowa MCP i miesięczna średnia eksportu korzystają ze wspólnego `period_summary`: `sum(mean_day * valid_count_day) / sum(valid_count_day)`. Obliczenie używa niezaokrąglonych danych. Dni bez poprawnych próbek nie są zerami i nie mają wagi. Średnie nie są ważone czasem. Wynik dla tego samego okresu i rewizji jest zgodny przed formatowaniem.

Limit 92 dni na stronę i 16 KiB wyniku dotyczy MCP. Eksport nadal strumieniowo zapisuje cały wybrany zakres do nowego pakietu, bez cichego obcinania i bez usuwania poprzednich eksportów. Oba kanały jawnie rozróżniają brak archiwum, częściowy import oraz brak poprawnych próbek metryki. Nie wyliczamy `wear_pct` z liczby próbek, ponieważ nie jest to wiarygodny czas noszenia zegarka.

Kompletność zawiera `ongoing_days` dla bieżącego dnia, który może otrzymać kolejne dane. Pole `decode_status` nadal opisuje stan dekodowania otrzymanych FIT. MCP używa powodu luki `current_day` dla takiego dnia.
