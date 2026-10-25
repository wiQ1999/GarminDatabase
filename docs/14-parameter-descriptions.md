# Objaśnienia parametrów Garmin

## Zakres i pochodzenie

Aplikacja przechowuje lokalne polskie parafrazy publicznych materiałów Garmin, z odnośnikami do producenta. Definicje są wspólne dla panelu pod wykresem i `description` w katalogu oraz obu metodach odczytu MCP. Rejestr jest w `src/garmin_database/application/parameter_descriptions.py`; nie wymaga sieci ani dodatkowego odczytu bazy podczas wyboru parametru.

Wersja opisu: **1**, sprawdzenie źródeł: **2026-10-25**. Definicje techniczne sprawdzono w publicznym profilu FIT SDK **21.218.0**, zgodnym z przypiętą zależnością projektu; odnośnik do repozytorium Garmin prowadzi do bieżącego publicznego profilu. Teksty nie zastępują instrukcji konkretnego modelu. Plik FIT nie zawsze identyfikuje sprzęt, który dostarczył pojedynczy odczyt, dlatego opis funkcji nie potwierdza rodzaju czujnika każdej próbki.

`evidence` określa zakres potwierdzenia: `manufacturer_explanation` — producent opisuje funkcję, `fit_profile_only` — potwierdzona definicja pola, ale ograniczony opis algorytmu, `not_documented` — brak zweryfikowanego objaśnienia nowego pola. Nieznany parametr zachowuje nazwę i wartość, bez wymyślonej interpretacji. Nieznane wagi, progi, jednostki i prywatne algorytmy pozostają nieznane.

## Jak porównywać z Garmin Connect

- `monitoring.heart_rate` to obserwacje tętna, a nie tętno spoczynkowe. Pole `monitoring_hr_data.resting_heart_rate` ma w FIT znaczenie średniej kroczącej RHR z 7 dni; `current_day_resting_heart_rate` jest odrębną wartością bieżącego dnia.
- `hrv_value.value` jest pięciominutowym RMSSD. Nocna średnia, nocne maksimum z 5 minut, tygodniowa średnia i status względem osobistej bazy to osobne źródłowe pola `hrv_status_summary`.
- `stress_level.stress_level_value` jest oceną algorytmiczną HR/HRV, nie bezpośrednim pomiarem emocji. W obliczonych średnich aplikacja wyłącza ujemne kody. Źródłowe `average_stress_during_sleep` wyłącza czuwanie w oknie snu zgodnie z definicją Garmin.
- Oddech jest estymowany z rytmu serca; Pulse Ox z sygnału optycznego czerwonego/podczerwonego. Dostępność odczytów zależy od urządzenia, ustawień i warunków. Średnia SpO₂ całego dnia nie oznacza średniej wyłącznie podczas snu.
- Ocena snu na skali 0–100 jest czymś innym niż liczba przebudzeń, kod fazy snu lub czas snu. `sleep_disruption_*` ma publiczne klasy nasilenia; sam profil nie potwierdza mapowania tych pól na konkretną ocenę oddychania w Garmin Connect.
- Odchylenie temperatury skóry od osobistej bazy nie jest temperaturą wnętrza ciała. Dla `nightly_value` publiczny profil nie podaje jednostki i pełnego przeliczenia; nie dopisujemy ich na podstawie nazwy.
- Liczniki monitoringu mogą zależeć od `activity_type`. Nie sumuje się kolejnych stanów licznika. `last_value` oznacza wartość ostatniej obserwacji, nie średnią ani znacznik czasu; czas jest osobnym polem. Przy jednakowych czasach istniejący reduktor rozstrzyga remis porządkiem identyfikatorów źródłowych w bazie, więc kolejność pierwszej rejestracji FIT może wpływać na tę wartość. Reguły importu i ograniczenia współbieżności są w [synchronizacji](04-synchronization.md).

