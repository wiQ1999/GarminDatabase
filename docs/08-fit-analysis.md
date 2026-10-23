# Analiza pełnej pobranej historii FIT

Stan z 2026-10-10. Analiza dotyczy plików uzyskanych z jednego endpointu dobrostanu, nie wszystkich informacji dostępnych na platformie Garmin Connect.

## Metoda

Każdy ZIP otwarto lokalnie, a FIT odczytywano pojedynczo. Nie rozpakowywano plików na dysk ani nie przekazywano pełnych pomiarów do kontekstu rozmowy. Raport przechowuje tylko metadane, liczby, typy, zakres czasu i katalog pól. Identyczne FIT deduplikowano po SHA-256 na czas dekodowania, zachowując liczbę ich wystąpień.

Parser: fitdecode 0.11.0, CRC i błędy w trybie RAISE. Kontrola uzupełniająca: oficjalne Garmin FIT SDK 21.218.0, bez skalowania, zamiany enumów, rozwijania komponentów ani łączenia tętna. SDK sprawdzono na jednym reprezentancie każdego wykrytego zestawu pól, nie na wszystkich plikach. Zgodność liczby wiadomości nie dowodzi zgodności każdej wartości.

Źródła zasad formatu: [protokół FIT](https://developer.garmin.com/fit/protocol/) oraz [oficjalny SDK Python](https://github.com/garmin/fit-python-sdk). Opcje rozwijania subpól i komponentów są transformacjami profilu FIT, które trzeba odróżniać od fizycznych pól źródła.

## Wyniki

| Pozycja | Wynik |
| --- | ---: |
| Archiwa ZIP | 844 |
| Rozmiar ZIP, bajty | 42329997 |
| Rozmiar FIT po rozpakowaniu, bajty | 88801002 |
| Wystąpienia FIT | 10994 |
| Unikatowe treści FIT | 10994 |
| Wiadomości FIT, z powtórzeniami plików | 8307429 |
| Typy wiadomości | 69 |
| Warianty pól | 1133 |
| Warianty fizycznych pól | 1129 |
| Warianty rozwinięć parsera | 4 |
| Wystąpienia fizycznych pól | 20841953 |
| Nazwane wystąpienia fizycznych pól, % | 52.78 |
| Nieznane warianty fizycznych pól | 773 |
| Warianty nazwane tylko w nowszym SDK | 36 |
| Nazwane wystąpienia po uzupełnieniu profilem SDK, % | 52.81 |
| Nieznane warianty po uzupełnieniu profilem SDK | 737 |
| Błędy dekodowania FIT | 0 |
| Ostrzeżenia parsera, z powtórzeniami | 0 |
| Reprezentanci sprawdzeni SDK | 345 |
| Próby SDK z błędem | 0 |
| Próby SDK z inną liczbą wiadomości | 0 |
| Warianty fizycznych pól z tablicami | 38 |
| Warianty z nieważnymi elementami tablic | 25 |
| Warianty z liczbami poza signed int64 | 0 |
| Warianty Developer Data | 0 |

## Dostępność historii

Pierwsze niepuste archiwum: **2024-02-17**, ostatnie: **2026-10-09**. Ciągła sekwencja dostępnych archiwów zaczyna się **2024-06-19**. Pozostaje **169** dni z odpowiedzią 404 oznaczoną jako nierozstrzygnięta.

Archiwum 2024-02-17 zawiera pojedynczy plik METRICS; nie jest początkiem pełnego zapisu dobrostanu. Od 2024-06-19 występuje ciągła historia ZIP do 2026-10-09. Brak ZIP na wcześniejsze daty nie rozstrzyga, czy pomiary nigdy nie istniały, czy nie są udostępniane przez ten endpoint.

Zakres rozpoznanych pól czasu UTC, obejmujący również metadane plików: `2024-02-17T03:13:36+00:00` – `2026-10-09T22:00:00+00:00`. Nie obejmuje czasu nierozpoznanych prywatnych pól i nie dowodzi kompletności pomiarów.

| Kategoria plików | Liczba wystąpień | Pierwszy ZIP | Ostatni ZIP |
| --- | ---: | --- | --- |
| ACTIVITY | 9 | 2024-06-19 | 2026-10-08 |
| HRV_STATUS | 838 | 2024-06-20 | 2026-10-09 |
| METRICS | 3591 | 2024-02-17 | 2026-10-09 |
| NAP | 9 | 2024-07-10 | 2026-08-09 |
| SKIN_TEMP | 833 | 2024-06-20 | 2026-10-09 |
| SLEEP_DATA | 838 | 2024-06-20 | 2026-10-09 |
| SLEEP_DISRUPTIONS | 451 | 2025-05-25 | 2026-10-09 |
| WELLNESS | 4425 | 2024-06-19 | 2026-10-09 |

## Rozpoznany zakres parametrów

Poniżej wszystkie nazwane rodziny wiadomości i ich rozpoznane pola. Obejmują zarówno pomiary, jak i metadane techniczne. Szczegółowy katalog zawiera również każdą nierozpoznaną wiadomość i pole, jednostki, tablice i liczbę wystąpień.

| Nr | Wiadomość | Rozpoznane pola |
| ---: | --- | --- |
| 0 | file_id | garmin_product, manufacturer, number, serial_number, time_created, type |
| 2 | device_settings | active_time_zone, activity_tracker_enabled, auto_activity_detect, autosync_min_steps, autosync_min_time, backlight_mode, date_mode, display_orientation, lactate_threshold_autodetect_enabled, mounting_side, move_alert_enabled, number_of_screens, time_mode, time_offset, time_zone_offset, utc_offset |
| 3 | user_profile | activity_class, depth_setting, dist_setting, elev_setting, gender, height, height_setting, hr_setting, language, position_setting, resting_heart_rate, sleep_time, speed_setting, temperature_setting, user_running_step_length, user_walking_step_length, wake_time, weight, weight_setting |
| 7 | zones_target | functional_threshold_power, hr_calc_type, max_heart_rate, pwr_calc_type, threshold_heart_rate |
| 12 | sport | name, sport, sub_sport |
| 13 | training_settings | target_distance, target_speed, target_time |
| 18 | session | active_time, avg_cadence, avg_cadence_position, avg_combined_pedal_smoothness, avg_flow, avg_fractional_cadence, avg_grade_adjusted_speed, avg_heart_rate, avg_left_pco, avg_left_pedal_smoothness, avg_left_power_phase, avg_left_power_phase_peak, avg_left_torque_effectiveness, avg_power, avg_power_position, avg_right_pco, avg_right_pedal_smoothness, avg_right_power_phase, avg_right_power_phase_peak, avg_right_torque_effectiveness, avg_spo2, avg_stance_time, avg_stance_time_balance, avg_stance_time_percent, avg_step_length, avg_stress, avg_stroke_count, avg_stroke_distance, avg_strokes_per_length, avg_swolf, avg_temperature, avg_vertical_oscillation, avg_vertical_ratio, end_position_lat, end_position_long, enhanced_avg_respiration_rate, enhanced_avg_speed, enhanced_max_respiration_rate, enhanced_max_speed, enhanced_min_respiration_rate, event, event_group, event_type, first_lap_index, front_gear_shift_count, intensity_factor, left_right_balance, max_cadence, max_cadence_position, max_fractional_cadence, max_heart_rate, max_power, max_power_position, max_temperature, message_index, metabolic_calories, min_temperature, nec_lat, nec_long, normalized_power, num_active_lengths, num_laps, num_lengths, num_segment_laps, pool_length, pool_length_unit, rear_gear_shift_count, rmssd_hrv, sdrr_hrv, sport, sport_profile_name, stand_count, start_position_lat, start_position_long, start_time, sub_sport, swc_lat, swc_long, swim_stroke, threshold_power, time_standing, timestamp, total_anaerobic_training_effect, total_ascent, total_calories, total_cycles, total_descent, total_distance, total_elapsed_time, total_fractional_ascent, total_fractional_cycles, total_fractional_descent, total_grit, total_moving_time, total_timer_time, total_training_effect, total_work, training_load_peak, training_stress_score, trigger, workout_feel, workout_rpe |
| 19 | lap | active_time, avg_cadence, avg_cadence_position, avg_combined_pedal_smoothness, avg_flow, avg_fractional_cadence, avg_grade_adjusted_speed, avg_heart_rate, avg_left_pco, avg_left_pedal_smoothness, avg_left_power_phase, avg_left_power_phase_peak, avg_left_torque_effectiveness, avg_power, avg_power_position, avg_right_pco, avg_right_pedal_smoothness, avg_right_power_phase, avg_right_power_phase_peak, avg_right_torque_effectiveness, avg_stance_time, avg_stance_time_balance, avg_stance_time_percent, avg_step_length, avg_stroke_distance, avg_strokes_per_length, avg_swolf, avg_temperature, avg_vertical_oscillation, avg_vertical_ratio, end_position_lat, end_position_long, enhanced_avg_altitude, enhanced_avg_respiration_rate, enhanced_avg_speed, enhanced_max_altitude, enhanced_max_respiration_rate, enhanced_max_speed, enhanced_min_altitude, event, event_group, event_type, first_length_index, front_gear_shift_count, intensity, lap_trigger, left_right_balance, max_cadence, max_cadence_position, max_fractional_cadence, max_heart_rate, max_power, max_power_position, max_temperature, message_index, metabolic_calories, min_temperature, nec_lat, nec_long, normalized_power, num_active_lengths, num_lengths, rear_gear_shift_count, sport, stand_count, start_position_lat, start_position_long, start_time, sub_sport, swc_lat, swc_long, swim_stroke, time_standing, timestamp, total_ascent, total_calories, total_cycles, total_descent, total_distance, total_elapsed_time, total_fat_calories, total_fractional_ascent, total_fractional_cycles, total_fractional_descent, total_grit, total_moving_time, total_timer_time, total_work, wkt_step_index |
| 20 | record | current_stress, enhanced_respiration_rate, heart_rate, timestamp |
| 21 | event | activity_type, auto_activity_detect_duration, auto_activity_detect_start_timestamp, data, data16, event, event_group, event_type, timer_trigger, timestamp |
| 23 | device_info | ant_device_number, ant_network, ant_transmission_type, battery_level, battery_status, battery_voltage, cum_operating_time, device_index, device_type, garmin_product, hardware_version, local_device_type, manufacturer, product, sensor_position, serial_number, software_version, source_type, timestamp |
| 34 | activity | event, event_group, event_type, local_timestamp, num_sessions, timestamp, total_timer_time, type |
| 35 | software | version |
| 49 | file_creator | hardware_version, software_version |
| 55 | monitoring | active_calories, active_time, activity_type, ascent, current_activity_type_intensity, cycles, descent, distance, duration_min, heart_rate, intensity, moderate_activity_minutes, steps, timestamp, timestamp_16, vigorous_activity_minutes |
| 103 | monitoring_info | activity_type, cycles_to_calories, cycles_to_distance, local_timestamp, resting_metabolic_rate, timestamp |
| 104 | battery | capacity, timestamp |
| 162 | timestamp_correlation | local_timestamp, system_timestamp, timestamp |
| 188 | ohr_settings | enabled, timestamp |
| 211 | monitoring_hr_data | current_day_resting_heart_rate, resting_heart_rate, timestamp |
| 216 | time_in_zone | functional_threshold_power, hr_calc_type, hr_zone_high_boundary, max_heart_rate, power_zone_high_boundary, pwr_calc_type, reference_index, reference_mesg, resting_heart_rate, threshold_heart_rate, time_in_hr_zone, time_in_power_zone, timestamp |
| 227 | stress_level | stress_level_time, stress_level_value |
| 229 | max_met_data | calibrated_data, hr_source, max_met_category, speed_source, sport, sub_sport, update_time, vo2_max |
| 269 | spo2_data | mode, reading_confidence, reading_spo2, timestamp |
| 275 | sleep_level | sleep_level, timestamp |
| 297 | respiration_rate | respiration_rate, timestamp |
| 346 | sleep_assessment | average_stress_during_sleep, awake_time_score, awakenings_count, awakenings_count_score, combined_awake_score, deep_sleep_score, interruptions_score, light_sleep_score, overall_sleep_score, rem_sleep_score, sleep_duration_score, sleep_quality_score, sleep_recovery_score, sleep_restlessness_score |
| 370 | hrv_status_summary | baseline_balanced_lower, baseline_balanced_upper, baseline_low_upper, last_night_5_min_high, last_night_average, status, timestamp, weekly_average |
| 371 | hrv_value | timestamp, value |
| 398 | skin_temp_overnight | average_7_day_deviation, average_deviation, local_timestamp, nightly_value, timestamp |
| 412 | nap_event | end_time, end_timezone_offset, feedback, is_deleted, message_index, source, start_time, start_timezone_offset, timestamp, update_timestamp |
| 470 | sleep_disruption_severity_period | message_index, severity, timestamp |
| 471 | sleep_disruption_overnight_severity | severity, timestamp |

## Ograniczenia i decyzje

Pokrycie strukturalne (odczyt bajtów i wiadomości) i pokrycie semantyczne (znaczenie, jednostka, skala) to odrębne wyniki. Brak wyjątku parsera nie oznacza, że rozumiemy każdą metrykę. W szczególności wiele pól METRICS i niektóre serie WELLNESS pozostają identyfikatorami numerycznymi. Nie przypisujemy im nazw Body Battery, Training Readiness ani innych nazw na podstawie przypuszczeń.

Pliki ACTIVITY znaleziono wewnątrz otrzymanych ZIP. Zachowujemy je zgodnie z zasadą pełnego zachowania źródła. Dziewięć wystąpień nie stanowi dowodu pełnej historii treningów; osobne pobieranie aktywności pozostaje poza zakresem.

Tablice, nieważne wartości, subpola i komponenty wymagają reprezentacji bardziej ogólnej niż tabela z jednym zestawem kolumn zdrowotnych. Ustalony [schemat PostgreSQL](10-postgresql-schema.md) zachowuje fizyczne pola oraz osobny katalog ich interpretacji. Nie liczy własnych podsumowań zdrowotnych.

Rozmiar przyszłego eksportu JSON i bazy nie jest jeszcze zmierzony: raport obejmuje rozmiary źródeł. Baza i JSON będą miały narzut struktury; nie można utożsamić go z rozmiarem ZIP ani obiecać zmieszczenia szczegółowych 90 dni w kontekście AI.

Uzupełnienie z 2026-10-11: aplikacja zaimportowała całą tę historię. Baza po migracji indeksów zajmuje około 3,11 GB; zmierzony szczegółowy eksport dwóch parametrów z 90 dni — około 4,96 MB. Walidację implementacji i zakres tych pomiarów opisuje [instrukcja uruchamiania i testów](12-running-and-testing.md).

## Odtworzenie analizy

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt
.\.venv\Scripts\python.exe scripts/analyze_fit_inventory.py
.\.venv\Scripts\python.exe scripts/render_fit_inventory_docs.py
```

Raport szczegółowy: `data/fit_inventory.json` (ignorowany przez Git). Przejściowy checkpoint zawiera tylko metadane i jest usuwany po udanej analizie. Wyniki dla ograniczenia `--limit` służą wyłącznie próbie skryptu i nie zastępują pełnego skanu. Pełny katalog w dokumentacji: [09-fit-field-catalog.md](09-fit-field-catalog.md).