Dzień wykresu pokazuje próbki. Tylko pięć `MEAN_PARAMETERS` ma obliczane średnie w dłuższych okresach i MCP. Są to średnie arytmetyczne poprawnych próbek, a średnia okresowa jest ważona ich liczbą. „Poprawna” oznacza tu zgodną z dotychczasowymi regułami kodowania i agregacji, nie potwierdzoną fizjologicznie. Algorytm 1 odrzuca znaczniki niepoprawności FIT, wartości niefinitywne i ujemny stres; nie ma dodatkowego filtra zerowego tętna ani ujemnego oddechu. Publiczny profil nie wyjaśnia znaczenia tych niestandardowych odczytów; nie zgadujemy go i nie zmieniamy reguł obliczeń przy dodawaniu objaśnień.

Nie stosuje się ważenia czasem ani uzupełniania luk. Przed porównaniem należy sprawdzić `valid_count`, braki, `first_time`/`last_time`, dzień Europe/Warsaw i tożsamość statystyki w Garmin Connect. Gotowe podsumowania Garmin nie są zastępowane tymi średnimi. Brak czasu źródłowego nie jest naprawiany datą archiwum.

## Struktura odpowiedzi MCP

Dostępne są trzy narzędzia: `garmin_catalog`, `get_daily`, `get_period_stats`. Pełne argumenty, kolumny, stronicowanie i limity opisuje [kontrakt MCP](12-running-and-testing.md#narzędzia-mcp-v1). Katalog obejmuje wyłącznie obecne i włączone pięć obsługiwanych metryk; szerszy katalog UI/eksportu i przypisanie do kategorii nie rozszerzają dostępu MCP.

Wynik MCP zawiera krótki `content` oraz właściwe dane w `structuredContent`. Wspólna koperta ma `schema_version`, `calendar_timezone`, `timestamp_timezone`, `data_revision`, `policy_revision`, `truncated` i `next_cursor`. Metody odczytu dodają `requested_from`, `requested_to`, faktyczne `from`/`to`, `gaps`, `gaps_format` i `decode_status`.

Katalog ma `metrics[]` z `parameter`, `label`, `unit`, `description`, `method`, `precision`, `from`, `to`, `operations`; dodatkowo `limits` i `gaps_detail`. Odczyty mają `series[]` z `parameter`, `unit`, `description`, `summary_origin`, `aggregation`, `precision`, `columns` i `data`. `data` jest tablicą wierszy pozycyjnych, a ich znaczenie podaje `columns`. Dzienne kolumny rozpoczynają się od `day`, `mean`, `minimum`, `maximum`; okresowe od `period_from`, `period_to`, `mean`, `minimum`, `maximum`. Dalej są liczniki jakości i czasy, a dla okresu również liczby dni.

Obiekt `description` zawiera:

```json
{
  "version": 1,
  "language": "pl-PL",
  "reviewed_on": "2026-10-25",
  "meaning": "Znaczenie konkretnego parametru",
  "measurement": "Czujnik lub algorytm opisany przez producenta",
  "limitations": "Granice interpretacji tego pola",
  "presentation": "Sposób prezentacji i agregacji w aplikacji",
  "evidence": "manufacturer_explanation",
  "sources": [{"title": "Tytuł oficjalnego materiału", "url": "https://www.garmin.com/"}]
}
```

Przykład wyżej jest schematyczny, nie zawiera pomiarów. Rzeczywiste odpowiedzi i porównania danych użytkownika nie należą do dokumentacji ani fixture testów. Objaśnienie występuje raz na serię, nie przy każdym wierszu. Wlicza się do limitu 16 KiB; strona dzienna może przez to zawierać mniej niż 92 dni. Wersja opisu jest niezależna od `data_revision` i wersji algorytmu średnich. Rozszerzenie nie zmienia schematu PostgreSQL, precyzji ani pomiarów.

## Definicje pól

To katalog definicji obsługiwanych przez aplikację, niezależny od zawartości konkretnej bazy. Szczegóły metody i ograniczenia każdego pola są w lokalnym rejestrze oraz w UI. Numery źródeł odsyłają do oficjalnych materiałów poniżej.

| Klucz | Znaczenie | Podstawa | Źródła |
| --- | --- | --- | --- |
| `hrv_status_summary.baseline_balanced_lower` | Dolna granica osobistego zakresu zrównoważonego HRV. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `hrv_status_summary.baseline_balanced_upper` | Górna granica osobistego zakresu zrównoważonego HRV. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `hrv_status_summary.baseline_low_upper` | Górna granica zakresu niskiego HRV w osobistej wartości bazowej. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `hrv_status_summary.last_night_5_min_high` | Najwyższa pięciominutowa wartość RMSSD ostatniej nocy. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `hrv_status_summary.last_night_average` | Średnie RMSSD z ostatniej nocy, wyznaczone przez Garmin. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `hrv_status_summary.status` | Klasyfikacja statusu HRV względem osobistej bazy; kod kategorii, nie pomiar w ms. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `hrv_status_summary.weekly_average` | 7-dniowa średnia nocnego RMSSD zapisana przez Garmin. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `hrv_value.value` | Pięciominutowa statystyka HRV RMSSD w milisekundach, zgodnie z definicją pola FIT. | `manufacturer_explanation` | [2](#źródła), [22](#źródła) |
| `monitoring.active_calories` | Energia zużyta na aktywność i ruch, w kcal. | `manufacturer_explanation` | [16](#źródła), [17](#źródła), [22](#źródła) |
| `monitoring.active_time` | Skumulowany czas aktywności zapisany w monitoringu FIT, w sekundach. | `fit_profile_only` | [22](#źródła) |
| `monitoring.activity_type` | Kategoria aktywności przypisana przez urządzenie. | `fit_profile_only` | [22](#źródła) |
| `monitoring.ascent` | Skumulowana wysokość wznoszenia zapisana w monitoringu, w metrach. | `manufacturer_explanation` | [20](#źródła), [22](#źródła) |
| `monitoring.calories` | Skumulowany licznik kalorii w monitoringu FIT, zależny od activity_type. | `manufacturer_explanation` | [16](#źródła), [17](#źródła), [22](#źródła) |
| `monitoring.current_activity_type_intensity` | Złożone pole FIT opisujące bieżący typ aktywności i intensywność od poprzedniej wiadomości. | `fit_profile_only` | [22](#źródła) |
| `monitoring.cycles` | Skumulowane cykle ruchu; ich znaczenie zależy od typu aktywności. | `fit_profile_only` | [22](#źródła) |
| `monitoring.descent` | Skumulowana wysokość opadania zapisana w monitoringu, w metrach. | `manufacturer_explanation` | [20](#źródła), [22](#źródła) |
| `monitoring.distance` | Skumulowany dystans monitoringu, w metrach, powiązany z typem aktywności. | `manufacturer_explanation` | [21](#źródła), [22](#źródła) |
| `monitoring.duration` | Czas trwania w sekundach zapisany w komunikacie monitoring. | `fit_profile_only` | [22](#źródła) |
| `monitoring.duration_min` | Czas trwania w minutach zapisany w komunikacie monitoring. | `fit_profile_only` | [22](#źródła) |
| `monitoring.heart_rate` | Częstość pracy serca w uderzeniach na minutę (bpm). | `manufacturer_explanation` | [1](#źródła) |
| `monitoring.intensity` | Źródłowa wartość intensywności ruchu w monitoringu FIT. | `fit_profile_only` | [22](#źródła) |
| `monitoring.moderate_activity_minutes` | Licznik minut umiarkowanej aktywności. | `manufacturer_explanation` | [18](#źródła), [19](#źródła) |
| `monitoring.steps` | Licznik kroków z monitoringu Garmin. | `manufacturer_explanation` | [15](#źródła), [22](#źródła) |
| `monitoring.vigorous_activity_minutes` | Licznik minut intensywnej aktywności; Garmin zalicza je podwójnie do celu minut intensywności. | `manufacturer_explanation` | [18](#źródła), [19](#źródła) |
| `monitoring_hr_data.current_day_resting_heart_rate` | Tętno spoczynkowe dla bieżącego dnia zapisane przez Garmin. | `manufacturer_explanation` | [3](#źródła), [22](#źródła) |
| `monitoring_hr_data.resting_heart_rate` | W tym polu FIT Garmin zapisuje 7-dniową średnią kroczącą tętna spoczynkowego. | `manufacturer_explanation` | [3](#źródła), [22](#źródła) |
| `nap_event.end_timezone_offset` | Przesunięcie czasu względem UTC na końcu drzemki, w minutach. | `manufacturer_explanation` | [12](#źródła), [22](#źródła) |
| `nap_event.feedback` | Źródłowa kategoria informacji zwrotnej o drzemce (m.in. pora, długość i zapotrzebowanie). | `manufacturer_explanation` | [12](#źródła), [22](#źródła) |
| `nap_event.is_deleted` | Źródłowa flaga oznaczająca usunięcie zdarzenia drzemki. | `manufacturer_explanation` | [12](#źródła), [22](#źródła) |
| `nap_event.message_index` | Techniczny indeks wiadomości FIT, z bitami flag i maską indeksu. | `fit_profile_only` | [23](#źródła), [22](#źródła) |
| `nap_event.source` | Źródło zdarzenia drzemki: automatyczne, ręczne w urządzeniu lub ręczne w Garmin Connect. | `manufacturer_explanation` | [12](#źródła), [22](#źródła) |
| `nap_event.start_timezone_offset` | Przesunięcie czasu względem UTC na początku drzemki, w minutach. | `manufacturer_explanation` | [12](#źródła), [22](#źródła) |
| `respiration_rate.respiration_rate` | Szacowana liczba pełnych oddechów na minutę. | `manufacturer_explanation` | [6](#źródła), [7](#źródła), [22](#źródła) |
| `skin_temp_overnight.average_7_day_deviation` | Średnie odchylenie nocnej temperatury skóry z 7 dni (°C w opisie profilu). | `manufacturer_explanation` | [13](#źródła), [14](#źródła), [22](#źródła) |
| `skin_temp_overnight.average_deviation` | Średnie nocne odchylenie temperatury skóry od wartości bazowej (°C w opisie profilu). | `manufacturer_explanation` | [13](#źródła), [14](#źródła), [22](#źródła) |
| `skin_temp_overnight.nightly_value` | Końcowa nocna wartość temperatury w źródłowym polu FIT nightly_value. | `fit_profile_only` | [13](#źródła), [14](#źródła), [22](#źródła) |
| `sleep_assessment.average_stress_during_sleep` | Źródłowa średnia stresu podczas snu obliczona przez Garmin. | `manufacturer_explanation` | [4](#źródła), [22](#źródła) |
| `sleep_assessment.awake_time_score` | Ocena czasu czuwania pomiędzy okresami snu. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.awakenings_count` | Liczba przebudzeń podczas snu zapisana przez Garmin. | `manufacturer_explanation` | [11](#źródła), [22](#źródła) |
| `sleep_assessment.awakenings_count_score` | Ocena liczby przebudzeń przerywających sen. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.combined_awake_score` | Ocena łącząca awake_time_score i awakenings_count_score; w FIT ich średnia. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.deep_sleep_score` | Ocena ilości snu głębokiego. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.interruptions_score` | Ocena przerw w śnie. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.light_sleep_score` | Ocena ilości snu płytkiego. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.overall_sleep_score` | Łączna ocena jakości i długości snu. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.rem_sleep_score` | Ocena ilości snu REM. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.sleep_duration_score` | Składowa oceny snu oznaczona przez Garmin jako sleep_duration_score. | `fit_profile_only` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.sleep_quality_score` | Ocena jakości snu: struktura faz, HRV i przebudzenia. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.sleep_recovery_score` | Ocena stresu i regeneracji podczas snu. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_assessment.sleep_restlessness_score` | Ocena niespokojności i ruchu podczas snu. | `manufacturer_explanation` | [10](#źródła), [22](#źródła) |
| `sleep_disruption_overnight_severity.severity` | Źródłowa kategoria nasilenia zakłóceń snu: none, low, medium lub high. | `fit_profile_only` | [22](#źródła) |
| `sleep_disruption_severity_period.message_index` | Techniczny indeks wiadomości FIT, z bitami flag i maską indeksu. | `fit_profile_only` | [23](#źródła), [22](#źródła) |
| `sleep_disruption_severity_period.severity` | Źródłowa kategoria nasilenia zakłóceń snu: none, low, medium lub high. | `fit_profile_only` | [22](#źródła) |
| `sleep_level.sleep_level` | Faza snu rozpoznana przez Garmin: czuwanie, sen płytki, głęboki, REM lub brak możliwości oceny. | `manufacturer_explanation` | [11](#źródła), [22](#źródła) |
| `spo2_data.mode` | Tryb zarejestrowania odczytu Pulse Ox; kod kategorii, nie wartość saturacji. | `manufacturer_explanation` | [9](#źródła), [22](#źródła) |
| `spo2_data.reading_confidence` | Źródłowe pole pewności odczytu SpO₂ w profilu FIT. | `fit_profile_only` | [22](#źródła) |
| `spo2_data.reading_spo2` | Szacowana saturacja obwodowa SpO₂: procent wysycenia krwi tlenem. | `manufacturer_explanation` | [8](#źródła) |
| `stress_level.stress_level_value` | Oszacowanie fizjologicznego poziomu stresu na skali Garmin 0–100. | `manufacturer_explanation` | [4](#źródła), [5](#źródła) |

## Źródła

1. [Garmin: Heart Rate Monitoring](https://www.garmin.com/en-US/garmin-technology/health-science/heart-rate-monitoring/)
2. [Garmin: HRV Status](https://www.garmin.com/en-US/garmin-technology/health-science/hrv-status/)
3. [Garmin: How Is Resting Heart Rate Calculated?](https://support.garmin.com/en-AU/?faq=F8YKCB4CJd5PG0DR9ICV3A)
4. [Garmin: Stress Tracking](https://www.garmin.com/en-CA/garmin-technology/health-science/stress-tracking/)
5. [Garmin: What Is the Stress Level Feature?](https://support.garmin.com/en-HK/?faq=WT9BmhjacO4ZpxbCc0EKn9)
6. [Garmin: Respiration Rate](https://www.garmin.com/en-GB/garmin-technology/health-science/respiration-rate/)
7. [Garmin: Using the Respiration Rate Feature](https://support.garmin.com/da-DK/?faq=2yEgS0Pax53UDqUH7q4WC6)
8. [Garmin: Pulse Ox](https://www.garmin.com/en-US/garmin-technology/health-science/pulse-ox/)
9. [Garmin: Top FAQs for Pulse Ox](https://support.garmin.com/en-IN/?faq=SK2Y9a9aBp5D6n4sXmPBG7)
10. [Garmin: Sleep Tracking](https://www.garmin.com/en-IE/garmin-technology/health-science/sleep-tracking/)
11. [Garmin: Advanced Sleep Monitoring](https://support.garmin.com/en-AU/navionics/faq/mBRMf4ks7XAQ03qtsbI8J6/)
12. [Garmin: Tracking Naps](https://support.garmin.com/in-ID/?faq=2icqqZFq3YAX5K9VGU2CQ9)
13. [Garmin: Skin Temperature](https://support.garmin.com/id-ID/?faq=RDXq6E5Iaq9rD1l1kTObf6)
14. [Garmin: Activity Tracking and Fitness Metric Accuracy](https://www.garmin.com/en-IE/legal/atdisclaimer/)
15. [Garmin: Counting Steps](https://support.garmin.com/en-IN/?faq=z1TfJCqajl8ZEZey72gg98)
16. [Garmin: Calorie Terminology](https://support.garmin.com/en-CA/?faq=lkl4cwCLlK7ox362uGQEV7)
17. [Garmin: Tracking Calories](https://support.garmin.com/it-IT/?faq=lkl4cwCLlK7ox362uGQEV7)
18. [Garmin: Intensity Minutes](https://support.garmin.com/en-US/aviation/faq/pNU9nnDzzGAHmEavp9rpY8/)
19. [Garmin: How Are Intensity Minutes Earned?](https://support.garmin.com/en-US/?faq=pNU9nnDzzGAHmEavp9rpY8&productID=707538&tab=)
20. [Garmin: tactix 8, elevation and floors](https://www8.garmin.com/manuals/webhelp/GUID-EA668398-46E4-42E4-8163-12F6CB299F0E/EN-US/GUID-C950F63E-2687-4B1D-AAF7-F67CE6B05EFF.html)
21. [Garmin: Step Distance and Stride Length](https://support.garmin.com/en-AU/?faq=ky5UNByyYh9iXay7mvbnt9&productID=583562&tab=)
22. [Garmin FIT SDK: public profile](https://github.com/garmin/fit-python-sdk/blob/main/garmin_fit_sdk/profile.py)
23. [Garmin: FIT Protocol, common fields](https://developer.garmin.com/fit/protocol/)
