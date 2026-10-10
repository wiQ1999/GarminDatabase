# Katalog pól FIT z całej pobranej historii

Wygenerowany przez `scripts/render_fit_inventory_docs.py` z lokalnego raportu `data/fit_inventory.json`. Nie zawiera wartości pomiarów. Nazwy i jednostki opisują pokrycie profilu, nie interpretację zdrowotną.

Zakres: 844 archiwa, 10994 wystąpień FIT; 1133 wariantów pól, w tym 4 rozwinięć parsera.

Wariant rozróżnia numer wiadomości, numer pola, przestrzeń deweloperską, nazwę i status rozwinięcia. To nie jest liczba niezależnych parametrów zdrowia. Kolumna „źródło” oznacza fizyczne pole, „rozwinięcie” — wynik reguły FIT. Liczby wystąpień obejmują również identyczne pliki obecne w kilku archiwach.

„Nieznane” oznacza brak publicznej semantyki w użytym profilu. Nazwa z nowszego SDK jest osobną kolumną, nie potwierdzeniem dekodowania przez fitdecode.

## 0: file_id

Nazwa w parserze strukturalnym: `file_id`.

Wiadomości: 10994. Kategorie: ACTIVITY, HRV_STATUS, METRICS, NAP, SKIN_TEMP, SLEEP_DATA, SLEEP_DISRUPTIONS, WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | type | type | — | enum | — | źródło | 10994 | 0 |
| 1 | manufacturer | manufacturer | — | uint16 | — | źródło | 10994 | 0 |
| 2 | garmin_product | product | — | uint16 | — | źródło | 10994 | 0 |
| 3 | serial_number | serial_number | — | uint32z | — | źródło | 10994 | 0 |
| 4 | time_created | time_created | — | uint32 | — | źródło | 10994 | 0 |
| 5 | number | number | — | uint16 | — | źródło | 10994 | 2978 |
| 6 | unknown_6 | — | — | uint16 | — | źródło | 4425 | 4425 |
| 7 | unknown_7 | — | — | uint32 | — | źródło | 2980 | 2980 |

## 2: device_settings

Nazwa w parserze strukturalnym: `device_settings`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | active_time_zone | active_time_zone | — | uint8 | — | źródło | 9 | 0 |
| 1 | utc_offset | utc_offset | — | uint32 | — | źródło | 9 | 0 |
| 2 | time_offset | time_offset | s | uint32 | — | źródło | 9 | 0 |
| 3 | unknown_3 | — | — | enum | — | źródło | 9 | 0 |
| 4 | time_mode | time_mode | — | enum | — | źródło | 9 | 0 |
| 5 | time_zone_offset | time_zone_offset | hr | sint8 | — | źródło | 9 | 0 |
| 8 | unknown_8 | — | — | uint16 | — | źródło | 9 | 9 |
| 9 | unknown_9 | — | — | enum | — | źródło | 9 | 9 |
| 10 | unknown_10 | — | — | enum | — | źródło | 9 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 9 | 0 |
| 12 | backlight_mode | backlight_mode | — | enum | — | źródło | 9 | 0 |
| 13 | unknown_13 | — | — | uint8 | — | źródło | 9 | 0 |
| 14 | unknown_14 | — | — | uint8 | — | źródło | 9 | 0 |
| 15 | unknown_15 | — | — | uint8 | — | źródło | 9 | 0 |
| 22 | unknown_22 | — | — | enum | — | źródło | 9 | 0 |
| 23 | unknown_23 | — | — | enum | — | źródło | 9 | 0 |
| 25 | unknown_25 | — | — | enum | — | źródło | 9 | 0 |
| 26 | unknown_26 | — | — | enum | — | źródło | 9 | 0 |
| 28 | unknown_28 | — | — | enum | — | źródło | 9 | 9 |
| 30 | unknown_30 | — | — | enum | — | źródło | 9 | 0 |
| 31 | unknown_31 | — | — | enum | — | źródło | 9 | 9 |
| 34 | unknown_34 | — | — | enum | — | źródło | 9 | 9 |
| 35 | unknown_35 | — | — | enum | — | źródło | 9 | 0 |
| 36 | activity_tracker_enabled | activity_tracker_enabled | — | enum | — | źródło | 9 | 0 |
| 38 | unknown_38 | — | — | enum | — | źródło | 9 | 0 |
| 41 | unknown_41 | — | — | enum | — | źródło | 9 | 0 |
| 42 | unknown_42 | — | — | enum | — | źródło | 9 | 0 |
| 43 | unknown_43 | — | — | enum | — | źródło | 9 | 0 |
| 44 | unknown_44 | — | — | enum | — | źródło | 9 | 9 |
| 45 | unknown_45 | — | — | enum | — | źródło | 9 | 0 |
| 46 | move_alert_enabled | move_alert_enabled | — | enum | — | źródło | 9 | 0 |
| 47 | date_mode | date_mode | — | enum | — | źródło | 9 | 0 |
| 48 | unknown_48 | — | — | enum | — | źródło | 9 | 0 |
| 49 | unknown_49 | — | — | uint16 | — | źródło | 9 | 9 |
| 53 | unknown_53 | — | — | enum | — | źródło | 9 | 0 |
| 54 | unknown_54 | — | — | enum | — | źródło | 9 | 9 |
| 55 | display_orientation | display_orientation | — | enum | — | źródło | 9 | 9 |
| 56 | mounting_side | mounting_side | — | enum | — | źródło | 9 | 0 |
| 58 | autosync_min_steps | autosync_min_steps | steps | uint16 | — | źródło | 9 | 0 |
| 59 | autosync_min_time | autosync_min_time | minutes | uint16 | — | źródło | 9 | 0 |
| 63 | unknown_63 | — | — | enum | 13 | źródło | 9 | 0 |
| 64 | unknown_64 | — | — | enum | — | źródło | 9 | 0 |
| 65 | unknown_65 | — | — | enum | — | źródło | 9 | 0 |
| 66 | unknown_66 | — | — | enum | — | źródło | 9 | 0 |
| 67 | unknown_67 | — | — | enum | — | źródło | 9 | 0 |
| 68 | unknown_68 | — | — | enum | — | źródło | 9 | 0 |
| 69 | unknown_69 | — | — | enum | — | źródło | 9 | 0 |
| 75 | unknown_75 | — | — | enum | — | źródło | 9 | 0 |
| 76 | unknown_76 | — | — | enum | — | źródło | 9 | 0 |
| 77 | unknown_77 | — | — | enum | — | źródło | 9 | 0 |
| 80 | lactate_threshold_autodetect_enabled | lactate_threshold_autodetect_enabled | — | enum | — | źródło | 9 | 0 |
| 81 | unknown_81 | — | — | enum | — | źródło | 9 | 0 |
| 82 | unknown_82 | — | — | enum | — | źródło | 9 | 0 |
| 83 | unknown_83 | — | — | enum | — | źródło | 9 | 0 |
| 84 | unknown_84 | — | — | enum | — | źródło | 9 | 0 |
| 85 | unknown_85 | — | — | enum | — | źródło | 9 | 0 |
| 87 | unknown_87 | — | — | enum | — | źródło | 9 | 0 |
| 90 | auto_activity_detect | auto_activity_detect | — | uint32 | — | źródło | 9 | 0 |
| 94 | number_of_screens | number_of_screens | — | uint8 | — | źródło | 9 | 9 |
| 97 | unknown_97 | — | — | uint8z | — | źródło | 9 | 0 |
| 98 | unknown_98 | — | — | enum | — | źródło | 9 | 0 |
| 101 | unknown_101 | — | — | enum | — | źródło | 9 | 0 |
| 104 | unknown_104 | — | — | enum | 40 | źródło | 9 | 0 |
| 107 | unknown_107 | — | — | enum | — | źródło | 9 | 0 |
| 108 | unknown_108 | — | — | enum | — | źródło | 9 | 0 |
| 109 | unknown_109 | — | — | enum | — | źródło | 9 | 0 |
| 110 | unknown_110 | — | — | enum | — | źródło | 9 | 0 |
| 111 | unknown_111 | — | — | enum | — | źródło | 9 | 0 |
| 112 | unknown_112 | — | — | enum | — | źródło | 9 | 0 |
| 116 | unknown_116 | — | — | enum | — | źródło | 9 | 0 |
| 117 | unknown_117 | — | — | enum | — | źródło | 9 | 0 |
| 124 | unknown_124 | — | — | uint8 | — | źródło | 9 | 0 |
| 125 | unknown_125 | — | — | uint8 | — | źródło | 9 | 0 |
| 126 | unknown_126 | — | — | enum | — | źródło | 9 | 0 |
| 127 | unknown_127 | — | — | enum | — | źródło | 9 | 0 |
| 128 | unknown_128 | — | — | enum | — | źródło | 9 | 0 |
| 129 | unknown_129 | — | — | enum | — | źródło | 9 | 0 |
| 130 | unknown_130 | — | — | enum | — | źródło | 9 | 0 |
| 131 | unknown_131 | — | — | enum | — | źródło | 9 | 0 |
| 132 | unknown_132 | — | — | enum | — | źródło | 9 | 0 |
| 133 | unknown_133 | — | — | enum | — | źródło | 9 | 0 |
| 135 | unknown_135 | — | — | enum | — | źródło | 9 | 0 |
| 137 | unknown_137 | — | — | enum | — | źródło | 9 | 0 |
| 138 | unknown_138 | — | — | enum | — | źródło | 9 | 0 |
| 139 | unknown_139 | — | — | enum | — | źródło | 9 | 0 |
| 141 | unknown_141 | — | — | uint8 | — | źródło | 9 | 0 |
| 142 | unknown_142 | — | — | uint8 | — | źródło | 9 | 0 |
| 143 | unknown_143 | — | — | uint8 | — | źródło | 9 | 0 |
| 144 | unknown_144 | — | — | enum | — | źródło | 9 | 0 |
| 145 | unknown_145 | — | — | enum | — | źródło | 9 | 0 |
| 148 | unknown_148 | — | — | enum | — | źródło | 9 | 0 |
| 149 | unknown_149 | — | — | enum | — | źródło | 9 | 0 |
| 151 | unknown_151 | — | — | enum | — | źródło | 9 | 0 |
| 159 | unknown_159 | — | — | enum | — | źródło | 9 | 0 |
| 160 | unknown_160 | — | — | enum | — | źródło | 9 | 0 |
| 161 | unknown_161 | — | — | enum | — | źródło | 9 | 0 |
| 162 | unknown_162 | — | — | enum | — | źródło | 9 | 0 |
| 163 | unknown_163 | — | — | enum | — | źródło | 9 | 0 |
| 164 | unknown_164 | — | — | uint8 | — | źródło | 9 | 0 |
| 165 | unknown_165 | — | — | enum | — | źródło | 9 | 0 |
| 167 | unknown_167 | — | — | string | — | źródło | 9 | 9 |
| 168 | unknown_168 | — | — | enum | — | źródło | 9 | 9 |
| 170 | unknown_170 | — | — | uint8 | 15 | źródło | 9 | 0 |
| 176 | unknown_176 | — | — | enum | — | źródło | 9 | 9 |
| 177 | unknown_177 | — | — | uint8 | — | źródło | 9 | 0 |
| 178 | unknown_178 | — | — | uint8 | — | źródło | 9 | 0 |
| 179 | unknown_179 | — | — | enum | — | źródło | 9 | 0 |
| 180 | unknown_180 | — | — | enum | — | źródło | 9 | 0 |
| 181 | unknown_181 | — | — | enum | — | źródło | 9 | 0 |
| 186 | unknown_186 | — | — | enum | — | źródło | 9 | 0 |
| 187 | unknown_187 | — | — | enum | — | źródło | 9 | 0 |
| 188 | unknown_188 | — | — | enum | — | źródło | 9 | 0 |
| 189 | unknown_189 | — | — | enum | — | źródło | 9 | 0 |
| 190 | unknown_190 | — | — | enum | — | źródło | 9 | 0 |
| 191 | unknown_191 | — | — | enum | — | źródło | 9 | 0 |
| 192 | unknown_192 | — | — | enum | — | źródło | 9 | 0 |
| 193 | unknown_193 | — | — | enum | — | źródło | 9 | 0 |
| 194 | unknown_194 | — | — | enum | — | źródło | 9 | 0 |
| 195 | unknown_195 | — | — | enum | — | źródło | 9 | 0 |
| 196 | unknown_196 | — | — | uint8z | — | źródło | 9 | 0 |
| 198 | unknown_198 | — | — | enum | — | źródło | 9 | 0 |
| 199 | unknown_199 | — | — | enum | — | źródło | 9 | 0 |
| 200 | unknown_200 | — | — | enum | — | źródło | 9 | 0 |
| 201 | unknown_201 | — | — | enum | — | źródło | 9 | 9 |
| 202 | unknown_202 | — | — | enum | — | źródło | 9 | 0 |
| 203 | unknown_203 | — | — | enum | — | źródło | 9 | 0 |
| 204 | unknown_204 | — | — | enum | — | źródło | 9 | 0 |
| 205 | unknown_205 | — | — | enum | — | źródło | 9 | 0 |
| 206 | unknown_206 | — | — | enum | — | źródło | 9 | 0 |
| 207 | unknown_207 | — | — | enum | — | źródło | 9 | 0 |
| 208 | unknown_208 | — | — | enum | — | źródło | 9 | 0 |
| 209 | unknown_209 | — | — | enum | — | źródło | 9 | 0 |
| 210 | unknown_210 | — | — | enum | — | źródło | 9 | 0 |
| 211 | unknown_211 | — | — | enum | — | źródło | 9 | 0 |
| 212 | unknown_212 | — | — | enum | — | źródło | 9 | 0 |
| 216 | unknown_216 | — | — | enum | — | źródło | 9 | 0 |
| 217 | unknown_217 | — | — | enum | — | źródło | 9 | 0 |
| 218 | unknown_218 | — | — | enum | — | źródło | 9 | 0 |
| 219 | unknown_219 | — | — | enum | — | źródło | 9 | 0 |
| 221 | unknown_221 | — | — | enum | — | źródło | 9 | 9 |
| 227 | unknown_227 | — | — | enum | — | źródło | 9 | 9 |
| 231 | unknown_231 | — | — | enum | — | źródło | 9 | 0 |
| 232 | unknown_232 | — | — | enum | — | źródło | 9 | 0 |
| 233 | unknown_233 | — | — | enum | — | źródło | 9 | 9 |
| 234 | unknown_234 | — | — | enum | — | źródło | 9 | 9 |
| 235 | unknown_235 | — | — | enum | — | źródło | 9 | 0 |
| 237 | unknown_237 | — | — | enum | — | źródło | 9 | 9 |
| 239 | unknown_239 | — | — | enum | — | źródło | 9 | 9 |
| 243 | unknown_243 | — | — | enum | — | źródło | 5 | 0 |
| 244 | unknown_244 | — | — | enum | — | źródło | 9 | 1 |

## 3: user_profile

Nazwa w parserze strukturalnym: `user_profile`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | gender | gender | — | enum | — | źródło | 9 | 0 |
| 3 | height | height | m | uint8 | — | źródło | 9 | 0 |
| 4 | weight | weight | kg | uint16 | — | źródło | 9 | 0 |
| 5 | language | language | — | enum | — | źródło | 9 | 0 |
| 6 | elev_setting | elev_setting | — | enum | — | źródło | 9 | 0 |
| 7 | weight_setting | weight_setting | — | enum | — | źródło | 9 | 0 |
| 8 | resting_heart_rate | resting_heart_rate | bpm | uint8 | — | źródło | 9 | 0 |
| 12 | hr_setting | hr_setting | — | enum | — | źródło | 9 | 0 |
| 13 | speed_setting | speed_setting | — | enum | — | źródło | 9 | 0 |
| 14 | dist_setting | dist_setting | — | enum | — | źródło | 9 | 0 |
| 17 | activity_class | activity_class | — | enum | — | źródło | 9 | 0 |
| 18 | position_setting | position_setting | — | enum | — | źródło | 9 | 0 |
| 21 | temperature_setting | temperature_setting | — | enum | — | źródło | 9 | 0 |
| 24 | unknown_24 | — | — | uint8 | — | źródło | 9 | 0 |
| 28 | wake_time | wake_time | — | uint32 | — | źródło | 9 | 0 |
| 29 | sleep_time | sleep_time | — | uint32 | — | źródło | 9 | 0 |
| 30 | height_setting | height_setting | — | enum | — | źródło | 9 | 0 |
| 31 | user_running_step_length | user_running_step_length | m | uint16 | — | źródło | 9 | 9 |
| 32 | user_walking_step_length | user_walking_step_length | m | uint16 | — | źródło | 9 | 9 |
| 33 | unknown_33 | — | — | uint16 | — | źródło | 9 | 9 |
| 36 | unknown_36 | — | — | uint8 | — | źródło | 9 | 0 |
| 37 | unknown_37 | — | — | uint16 | — | źródło | 9 | 0 |
| 38 | unknown_38 | — | — | uint16 | — | źródło | 9 | 9 |
| 41 | unknown_41 | — | — | uint32 | — | źródło | 9 | 5 |
| 42 | unknown_42 | — | — | uint32 | — | źródło | 9 | 9 |
| 43 | unknown_43 | — | — | enum | — | źródło | 9 | 0 |
| 44 | unknown_44 | — | — | uint8 | — | źródło | 9 | 0 |
| 45 | unknown_45 | — | — | uint8z | — | źródło | 9 | 0 |
| 47 | depth_setting | depth_setting | — | enum | — | źródło | 9 | 0 |
| 52 | unknown_52 | — | — | enum | — | źródło | 9 | 0 |
| 53 | unknown_53 | — | — | uint8 | — | źródło | 9 | 0 |
| 54 | unknown_54 | — | — | uint8 | — | źródło | 9 | 0 |
| 57 | unknown_57 | — | — | enum | — | źródło | 9 | 0 |
| 58 | unknown_58 | — | — | enum | — | źródło | 9 | 0 |
| 60 | unknown_60 | — | — | enum | 7 | źródło | 9 | 0 |
| 62 | unknown_62 | — | — | enum | — | źródło | 9 | 0 |
| 63 | unknown_63 | — | — | enum | — | źródło | 9 | 9 |
| 65 | unknown_65 | — | — | enum | — | źródło | 9 | 0 |
| 66 | unknown_66 | — | — | enum | — | źródło | 9 | 0 |
| 67 | unknown_67 | — | — | string | — | źródło | 9 | 5 |
| 68 | unknown_68 | — | — | enum | — | źródło | 5 | 5 |
| 69 | unknown_69 | — | — | enum | — | źródło | 4 | 4 |
| 70 | unknown_70 | — | — | uint8 | — | źródło | 4 | 0 |
| 71 | unknown_71 | — | — | enum | — | źródło | 1 | 0 |

## 7: zones_target

Nazwa w parserze strukturalnym: `zones_target`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | max_heart_rate | max_heart_rate | — | uint8 | — | źródło | 9 | 0 |
| 2 | threshold_heart_rate | threshold_heart_rate | — | uint8 | — | źródło | 9 | 0 |
| 3 | functional_threshold_power | functional_threshold_power | — | uint16 | — | źródło | 9 | 9 |
| 5 | hr_calc_type | hr_calc_type | — | enum | — | źródło | 9 | 0 |
| 7 | pwr_calc_type | pwr_calc_type | — | enum | — | źródło | 9 | 0 |
| 8 | unknown_8 | — | — | uint16 | — | źródło | 9 | 9 |
| 9 | unknown_9 | — | — | enum | — | źródło | 9 | 0 |
| 10 | unknown_10 | — | — | enum | — | źródło | 9 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 9 | 0 |
| 12 | unknown_12 | — | — | enum | — | źródło | 9 | 0 |
| 13 | unknown_13 | — | — | enum | — | źródło | 9 | 0 |
| 15 | unknown_15 | — | — | uint16 | — | źródło | 9 | 9 |
| 16 | unknown_16 | — | — | uint32 | — | źródło | 9 | 9 |
| 254 | unknown_254 | — | — | uint16 | — | źródło | 9 | 0 |

## 12: sport

Nazwa w parserze strukturalnym: `sport`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | sport | sport | — | enum | — | źródło | 9 | 0 |
| 1 | sub_sport | sub_sport | — | enum | — | źródło | 9 | 0 |
| 3 | name | name | — | string | — | źródło | 9 | 0 |
| 5 | unknown_5 | — | — | enum | — | źródło | 9 | 0 |
| 6 | unknown_6 | — | — | enum | — | źródło | 9 | 0 |
| 9 | unknown_9 | — | — | uint8 | — | źródło | 9 | 9 |
| 10 | unknown_10 | — | — | uint8 | 4 | źródło | 9 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 9 | 9 |
| 12 | unknown_12 | — | — | uint8 | — | źródło | 9 | 9 |
| 13 | unknown_13 | — | — | enum | — | źródło | 9 | 9 |
| 15 | unknown_15 | — | — | enum | — | źródło | 9 | 9 |
| 19 | unknown_19 | — | — | enum | 3 | źródło | 9 | 0 |
| 21 | unknown_21 | — | — | enum | — | źródło | 9 | 9 |

## 13: training_settings

Nazwa w parserze strukturalnym: `training_settings`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | unknown_1 | — | — | enum | — | źródło | 9 | 9 |
| 2 | unknown_2 | — | — | uint16 | — | źródło | 9 | 0 |
| 3 | unknown_3 | — | — | enum | — | źródło | 9 | 0 |
| 4 | unknown_4 | — | — | uint32 | — | źródło | 9 | 0 |
| 5 | unknown_5 | — | — | sint32 | — | źródło | 9 | 9 |
| 6 | unknown_6 | — | — | sint32 | — | źródło | 9 | 9 |
| 7 | unknown_7 | — | — | enum | — | źródło | 9 | 0 |
| 8 | unknown_8 | — | — | uint16 | — | źródło | 9 | 0 |
| 11 | unknown_11 | — | — | uint8 | — | źródło | 9 | 0 |
| 12 | unknown_12 | — | — | enum | — | źródło | 9 | 9 |
| 13 | unknown_13 | — | — | enum | — | źródło | 9 | 0 |
| 14 | unknown_14 | — | — | enum | — | źródło | 9 | 9 |
| 15 | unknown_15 | — | — | enum | — | źródło | 9 | 0 |
| 16 | unknown_16 | — | — | enum | — | źródło | 9 | 0 |
| 21 | unknown_21 | — | — | enum | — | źródło | 9 | 9 |
| 22 | unknown_22 | — | — | uint16 | — | źródło | 9 | 9 |
| 23 | unknown_23 | — | — | enum | — | źródło | 9 | 9 |
| 24 | unknown_24 | — | — | enum | — | źródło | 9 | 5 |
| 27 | unknown_27 | — | — | enum | — | źródło | 9 | 0 |
| 28 | unknown_28 | — | — | enum | — | źródło | 9 | 9 |
| 29 | unknown_29 | — | — | enum | — | źródło | 9 | 9 |
| 30 | unknown_30 | — | — | enum | — | źródło | 9 | 0 |
| 31 | target_distance | target_distance | m | uint32 | — | źródło | 9 | 9 |
| 32 | target_speed | target_speed | m/s | uint16 | — | źródło | 9 | 9 |
| 33 | target_time | target_time | s | uint32 | — | źródło | 9 | 9 |
| 34 | unknown_34 | — | — | enum | — | źródło | 9 | 9 |
| 35 | unknown_35 | — | — | enum | — | źródło | 9 | 9 |
| 36 | unknown_36 | — | — | enum | — | źródło | 9 | 9 |
| 37 | unknown_37 | — | — | enum | — | źródło | 9 | 9 |
| 38 | unknown_38 | — | — | uint8 | — | źródło | 9 | 9 |
| 39 | unknown_39 | — | — | uint8 | — | źródło | 9 | 9 |
| 40 | unknown_40 | — | — | enum | — | źródło | 9 | 9 |
| 41 | unknown_41 | — | — | sint32 | — | źródło | 9 | 0 |
| 42 | unknown_42 | — | — | uint8 | — | źródło | 9 | 9 |
| 43 | unknown_43 | — | — | enum | — | źródło | 9 | 9 |
| 44 | unknown_44 | — | — | enum | — | źródło | 9 | 9 |
| 45 | unknown_45 | — | — | enum | — | źródło | 9 | 9 |
| 46 | unknown_46 | — | — | enum | — | źródło | 9 | 9 |
| 47 | unknown_47 | — | — | enum | — | źródło | 9 | 9 |
| 48 | unknown_48 | — | — | enum | — | źródło | 9 | 9 |
| 51 | unknown_51 | — | — | enum | — | źródło | 9 | 9 |
| 52 | unknown_52 | — | — | uint16 | — | źródło | 9 | 9 |
| 53 | unknown_53 | — | — | enum | — | źródło | 9 | 9 |
| 54 | unknown_54 | — | — | uint32 | — | źródło | 9 | 9 |
| 55 | unknown_55 | — | — | enum | — | źródło | 9 | 9 |
| 57 | unknown_57 | — | — | enum | — | źródło | 9 | 9 |
| 60 | unknown_60 | — | — | enum | — | źródło | 9 | 9 |
| 62 | unknown_62 | — | — | enum | — | źródło | 9 | 9 |
| 63 | unknown_63 | — | — | enum | — | źródło | 9 | 9 |
| 64 | unknown_64 | — | — | uint16 | — | źródło | 9 | 9 |
| 65 | unknown_65 | — | — | enum | — | źródło | 9 | 0 |
| 66 | unknown_66 | — | — | enum | — | źródło | 9 | 9 |
| 68 | unknown_68 | — | — | sint32 | — | źródło | 9 | 9 |
| 71 | unknown_71 | — | — | enum | — | źródło | 9 | 9 |
| 72 | unknown_72 | — | — | enum | — | źródło | 9 | 9 |
| 73 | unknown_73 | — | — | sint32 | 4 | źródło | 9 | 0 |
| 74 | unknown_74 | — | — | sint32 | 4 | źródło | 9 | 0 |
| 75 | unknown_75 | — | — | enum | — | źródło | 9 | 9 |
| 76 | unknown_76 | — | — | enum | — | źródło | 9 | 0 |
| 78 | unknown_78 | — | — | enum | — | źródło | 9 | 9 |
| 79 | unknown_79 | — | — | enum | — | źródło | 9 | 9 |
| 81 | unknown_81 | — | — | enum | — | źródło | 9 | 9 |
| 82 | unknown_82 | — | — | enum | — | źródło | 9 | 9 |
| 83 | unknown_83 | — | — | enum | — | źródło | 9 | 9 |
| 85 | unknown_85 | — | — | enum | — | źródło | 9 | 9 |
| 86 | unknown_86 | — | — | uint8 | — | źródło | 9 | 9 |
| 87 | unknown_87 | — | — | enum | — | źródło | 9 | 9 |
| 88 | unknown_88 | — | — | enum | — | źródło | 9 | 9 |
| 89 | unknown_89 | — | — | enum | — | źródło | 9 | 9 |
| 90 | unknown_90 | — | — | uint32 | — | źródło | 9 | 9 |
| 93 | unknown_93 | — | — | enum | — | źródło | 9 | 9 |
| 94 | unknown_94 | — | — | enum | — | źródło | 9 | 9 |
| 95 | unknown_95 | — | — | enum | — | źródło | 9 | 9 |
| 96 | unknown_96 | — | — | enum | — | źródło | 9 | 0 |
| 97 | unknown_97 | — | — | enum | — | źródło | 9 | 0 |
| 98 | unknown_98 | — | — | enum | — | źródło | 9 | 0 |
| 99 | unknown_99 | — | — | enum | — | źródło | 9 | 9 |
| 100 | unknown_100 | — | — | uint32 | — | źródło | 9 | 9 |
| 101 | unknown_101 | — | — | uint32 | — | źródło | 9 | 9 |
| 102 | unknown_102 | — | — | enum | — | źródło | 9 | 9 |
| 103 | unknown_103 | — | — | enum | — | źródło | 9 | 0 |
| 104 | unknown_104 | — | — | enum | — | źródło | 9 | 9 |
| 105 | unknown_105 | — | — | enum | — | źródło | 9 | 0 |
| 106 | unknown_106 | — | — | enum | — | źródło | 9 | 0 |
| 107 | unknown_107 | — | — | enum | — | źródło | 9 | 9 |
| 108 | unknown_108 | — | — | enum | — | źródło | 9 | 9 |
| 109 | unknown_109 | — | — | enum | — | źródło | 9 | 9 |
| 110 | unknown_110 | — | — | enum | — | źródło | 9 | 9 |
| 112 | unknown_112 | — | — | enum | — | źródło | 9 | 9 |
| 113 | unknown_113 | — | — | enum | — | źródło | 9 | 9 |
| 114 | unknown_114 | — | — | uint16 | — | źródło | 9 | 9 |
| 115 | unknown_115 | — | — | uint32 | — | źródło | 9 | 9 |
| 116 | unknown_116 | — | — | enum | — | źródło | 9 | 9 |
| 120 | unknown_120 | — | — | enum | — | źródło | 9 | 9 |
| 121 | unknown_121 | — | — | enum | — | źródło | 9 | 0 |
| 123 | unknown_123 | — | — | uint32 | — | źródło | 9 | 9 |
| 125 | unknown_125 | — | — | enum | — | źródło | 9 | 9 |
| 254 | unknown_254 | — | — | uint16 | — | źródło | 9 | 0 |

## 18: session

Nazwa w parserze strukturalnym: `session`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | event | event | — | enum | — | źródło | 9 | 0 |
| 1 | event_type | event_type | — | enum | — | źródło | 9 | 0 |
| 2 | start_time | start_time | — | uint32 | — | źródło | 9 | 0 |
| 3 | start_position_lat | start_position_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 4 | start_position_long | start_position_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 5 | sport | sport | — | enum | — | źródło | 9 | 0 |
| 6 | sub_sport | sub_sport | — | enum | — | źródło | 9 | 0 |
| 7 | total_elapsed_time | total_elapsed_time | s | uint32 | — | źródło | 9 | 0 |
| 8 | total_timer_time | total_timer_time | s | uint32 | — | źródło | 9 | 0 |
| 9 | total_distance | total_distance | m | uint32 | — | źródło | 9 | 9 |
| 10 | total_cycles | total_cycles | cycles | uint32 | — | źródło | 9 | 9 |
| 11 | total_calories | total_calories | kcal | uint16 | — | źródło | 9 | 9 |
| 16 | avg_heart_rate | avg_heart_rate | bpm | uint8 | — | źródło | 9 | 0 |
| 17 | max_heart_rate | max_heart_rate | bpm | uint8 | — | źródło | 9 | 0 |
| 18 | avg_cadence | avg_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 19 | max_cadence | max_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 20 | avg_power | avg_power | watts | uint16 | — | źródło | 9 | 9 |
| 21 | max_power | max_power | watts | uint16 | — | źródło | 9 | 9 |
| 22 | total_ascent | total_ascent | m | uint16 | — | źródło | 9 | 9 |
| 23 | total_descent | total_descent | m | uint16 | — | źródło | 9 | 9 |
| 24 | total_training_effect | total_training_effect | — | uint8 | — | źródło | 9 | 0 |
| 25 | first_lap_index | first_lap_index | — | uint16 | — | źródło | 9 | 0 |
| 26 | num_laps | num_laps | — | uint16 | — | źródło | 9 | 0 |
| 27 | event_group | event_group | — | uint8 | — | źródło | 9 | 9 |
| 28 | trigger | trigger | — | enum | — | źródło | 9 | 0 |
| 29 | nec_lat | nec_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 30 | nec_long | nec_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 31 | swc_lat | swc_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 32 | swc_long | swc_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 33 | num_lengths | num_lengths | lengths | uint16 | — | źródło | 9 | 9 |
| 34 | normalized_power | normalized_power | watts | uint16 | — | źródło | 9 | 9 |
| 35 | training_stress_score | training_stress_score | tss | uint16 | — | źródło | 9 | 9 |
| 36 | intensity_factor | intensity_factor | if | uint16 | — | źródło | 9 | 9 |
| 37 | left_right_balance | left_right_balance | — | uint16 | — | źródło | 9 | 9 |
| 38 | end_position_lat | end_position_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 39 | end_position_long | end_position_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 41 | avg_stroke_count | avg_stroke_count | strokes/lap | uint32 | — | źródło | 9 | 9 |
| 42 | avg_stroke_distance | avg_stroke_distance | m | uint16 | — | źródło | 9 | 9 |
| 43 | swim_stroke | swim_stroke | swim_stroke | enum | — | źródło | 9 | 9 |
| 44 | pool_length | pool_length | m | uint16 | — | źródło | 9 | 9 |
| 45 | threshold_power | threshold_power | watts | uint16 | — | źródło | 9 | 9 |
| 46 | pool_length_unit | pool_length_unit | — | enum | — | źródło | 9 | 9 |
| 47 | num_active_lengths | num_active_lengths | lengths | uint16 | — | źródło | 9 | 9 |
| 48 | total_work | total_work | J | uint32 | — | źródło | 9 | 9 |
| 57 | avg_temperature | avg_temperature | C | sint8 | — | źródło | 9 | 9 |
| 58 | max_temperature | max_temperature | C | sint8 | — | źródło | 9 | 9 |
| 59 | total_moving_time | total_moving_time | s | uint32 | — | źródło | 9 | 9 |
| 78 | unknown_78 | active_time | s | uint32 | — | źródło | 9 | 9 |
| 79 | unknown_79 | avg_strokes_per_length | strokes/length | uint16 | — | źródło | 9 | 9 |
| 80 | unknown_80 | avg_swolf | — | uint16 | — | źródło | 9 | 9 |
| 81 | unknown_81 | — | — | enum | — | źródło | 9 | 0 |
| 89 | avg_vertical_oscillation | avg_vertical_oscillation | mm | uint16 | — | źródło | 9 | 9 |
| 90 | avg_stance_time_percent | avg_stance_time_percent | percent | uint16 | — | źródło | 9 | 9 |
| 91 | avg_stance_time | avg_stance_time | ms | uint16 | — | źródło | 9 | 9 |
| 92 | avg_fractional_cadence | avg_fractional_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 93 | max_fractional_cadence | max_fractional_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 94 | total_fractional_cycles | total_fractional_cycles | cycles | uint8 | — | źródło | 9 | 9 |
| 101 | avg_left_torque_effectiveness | avg_left_torque_effectiveness | percent | uint8 | — | źródło | 9 | 9 |
| 102 | avg_right_torque_effectiveness | avg_right_torque_effectiveness | percent | uint8 | — | źródło | 9 | 9 |
| 103 | avg_left_pedal_smoothness | avg_left_pedal_smoothness | percent | uint8 | — | źródło | 9 | 9 |
| 104 | avg_right_pedal_smoothness | avg_right_pedal_smoothness | percent | uint8 | — | źródło | 9 | 9 |
| 105 | avg_combined_pedal_smoothness | avg_combined_pedal_smoothness | percent | uint8 | — | źródło | 9 | 9 |
| 106 | unknown_106 | num_segment_laps | — | uint16 | — | źródło | 9 | 0 |
| 107 | unknown_107 | front_gear_shift_count | — | uint16 | — | źródło | 9 | 9 |
| 108 | unknown_108 | rear_gear_shift_count | — | uint16 | — | źródło | 9 | 9 |
| 109 | unknown_109 | — | — | uint8 | — | źródło | 9 | 9 |
| 110 | sport_profile_name | sport_profile_name | — | string | — | źródło | 9 | 0 |
| 112 | time_standing | time_standing | s | uint32 | — | źródło | 9 | 9 |
| 113 | stand_count | stand_count | — | uint16 | — | źródło | 9 | 9 |
| 114 | avg_left_pco | avg_left_pco | mm | sint8 | — | źródło | 9 | 9 |
| 115 | avg_right_pco | avg_right_pco | mm | sint8 | — | źródło | 9 | 9 |
| 116 | avg_left_power_phase | avg_left_power_phase | degrees | uint8 | 4 | źródło | 9 | 0 |
| 117 | avg_left_power_phase_peak | avg_left_power_phase_peak | degrees | uint8 | 4 | źródło | 9 | 0 |
| 118 | avg_right_power_phase | avg_right_power_phase | degrees | uint8 | 4 | źródło | 9 | 0 |
| 119 | avg_right_power_phase_peak | avg_right_power_phase_peak | degrees | uint8 | 4 | źródło | 9 | 0 |
| 120 | avg_power_position | avg_power_position | watts | uint16 | 2 | źródło | 9 | 0 |
| 121 | max_power_position | max_power_position | watts | uint16 | 2 | źródło | 9 | 0 |
| 122 | avg_cadence_position | avg_cadence_position | rpm | uint8 | 2 | źródło | 9 | 0 |
| 123 | max_cadence_position | max_cadence_position | rpm | uint8 | 2 | źródło | 9 | 0 |
| 124 | enhanced_avg_speed | enhanced_avg_speed | m/s | uint32 | — | źródło | 9 | 9 |
| 125 | enhanced_max_speed | enhanced_max_speed | m/s | uint32 | — | źródło | 9 | 9 |
| 132 | avg_vertical_ratio | avg_vertical_ratio | percent | uint16 | — | źródło | 9 | 9 |
| 133 | avg_stance_time_balance | avg_stance_time_balance | percent | uint16 | — | źródło | 9 | 9 |
| 134 | avg_step_length | avg_step_length | mm | uint16 | — | źródło | 9 | 9 |
| 137 | total_anaerobic_training_effect | total_anaerobic_training_effect | — | uint8 | — | źródło | 9 | 0 |
| 138 | unknown_138 | — | — | uint8 | 2 | źródło | 9 | 0 |
| 150 | min_temperature | min_temperature | C | sint8 | — | źródło | 9 | 9 |
| 151 | unknown_151 | — | — | uint16 | — | źródło | 9 | 0 |
| 152 | unknown_152 | — | — | uint32 | — | źródło | 9 | 0 |
| 157 | unknown_157 | — | — | uint16 | — | źródło | 9 | 9 |
| 158 | unknown_158 | — | — | uint16 | — | źródło | 9 | 9 |
| 168 | training_load_peak | training_load_peak | — | sint32 | — | źródło | 9 | 0 |
| 169 | enhanced_avg_respiration_rate | enhanced_avg_respiration_rate | Breaths/min | uint16 | — | źródło | 9 | 0 |
| 170 | enhanced_max_respiration_rate | enhanced_max_respiration_rate | Breaths/min | uint16 | — | źródło | 9 | 0 |
| 177 | unknown_177 | — | — | uint16 | — | źródło | 9 | 9 |
| 178 | unknown_178 | — | — | uint16 | — | źródło | 9 | 0 |
| 179 | unknown_179 | — | — | uint16 | — | źródło | 9 | 9 |
| 180 | enhanced_min_respiration_rate | enhanced_min_respiration_rate | — | uint16 | — | źródło | 9 | 0 |
| 181 | total_grit | total_grit | kGrit | float32 | — | źródło | 9 | 9 |
| 184 | unknown_184 | — | — | enum | — | źródło | 9 | 0 |
| 185 | unknown_185 | — | — | uint8 | — | źródło | 9 | 9 |
| 187 | avg_flow | avg_flow | Flow | float32 | — | źródło | 9 | 9 |
| 188 | unknown_188 | — | — | enum | — | źródło | 9 | 0 |
| 189 | unknown_189 | — | — | uint16 | — | źródło | 9 | 0 |
| 190 | unknown_190 | — | — | uint16 | — | źródło | 9 | 0 |
| 192 | workout_feel | workout_feel | — | uint8 | — | źródło | 9 | 9 |
| 193 | workout_rpe | workout_rpe | — | uint8 | — | źródło | 9 | 9 |
| 194 | avg_spo2 | avg_spo2 | percent | uint8 | — | źródło | 9 | 0 |
| 195 | avg_stress | avg_stress | percent | uint8 | — | źródło | 9 | 0 |
| 196 | unknown_196 | metabolic_calories | kcal | uint16 | — | źródło | 9 | 9 |
| 197 | sdrr_hrv | sdrr_hrv | mS | uint8 | — | źródło | 9 | 0 |
| 198 | rmssd_hrv | rmssd_hrv | mS | uint8 | — | źródło | 9 | 0 |
| 199 | total_fractional_ascent | total_fractional_ascent | m | uint8 | — | źródło | 9 | 9 |
| 200 | total_fractional_descent | total_fractional_descent | m | uint8 | — | źródło | 9 | 9 |
| 201 | unknown_201 | — | — | uint8 | — | źródło | 9 | 0 |
| 202 | unknown_202 | — | — | uint8 | — | źródło | 9 | 4 |
| 205 | unknown_205 | — | — | uint8 | — | źródło | 9 | 9 |
| 206 | unknown_206 | — | — | uint8 | — | źródło | 9 | 9 |
| 207 | unknown_207 | — | — | uint8 | — | źródło | 9 | 9 |
| 211 | unknown_211 | avg_grade_adjusted_speed | m/s | uint32 | — | źródło | 9 | 9 |
| 212 | unknown_212 | — | — | enum | — | źródło | 9 | 9 |
| 215 | unknown_215 | — | — | uint8 | — | źródło | 9 | 0 |
| 216 | unknown_216 | — | — | uint8 | — | źródło | 9 | 0 |
| 218 | unknown_218 | — | — | uint32 | — | źródło | 9 | 9 |
| 224 | unknown_224 | — | — | sint32 | — | źródło | 2 | 2 |
| 225 | unknown_225 | — | — | sint32 | — | źródło | 2 | 2 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 9 | 0 |
| 254 | message_index | message_index | — | uint16 | — | źródło | 9 | 0 |

## 19: lap

Nazwa w parserze strukturalnym: `lap`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | event | event | — | enum | — | źródło | 9 | 0 |
| 1 | event_type | event_type | — | enum | — | źródło | 9 | 0 |
| 2 | start_time | start_time | — | uint32 | — | źródło | 9 | 0 |
| 3 | start_position_lat | start_position_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 4 | start_position_long | start_position_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 5 | end_position_lat | end_position_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 6 | end_position_long | end_position_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 7 | total_elapsed_time | total_elapsed_time | s | uint32 | — | źródło | 9 | 0 |
| 8 | total_timer_time | total_timer_time | s | uint32 | — | źródło | 9 | 0 |
| 9 | total_distance | total_distance | m | uint32 | — | źródło | 9 | 9 |
| 10 | total_cycles | total_cycles | cycles | uint32 | — | źródło | 9 | 9 |
| 11 | total_calories | total_calories | kcal | uint16 | — | źródło | 9 | 9 |
| 12 | total_fat_calories | total_fat_calories | kcal | uint16 | — | źródło | 9 | 9 |
| 15 | avg_heart_rate | avg_heart_rate | bpm | uint8 | — | źródło | 9 | 0 |
| 16 | max_heart_rate | max_heart_rate | bpm | uint8 | — | źródło | 9 | 0 |
| 17 | avg_cadence | avg_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 18 | max_cadence | max_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 19 | avg_power | avg_power | watts | uint16 | — | źródło | 9 | 9 |
| 20 | max_power | max_power | watts | uint16 | — | źródło | 9 | 9 |
| 21 | total_ascent | total_ascent | m | uint16 | — | źródło | 9 | 9 |
| 22 | total_descent | total_descent | m | uint16 | — | źródło | 9 | 9 |
| 23 | intensity | intensity | — | enum | — | źródło | 9 | 0 |
| 24 | lap_trigger | lap_trigger | — | enum | — | źródło | 9 | 0 |
| 25 | sport | sport | — | enum | — | źródło | 9 | 0 |
| 26 | event_group | event_group | — | uint8 | — | źródło | 9 | 9 |
| 27 | unknown_27 | nec_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 28 | unknown_28 | nec_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 29 | unknown_29 | swc_lat | semicircles | sint32 | — | źródło | 9 | 9 |
| 30 | unknown_30 | swc_long | semicircles | sint32 | — | źródło | 9 | 9 |
| 32 | num_lengths | num_lengths | lengths | uint16 | — | źródło | 9 | 9 |
| 33 | normalized_power | normalized_power | watts | uint16 | — | źródło | 9 | 9 |
| 34 | left_right_balance | left_right_balance | — | uint16 | — | źródło | 9 | 9 |
| 35 | first_length_index | first_length_index | — | uint16 | — | źródło | 9 | 9 |
| 37 | avg_stroke_distance | avg_stroke_distance | m | uint16 | — | źródło | 9 | 9 |
| 38 | swim_stroke | swim_stroke | — | enum | — | źródło | 9 | 9 |
| 39 | sub_sport | sub_sport | — | enum | — | źródło | 9 | 0 |
| 40 | num_active_lengths | num_active_lengths | lengths | uint16 | — | źródło | 9 | 9 |
| 41 | total_work | total_work | J | uint32 | — | źródło | 9 | 9 |
| 50 | avg_temperature | avg_temperature | C | sint8 | — | źródło | 9 | 9 |
| 51 | max_temperature | max_temperature | C | sint8 | — | źródło | 9 | 9 |
| 52 | total_moving_time | total_moving_time | s | uint32 | — | źródło | 9 | 9 |
| 70 | unknown_70 | active_time | s | uint32 | — | źródło | 9 | 9 |
| 71 | wkt_step_index | wkt_step_index | — | uint16 | — | źródło | 9 | 9 |
| 72 | unknown_72 | — | — | enum | — | źródło | 9 | 9 |
| 73 | unknown_73 | avg_swolf | — | uint16 | — | źródło | 9 | 9 |
| 77 | avg_vertical_oscillation | avg_vertical_oscillation | mm | uint16 | — | źródło | 9 | 9 |
| 78 | avg_stance_time_percent | avg_stance_time_percent | percent | uint16 | — | źródło | 9 | 9 |
| 79 | avg_stance_time | avg_stance_time | ms | uint16 | — | źródło | 9 | 9 |
| 80 | avg_fractional_cadence | avg_fractional_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 81 | max_fractional_cadence | max_fractional_cadence | rpm | uint8 | — | źródło | 9 | 9 |
| 82 | total_fractional_cycles | total_fractional_cycles | cycles | uint8 | — | źródło | 9 | 9 |
| 90 | unknown_90 | avg_strokes_per_length | strokes / length | uint16 | — | źródło | 9 | 9 |
| 91 | avg_left_torque_effectiveness | avg_left_torque_effectiveness | percent | uint8 | — | źródło | 9 | 9 |
| 92 | avg_right_torque_effectiveness | avg_right_torque_effectiveness | percent | uint8 | — | źródło | 9 | 9 |
| 93 | avg_left_pedal_smoothness | avg_left_pedal_smoothness | percent | uint8 | — | źródło | 9 | 9 |
| 94 | avg_right_pedal_smoothness | avg_right_pedal_smoothness | percent | uint8 | — | źródło | 9 | 9 |
| 95 | avg_combined_pedal_smoothness | avg_combined_pedal_smoothness | percent | uint8 | — | źródło | 9 | 9 |
| 96 | unknown_96 | front_gear_shift_count | — | uint16 | — | źródło | 9 | 9 |
| 97 | unknown_97 | rear_gear_shift_count | — | uint16 | — | źródło | 9 | 9 |
| 98 | time_standing | time_standing | s | uint32 | — | źródło | 9 | 9 |
| 99 | stand_count | stand_count | — | uint16 | — | źródło | 9 | 9 |
| 100 | avg_left_pco | avg_left_pco | mm | sint8 | — | źródło | 9 | 9 |
| 101 | avg_right_pco | avg_right_pco | mm | sint8 | — | źródło | 9 | 9 |
| 102 | avg_left_power_phase | avg_left_power_phase | degrees | uint8 | 4 | źródło | 9 | 0 |
| 103 | avg_left_power_phase_peak | avg_left_power_phase_peak | degrees | uint8 | 4 | źródło | 9 | 0 |
| 104 | avg_right_power_phase | avg_right_power_phase | degrees | uint8 | 4 | źródło | 9 | 0 |
| 105 | avg_right_power_phase_peak | avg_right_power_phase_peak | degrees | uint8 | 4 | źródło | 9 | 0 |
| 106 | avg_power_position | avg_power_position | watts | uint16 | 2 | źródło | 9 | 0 |
| 107 | max_power_position | max_power_position | watts | uint16 | 2 | źródło | 9 | 0 |
| 108 | avg_cadence_position | avg_cadence_position | rpm | uint8 | 2 | źródło | 9 | 0 |
| 109 | max_cadence_position | max_cadence_position | rpm | uint8 | 2 | źródło | 9 | 0 |
| 110 | enhanced_avg_speed | enhanced_avg_speed | m/s | uint32 | — | źródło | 9 | 9 |
| 111 | enhanced_max_speed | enhanced_max_speed | m/s | uint32 | — | źródło | 9 | 9 |
| 112 | enhanced_avg_altitude | enhanced_avg_altitude | m | uint32 | — | źródło | 9 | 9 |
| 113 | enhanced_min_altitude | enhanced_min_altitude | m | uint32 | — | źródło | 9 | 9 |
| 114 | enhanced_max_altitude | enhanced_max_altitude | m | uint32 | — | źródło | 9 | 9 |
| 118 | avg_vertical_ratio | avg_vertical_ratio | percent | uint16 | — | źródło | 9 | 9 |
| 119 | avg_stance_time_balance | avg_stance_time_balance | percent | uint16 | — | źródło | 9 | 9 |
| 120 | avg_step_length | avg_step_length | mm | uint16 | — | źródło | 9 | 9 |
| 124 | min_temperature | min_temperature | C | sint8 | — | źródło | 9 | 9 |
| 125 | unknown_125 | — | — | uint16 | — | źródło | 9 | 9 |
| 126 | unknown_126 | — | — | uint16 | — | źródło | 9 | 9 |
| 136 | enhanced_avg_respiration_rate | enhanced_avg_respiration_rate | Breaths/min | uint16 | — | źródło | 9 | 0 |
| 137 | enhanced_max_respiration_rate | enhanced_max_respiration_rate | Breaths/min | uint16 | — | źródło | 9 | 0 |
| 143 | unknown_143 | — | — | uint16 | — | źródło | 9 | 9 |
| 145 | unknown_145 | — | — | uint16 | — | źródło | 9 | 0 |
| 149 | total_grit | total_grit | kGrit | float32 | — | źródło | 9 | 9 |
| 152 | unknown_152 | — | — | uint8 | — | źródło | 9 | 8 |
| 154 | avg_flow | avg_flow | Flow | float32 | — | źródło | 9 | 9 |
| 155 | unknown_155 | metabolic_calories | kcal | uint16 | — | źródło | 9 | 9 |
| 156 | total_fractional_ascent | total_fractional_ascent | m | uint8 | — | źródło | 9 | 9 |
| 157 | total_fractional_descent | total_fractional_descent | m | uint8 | — | źródło | 9 | 9 |
| 161 | unknown_161 | avg_grade_adjusted_speed | m/s | uint32 | — | źródło | 9 | 9 |
| 166 | unknown_166 | — | — | sint32 | — | źródło | 2 | 2 |
| 167 | unknown_167 | — | — | sint32 | — | źródło | 2 | 2 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 9 | 0 |
| 254 | message_index | message_index | — | uint16 | — | źródło | 9 | 0 |

## 20: record

Nazwa w parserze strukturalnym: `record`.

Wiadomości: 1086. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 3 | heart_rate | heart_rate | bpm | uint8 | — | źródło | 1086 | 0 |
| 108 | enhanced_respiration_rate | enhanced_respiration_rate | Breaths/min | uint16 | — | źródło | 1086 | 0 |
| 116 | current_stress | current_stress | — | uint16 | — | źródło | 1086 | 75 |
| 133 | unknown_133 | — | — | uint8 | — | źródło | 1086 | 152 |
| 134 | unknown_134 | — | — | uint8 | — | źródło | 1086 | 1086 |
| 135 | unknown_135 | — | — | uint8 | — | źródło | 1086 | 0 |
| 136 | unknown_136 | — | — | uint8 | — | źródło | 1086 | 0 |
| 143 | unknown_143 | — | — | uint8 | — | źródło | 1086 | 0 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 1086 | 0 |

## 21: event

Nazwa w parserze strukturalnym: `event`.

Wiadomości: 217794. Kategorie: ACTIVITY, SLEEP_DATA, WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | event | event | — | enum | — | źródło | 217794 | 0 |
| 1 | event_type | event_type | — | enum | — | źródło | 217794 | 0 |
| 2 | data16 | data16 | — | uint16 | — | źródło | 216100 | 0 |
| 3 | auto_activity_detect_duration | data | min | uint16 | — | rozwinięcie | 200627 | 0 |
| 3 | data | data | — | uint32 | — | rozwinięcie | 15473 | 0 |
| 3 | data | data | — | uint32 | — | źródło | 1676 | 0 |
| 3 | timer_trigger | data | — | uint32 | — | źródło | 18 | 0 |
| 4 | event_group | event_group | — | uint8 | — | źródło | 1694 | 1676 |
| 14 | activity_type | activity_type | — | enum | — | źródło | 200627 | 0 |
| 15 | auto_activity_detect_start_timestamp | start_timestamp | s | uint32 | — | źródło | 200627 | 0 |
| 16 | unknown_16 | — | — | enum | — | źródło | 200627 | 200555 |
| 19 | unknown_19 | — | — | uint8 | — | źródło | 1694 | 1694 |
| 20 | unknown_20 | — | — | uint8 | — | źródło | 1694 | 1694 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 217794 | 0 |

## 22: unknown_22

Nazwa w parserze strukturalnym: `unknown_22`.

Wiadomości: 847. Kategorie: ACTIVITY, HRV_STATUS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 847 | 847 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 847 | 847 |
| 2 | unknown_2 | — | — | uint8 | — | źródło | 847 | 847 |
| 3 | unknown_3 | — | — | uint8 | — | źródło | 847 | 847 |
| 4 | unknown_4 | — | — | uint8 | — | źródło | 847 | 0 |
| 5 | unknown_5 | — | — | enum | — | źródło | 847 | 847 |
| 6 | unknown_6 | — | — | uint8 | — | źródło | 847 | 847 |
| 8 | unknown_8 | — | — | uint8 | — | źródło | 847 | 847 |
| 14 | unknown_14 | — | — | uint8 | — | źródło | 847 | 847 |
| 15 | unknown_15 | — | — | uint8 | — | źródło | 847 | 847 |
| 16 | unknown_16 | — | — | uint8 | — | źródło | 847 | 847 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 847 | 0 |

## 23: device_info

Nazwa w parserze strukturalnym: `device_info`.

Wiadomości: 11910. Kategorie: ACTIVITY, HRV_STATUS, METRICS, NAP, SKIN_TEMP, SLEEP_DATA, SLEEP_DISRUPTIONS, WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | device_index | device_index | — | uint8 | — | źródło | 3896 | 2133 |
| 1 | device_type | device_type | — | uint8 | — | źródło | 2133 | 2133 |
| 1 | local_device_type | device_type | — | uint8 | — | źródło | 1763 | 856 |
| 2 | manufacturer | manufacturer | — | uint16 | — | źródło | 8321 | 873 |
| 3 | serial_number | serial_number | — | uint32z | — | źródło | 11910 | 907 |
| 4 | garmin_product | product | — | uint16 | — | źródło | 7448 | 0 |
| 4 | product | product | — | uint16 | — | źródło | 4462 | 871 |
| 5 | software_version | software_version | — | uint16 | — | źródło | 11910 | 853 |
| 6 | hardware_version | hardware_version | — | uint8 | — | źródło | 3896 | 3896 |
| 7 | cum_operating_time | cum_operating_time | s | uint32 | — | źródło | 3896 | 3896 |
| 8 | unknown_8 | — | — | uint32 | — | źródło | 3896 | 3896 |
| 9 | unknown_9 | — | — | uint8 | — | źródło | 3896 | 3896 |
| 10 | battery_voltage | battery_voltage | V | uint16 | — | źródło | 3896 | 3896 |
| 11 | battery_status | battery_status | — | uint8 | — | źródło | 3896 | 3896 |
| 13 | unknown_13 | — | — | uint16 | — | źródło | 3896 | 3896 |
| 15 | unknown_15 | — | — | uint32 | — | źródło | 3896 | 3896 |
| 16 | unknown_16 | — | — | uint32 | — | źródło | 3896 | 3896 |
| 17 | unknown_17 | — | — | string | — | źródło | 3896 | 3896 |
| 18 | sensor_position | sensor_position | — | enum | — | źródło | 3896 | 3896 |
| 20 | ant_transmission_type | ant_transmission_type | — | uint8z | — | źródło | 3896 | 3896 |
| 21 | ant_device_number | ant_device_number | — | uint16z | — | źródło | 3896 | 3896 |
| 22 | ant_network | ant_network | — | enum | — | źródło | 3896 | 3896 |
| 23 | unknown_23 | — | — | uint8 | — | źródło | 3896 | 3896 |
| 24 | unknown_24 | — | — | uint32z | — | źródło | 3896 | 3896 |
| 25 | source_type | source_type | — | enum | — | źródło | 3896 | 2133 |
| 29 | unknown_29 | — | — | uint8 | 6 | źródło | 3896 | 0 |
| 30 | unknown_30 | — | — | uint8 | — | źródło | 3896 | 3896 |
| 31 | unknown_31 | — | — | uint32 | — | źródło | 3896 | 3896 |
| 32 | battery_level | battery_level | % | uint8 | — | źródło | 3896 | 3896 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 11910 | 0 |

## 24: unknown_24

Nazwa w parserze strukturalnym: `unknown_24`.

Wiadomości: 753590. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 2 | unknown_2 | — | — | byte | 27 | źródło | 753590 | 0 |

## 34: activity

Nazwa w parserze strukturalnym: `activity`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | total_timer_time | total_timer_time | s | uint32 | — | źródło | 9 | 0 |
| 1 | num_sessions | num_sessions | — | uint16 | — | źródło | 9 | 0 |
| 2 | type | type | — | enum | — | źródło | 9 | 0 |
| 3 | event | event | — | enum | — | źródło | 9 | 0 |
| 4 | event_type | event_type | — | enum | — | źródło | 9 | 0 |
| 5 | local_timestamp | local_timestamp | — | uint32 | — | źródło | 9 | 0 |
| 6 | event_group | event_group | — | uint8 | — | źródło | 9 | 9 |
| 7 | unknown_7 | — | — | uint8 | — | źródło | 9 | 9 |
| 8 | unknown_8 | — | — | string | — | źródło | 9 | 9 |
| 253 | timestamp | timestamp | — | uint32 | — | źródło | 9 | 0 |

## 35: software

Nazwa w parserze strukturalnym: `software`.

Wiadomości: 4425. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 3 | version | version | — | uint16 | — | źródło | 4425 | 0 |

## 49: file_creator

Nazwa w parserze strukturalnym: `file_creator`.

Wiadomości: 6569. Kategorie: ACTIVITY, HRV_STATUS, METRICS, NAP, SKIN_TEMP, SLEEP_DATA, SLEEP_DISRUPTIONS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | software_version | software_version | — | uint16 | — | źródło | 6569 | 0 |
| 1 | hardware_version | hardware_version | — | uint8 | — | źródło | 2980 | 2980 |
| 2 | unknown_2 | — | — | string | — | źródło | 2980 | 2980 |
| 3 | unknown_3 | — | — | enum | — | źródło | 6569 | 2980 |
| 4 | unknown_4 | — | — | enum | — | źródło | 6569 | 2980 |

## 55: monitoring

Nazwa w parserze strukturalnym: `monitoring`.

Wiadomości: 1323982. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 2 | distance | distance | m | uint32 | — | źródło | 14550 | 0 |
| 3 | cycles | cycles | cycles | uint32 | — | źródło | 70999 | 0 |
| 3 | steps | cycles | steps | uint32 | — | źródło | 9315 | 0 |
| 4 | active_time | active_time | s | uint32 | — | źródło | 80314 | 0 |
| 5 | activity_type | activity_type | — | enum | — | źródło | 12902 | 0 |
| 5 | activity_type | activity_type | — | enum | — | rozwinięcie | 296393 | 0 |
| 19 | active_calories | active_calories | kcal | uint16 | — | źródło | 80098 | 0 |
| 24 | current_activity_type_intensity | current_activity_type_intensity | , | byte | 1 | źródło | 296393 | 0 |
| 26 | timestamp_16 | timestamp_16 | s | uint16 | — | źródło | 1064401 | 0 |
| 27 | heart_rate | heart_rate | bpm | uint8 | — | źródło | 973061 | 0 |
| 28 | intensity | intensity | — | uint8 | — | rozwinięcie | 296393 | 0 |
| 29 | duration_min | duration_min | min | uint16 | — | źródło | 12902 | 0 |
| 31 | ascent | ascent | m | uint32 | — | źródło | 10206 | 0 |
| 32 | descent | descent | m | uint32 | — | źródło | 11389 | 0 |
| 33 | moderate_activity_minutes | moderate_activity_minutes | minutes | uint16 | — | źródło | 2112 | 0 |
| 34 | vigorous_activity_minutes | vigorous_activity_minutes | minutes | uint16 | — | źródło | 667 | 0 |
| 35 | unknown_35 | — | — | uint32 | — | źródło | 19055 | 0 |
| 36 | unknown_36 | — | — | uint32 | — | źródło | 20238 | 0 |
| 37 | unknown_37 | — | — | uint16 | — | źródło | 10961 | 0 |
| 38 | unknown_38 | — | — | uint16 | — | źródło | 9516 | 0 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 259581 | 0 |

## 79: unknown_79

Nazwa w parserze strukturalnym: `unknown_79`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint16 | — | źródło | 9 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 9 | 0 |
| 2 | unknown_2 | — | — | uint8 | — | źródło | 9 | 0 |
| 3 | unknown_3 | — | — | uint16 | — | źródło | 9 | 0 |
| 4 | unknown_4 | — | — | enum | — | źródło | 9 | 0 |
| 5 | unknown_5 | — | — | enum | — | źródło | 9 | 0 |
| 6 | unknown_6 | — | — | uint8 | — | źródło | 9 | 0 |
| 7 | unknown_7 | — | — | sint8 | — | źródło | 9 | 0 |
| 8 | unknown_8 | — | — | uint16 | — | źródło | 9 | 0 |
| 9 | unknown_9 | — | — | uint16 | — | źródło | 9 | 0 |
| 10 | unknown_10 | — | — | uint8 | — | źródło | 9 | 0 |
| 11 | unknown_11 | — | — | uint16 | — | źródło | 9 | 0 |
| 12 | unknown_12 | — | — | uint16 | — | źródło | 9 | 0 |
| 13 | unknown_13 | — | — | uint16 | — | źródło | 9 | 0 |
| 14 | unknown_14 | — | — | uint8 | — | źródło | 9 | 0 |
| 15 | unknown_15 | — | — | uint8 | — | źródło | 9 | 0 |
| 16 | unknown_16 | — | — | uint32 | — | źródło | 9 | 0 |
| 17 | unknown_17 | — | — | sint32 | — | źródło | 9 | 0 |
| 18 | unknown_18 | — | — | sint32 | — | źródło | 9 | 0 |
| 19 | unknown_19 | — | — | sint32 | — | źródło | 9 | 0 |
| 20 | unknown_20 | — | — | uint16 | — | źródło | 9 | 0 |
| 21 | unknown_21 | — | — | sint32 | — | źródło | 9 | 0 |
| 22 | unknown_22 | — | — | sint32 | — | źródło | 9 | 0 |
| 23 | unknown_23 | — | — | sint16 | — | źródło | 9 | 0 |
| 25 | unknown_25 | — | — | uint32 | — | źródło | 9 | 0 |
| 26 | unknown_26 | — | — | uint32 | — | źródło | 9 | 0 |
| 27 | unknown_27 | — | — | uint8 | — | źródło | 9 | 0 |
| 28 | unknown_28 | — | — | uint8 | — | źródło | 9 | 0 |
| 29 | unknown_29 | — | — | uint32 | — | źródło | 9 | 0 |
| 30 | unknown_30 | — | — | uint32 | — | źródło | 9 | 0 |
| 31 | unknown_31 | — | — | uint8 | — | źródło | 9 | 0 |
| 32 | unknown_32 | — | — | uint8 | — | źródło | 9 | 0 |
| 33 | unknown_33 | — | — | uint16 | — | źródło | 9 | 0 |
| 34 | unknown_34 | — | — | uint16 | — | źródło | 9 | 0 |
| 35 | unknown_35 | — | — | uint32 | — | źródło | 9 | 0 |
| 36 | unknown_36 | — | — | sint32 | — | źródło | 9 | 0 |
| 37 | unknown_37 | — | — | sint16 | — | źródło | 9 | 0 |
| 38 | unknown_38 | — | — | uint16 | — | źródło | 9 | 0 |
| 39 | unknown_39 | — | — | uint32 | — | źródło | 9 | 0 |
| 40 | unknown_40 | — | — | enum | — | źródło | 9 | 0 |
| 41 | unknown_41 | — | — | uint8 | — | źródło | 9 | 0 |
| 42 | unknown_42 | — | — | uint8 | — | źródło | 9 | 0 |
| 44 | unknown_44 | — | — | enum | — | źródło | 4 | 0 |
| 45 | unknown_45 | — | — | enum | — | źródło | 4 | 4 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 9 | 0 |

## 103: monitoring_info

Nazwa w parserze strukturalnym: `monitoring_info`.

Wiadomości: 4446. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | local_timestamp | local_timestamp | s | uint32 | — | źródło | 4446 | 0 |
| 1 | activity_type | activity_type | — | enum | 2 | źródło | 4446 | 0 |
| 3 | cycles_to_distance | cycles_to_distance | m/cycle | uint16 | 2 | źródło | 4446 | 0 |
| 4 | cycles_to_calories | cycles_to_calories | kcal/cycle | uint16 | 2 | źródło | 4446 | 0 |
| 5 | resting_metabolic_rate | resting_metabolic_rate | kcal/day | uint16 | — | źródło | 4446 | 0 |
| 7 | unknown_7 | — | — | uint32 | 2 | źródło | 4446 | 0 |
| 8 | unknown_8 | — | — | enum | — | źródło | 4446 | 4446 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 4446 | 0 |

## 104: battery

Nazwa w parserze strukturalnym: `unknown_104`.

Wiadomości: 3. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint16 | — | źródło | 3 | 0 |
| 2 | unknown_2 | capacity | % | uint8 | — | źródło | 3 | 0 |
| 3 | unknown_3 | — | — | sint8 | — | źródło | 3 | 0 |
| 4 | unknown_4 | — | — | sint32 | — | źródło | 3 | 0 |
| 253 | unknown_253 | timestamp | — | uint32 | — | źródło | 3 | 0 |

## 140: unknown_140

Nazwa w parserze strukturalnym: `unknown_140`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 9 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 9 | 0 |
| 2 | unknown_2 | — | — | sint32 | — | źródło | 9 | 0 |
| 3 | unknown_3 | — | — | sint32 | — | źródło | 9 | 0 |
| 4 | unknown_4 | — | — | uint8 | — | źródło | 9 | 0 |
| 5 | unknown_5 | — | — | sint32 | — | źródło | 9 | 0 |
| 6 | unknown_6 | — | — | sint32 | — | źródło | 9 | 9 |
| 7 | unknown_7 | — | — | sint32 | — | źródło | 9 | 0 |
| 8 | unknown_8 | — | — | sint8 | — | źródło | 9 | 0 |
| 9 | unknown_9 | — | — | uint16 | — | źródło | 9 | 0 |
| 10 | unknown_10 | — | — | uint16 | — | źródło | 9 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 9 | 0 |
| 12 | unknown_12 | — | — | enum | — | źródło | 9 | 0 |
| 13 | unknown_13 | — | — | uint8 | — | źródło | 9 | 0 |
| 14 | unknown_14 | — | — | uint16 | — | źródło | 5 | 0 |
| 15 | unknown_15 | — | — | uint16 | — | źródło | 5 | 0 |
| 16 | unknown_16 | — | — | uint16 | — | źródło | 5 | 0 |
| 17 | unknown_17 | — | — | sint8 | — | źródło | 9 | 0 |
| 18 | unknown_18 | — | — | uint8 | — | źródło | 9 | 0 |
| 19 | unknown_19 | — | — | uint8 | — | źródło | 9 | 0 |
| 20 | unknown_20 | — | — | uint8 | — | źródło | 9 | 0 |
| 21 | unknown_21 | — | — | sint32 | — | źródło | 9 | 0 |
| 22 | unknown_22 | — | — | uint8 | — | źródło | 9 | 0 |
| 23 | unknown_23 | — | — | uint8 | — | źródło | 9 | 0 |
| 24 | unknown_24 | — | — | sint32 | — | źródło | 9 | 0 |
| 25 | unknown_25 | — | — | uint8 | — | źródło | 9 | 0 |
| 26 | unknown_26 | — | — | sint32 | — | źródło | 9 | 0 |
| 27 | unknown_27 | — | — | sint32 | — | źródło | 9 | 0 |
| 28 | unknown_28 | — | — | sint32 | — | źródło | 9 | 0 |
| 29 | unknown_29 | — | — | sint32 | — | źródło | 9 | 0 |
| 30 | unknown_30 | — | — | sint8 | — | źródło | 9 | 0 |
| 31 | unknown_31 | — | — | sint8 | — | źródło | 9 | 0 |
| 32 | unknown_32 | — | — | sint32 | — | źródło | 9 | 0 |
| 33 | unknown_33 | — | — | uint8 | — | źródło | 9 | 0 |
| 34 | unknown_34 | — | — | enum | — | źródło | 9 | 0 |
| 35 | unknown_35 | — | — | uint32 | — | źródło | 9 | 0 |
| 36 | unknown_36 | — | — | uint32 | — | źródło | 9 | 0 |
| 37 | unknown_37 | — | — | sint32 | — | źródło | 9 | 0 |
| 38 | unknown_38 | — | — | sint32 | — | źródło | 9 | 0 |
| 39 | unknown_39 | — | — | sint32 | — | źródło | 9 | 0 |
| 40 | unknown_40 | — | — | sint32 | — | źródło | 9 | 0 |
| 41 | unknown_41 | — | — | enum | — | źródło | 9 | 0 |
| 42 | unknown_42 | — | — | uint8 | — | źródło | 9 | 9 |
| 43 | unknown_43 | — | — | sint16 | — | źródło | 9 | 0 |
| 44 | unknown_44 | — | — | sint16 | — | źródło | 9 | 0 |
| 45 | unknown_45 | — | — | sint16 | — | źródło | 9 | 0 |
| 46 | unknown_46 | — | — | uint8 | — | źródło | 9 | 0 |
| 48 | unknown_48 | — | — | uint32 | — | źródło | 9 | 0 |
| 49 | unknown_49 | — | — | uint8 | — | źródło | 9 | 0 |
| 50 | unknown_50 | — | — | uint8 | — | źródło | 9 | 0 |
| 51 | unknown_51 | — | — | enum | — | źródło | 9 | 0 |
| 52 | unknown_52 | — | — | enum | — | źródło | 9 | 9 |
| 53 | unknown_53 | — | — | uint8 | — | źródło | 9 | 0 |
| 54 | unknown_54 | — | — | sint32 | — | źródło | 9 | 0 |
| 55 | unknown_55 | — | — | uint16 | — | źródło | 9 | 0 |
| 56 | unknown_56 | — | — | uint8 | — | źródło | 9 | 0 |
| 57 | unknown_57 | — | — | uint16 | — | źródło | 9 | 9 |
| 58 | unknown_58 | — | — | uint16 | — | źródło | 9 | 9 |
| 59 | unknown_59 | — | — | enum | — | źródło | 9 | 0 |
| 60 | unknown_60 | — | — | uint16 | — | źródło | 9 | 9 |
| 61 | unknown_61 | — | — | uint16 | — | źródło | 9 | 9 |
| 62 | unknown_62 | — | — | uint16 | — | źródło | 9 | 9 |
| 63 | unknown_63 | — | — | uint8 | — | źródło | 9 | 0 |
| 64 | unknown_64 | — | — | uint8 | — | źródło | 9 | 0 |
| 65 | unknown_65 | — | — | uint8 | — | źródło | 4 | 0 |
| 66 | unknown_66 | — | — | uint16 | — | źródło | 4 | 0 |
| 67 | unknown_67 | — | — | uint16 | — | źródło | 4 | 0 |
| 68 | unknown_68 | — | — | uint16 | — | źródło | 4 | 4 |
| 69 | unknown_69 | — | — | uint16 | — | źródło | 9 | 9 |
| 70 | unknown_70 | — | — | uint16 | — | źródło | 9 | 9 |
| 71 | unknown_71 | — | — | uint16 | — | źródło | 9 | 9 |
| 72 | unknown_72 | — | — | uint16 | — | źródło | 9 | 9 |
| 73 | unknown_73 | — | — | uint16 | — | źródło | 4 | 4 |
| 74 | unknown_74 | — | — | uint16 | — | źródło | 4 | 4 |
| 75 | unknown_75 | — | — | uint16 | — | źródło | 4 | 4 |
| 76 | unknown_76 | — | — | uint16 | — | źródło | 4 | 4 |
| 77 | unknown_77 | — | — | uint16 | — | źródło | 4 | 4 |
| 78 | unknown_78 | — | — | sint32 | — | źródło | 4 | 4 |
| 79 | unknown_79 | — | — | uint8 | — | źródło | 4 | 4 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 9 | 0 |

## 141: unknown_141

Nazwa w parserze strukturalnym: `unknown_141`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | enum | — | źródło | 9 | 0 |
| 1 | unknown_1 | — | — | uint32 | — | źródło | 9 | 9 |
| 2 | unknown_2 | — | — | uint32 | — | źródło | 9 | 9 |
| 3 | unknown_3 | — | — | uint32 | — | źródło | 9 | 9 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 9 | 0 |

## 162: timestamp_correlation

Nazwa w parserze strukturalnym: `timestamp_correlation`.

Wiadomości: 3793. Kategorie: ACTIVITY, HRV_STATUS, SKIN_TEMP, SLEEP_DISRUPTIONS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | system_timestamp | system_timestamp | s | uint32 | — | źródło | 3453 | 1496 |
| 3 | local_timestamp | local_timestamp | s | uint32 | — | źródło | 3793 | 0 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 3793 | 0 |

## 188: ohr_settings

Nazwa w parserze strukturalnym: `ohr_settings`.

Wiadomości: 8139. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | enabled | enabled | — | enum | — | źródło | 8139 | 0 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 8139 | 0 |

## 211: monitoring_hr_data

Nazwa w parserze strukturalnym: `monitoring_hr_data`.

Wiadomości: 7915. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | resting_heart_rate | resting_heart_rate | bpm | uint8 | — | źródło | 7915 | 0 |
| 1 | current_day_resting_heart_rate | current_day_resting_heart_rate | bpm | uint8 | — | źródło | 7915 | 0 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 7915 | 0 |

## 216: time_in_zone

Nazwa w parserze strukturalnym: `time_in_zone`.

Wiadomości: 18. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | reference_mesg | reference_mesg | — | uint16 | — | źródło | 18 | 0 |
| 1 | reference_index | reference_index | — | uint16 | — | źródło | 18 | 0 |
| 2 | time_in_hr_zone | time_in_hr_zone | s | uint32 | 7 | źródło | 18 | 0 |
| 5 | time_in_power_zone | time_in_power_zone | s | uint32 | 8 | źródło | 18 | 0 |
| 6 | hr_zone_high_boundary | hr_zone_high_boundary | bpm | uint8 | 6 | źródło | 18 | 0 |
| 9 | power_zone_high_boundary | power_zone_high_boundary | watts | uint16 | 8 | źródło | 18 | 0 |
| 10 | hr_calc_type | hr_calc_type | — | enum | — | źródło | 18 | 0 |
| 11 | max_heart_rate | max_heart_rate | — | uint8 | — | źródło | 18 | 0 |
| 12 | resting_heart_rate | resting_heart_rate | — | uint8 | — | źródło | 18 | 0 |
| 13 | threshold_heart_rate | threshold_heart_rate | — | uint8 | — | źródło | 18 | 0 |
| 14 | pwr_calc_type | pwr_calc_type | — | enum | — | źródło | 18 | 18 |
| 15 | functional_threshold_power | functional_threshold_power | — | uint16 | — | źródło | 18 | 18 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 18 | 0 |

## 227: stress_level

Nazwa w parserze strukturalnym: `stress_level`.

Wiadomości: 1186826. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | stress_level_value | stress_level_value | — | sint16 | — | źródło | 1186826 | 0 |
| 1 | stress_level_time | stress_level_time | s | uint32 | — | źródło | 1186826 | 0 |
| 2 | unknown_2 | — | — | sint8 | — | źródło | 1186826 | 0 |
| 3 | unknown_3 | — | — | sint8 | — | źródło | 1186826 | 2841 |
| 4 | unknown_4 | — | — | sint8 | — | źródło | 1186826 | 0 |

## 229: max_met_data

Nazwa w parserze strukturalnym: `max_met_data`.

Wiadomości: 32. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | update_time | update_time | — | uint32 | — | źródło | 32 | 0 |
| 1 | unknown_1 | — | — | sint32 | — | źródło | 32 | 0 |
| 2 | vo2_max | vo2_max | mL/kg/min | uint16 | — | źródło | 32 | 0 |
| 5 | sport | sport | — | enum | — | źródło | 32 | 0 |
| 6 | sub_sport | sub_sport | — | enum | — | źródło | 32 | 0 |
| 8 | max_met_category | max_met_category | — | enum | — | źródło | 32 | 0 |
| 9 | calibrated_data | calibrated_data | — | enum | — | źródło | 32 | 0 |
| 10 | unknown_10 | — | — | sint32 | — | źródło | 32 | 0 |
| 11 | unknown_11 | — | — | sint32 | — | źródło | 32 | 0 |
| 12 | hr_source | hr_source | — | enum | — | źródło | 32 | 0 |
| 13 | speed_source | speed_source | — | enum | — | źródło | 32 | 0 |
| 14 | unknown_14 | — | — | uint16 | — | źródło | 32 | 0 |

## 232: unknown_232

Nazwa w parserze strukturalnym: `unknown_232`.

Wiadomości: 1130. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | enum | — | źródło | 293 | 0 |
| 1 | unknown_1 | — | — | enum | — | źródło | 293 | 0 |
| 2 | unknown_2 | — | — | enum | — | źródło | 1130 | 0 |
| 3 | unknown_3 | — | — | enum | — | źródło | 1124 | 0 |
| 9 | unknown_9 | — | — | enum | — | źródło | 1124 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 1130 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1130 | 0 |

## 233: unknown_233

Nazwa w parserze strukturalnym: `unknown_233`.

Wiadomości: 1215938. Kategorie: ACTIVITY, WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 2 | unknown_2 | — | — | byte | 4 | źródło | 1215938 | 0 |

## 241: unknown_241

Nazwa w parserze strukturalnym: `unknown_241`.

Wiadomości: 3591. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint32 | — | źródło | 3591 | 0 |
| 1 | unknown_1 | — | — | enum | — | źródło | 3591 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 3591 | 0 |

## 269: spo2_data

Nazwa w parserze strukturalnym: `spo2_data`.

Wiadomości: 400155. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | reading_spo2 | reading_spo2 | percent | uint8 | — | źródło | 400155 | 711 |
| 1 | reading_confidence | reading_confidence | — | uint8 | — | źródło | 400155 | 0 |
| 2 | mode | mode | — | uint8 | — | źródło | 400155 | 0 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 400155 | 0 |

## 273: unknown_273

Nazwa w parserze strukturalnym: `unknown_273`.

Wiadomości: 838. Kategorie: SLEEP_DATA.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 838 | 0 |
| 1 | unknown_1 | — | — | uint16 | — | źródło | 838 | 0 |
| 2 | unknown_2 | — | — | uint32 | — | źródło | 838 | 0 |
| 3 | unknown_3 | — | — | enum | — | źródło | 838 | 0 |
| 4 | unknown_4 | — | — | string | — | źródło | 838 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 838 | 0 |

## 275: sleep_level

Nazwa w parserze strukturalnym: `sleep_level`.

Wiadomości: 15218. Kategorie: SLEEP_DATA.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | sleep_level | sleep_level | — | enum | — | źródło | 15218 | 0 |
| 253 | timestamp | timestamp | s | uint32 | — | źródło | 15218 | 0 |

## 279: unknown_279

Nazwa w parserze strukturalnym: `unknown_279`.

Wiadomości: 605020. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint32 | — | źródło | 605020 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 605020 | 0 |

## 281: unknown_281

Nazwa w parserze strukturalnym: `unknown_281`.

Wiadomości: 1872. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint32 | — | źródło | 44 | 2 |
| 1 | unknown_1 | — | — | uint32 | — | źródło | 476 | 0 |
| 2 | unknown_2 | — | — | uint32 | — | źródło | 460 | 1 |
| 3 | unknown_3 | — | — | uint32 | — | źródło | 42 | 2 |
| 4 | unknown_4 | — | — | uint16 | — | źródło | 1872 | 0 |
| 5 | unknown_5 | — | — | uint16 | — | źródło | 1872 | 0 |
| 6 | unknown_6 | — | — | uint8 | — | źródło | 1872 | 0 |
| 7 | unknown_7 | — | — | enum | — | źródło | 476 | 0 |
| 8 | unknown_8 | — | — | enum | — | źródło | 44 | 2 |
| 9 | unknown_9 | — | — | uint8 | — | źródło | 1872 | 0 |
| 10 | unknown_10 | — | — | uint8 | — | źródło | 1872 | 0 |
| 11 | unknown_11 | — | — | uint16 | — | źródło | 1872 | 0 |
| 12 | unknown_12 | — | — | uint8 | — | źródło | 1872 | 0 |
| 13 | unknown_13 | — | — | uint16 | — | źródło | 1872 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1872 | 0 |

## 284: unknown_284

Nazwa w parserze strukturalnym: `unknown_284`.

Wiadomości: 1070. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint16 | — | źródło | 1070 | 0 |
| 1 | unknown_1 | — | — | uint32 | — | źródło | 1070 | 0 |
| 2 | unknown_2 | — | — | sint16 | — | źródło | 1070 | 0 |
| 3 | unknown_3 | — | — | sint16 | — | źródło | 1070 | 0 |
| 4 | unknown_4 | — | — | sint16 | — | źródło | 1070 | 0 |
| 5 | unknown_5 | — | — | uint16 | — | źródło | 1070 | 0 |

## 288: unknown_288

Nazwa w parserze strukturalnym: `unknown_288`.

Wiadomości: 12. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | sint8 | — | źródło | 12 | 8 |
| 1 | unknown_1 | — | — | sint8 | — | źródło | 12 | 8 |
| 2 | unknown_2 | — | — | uint16 | — | źródło | 12 | 12 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 12 | 0 |

## 294: unknown_294

Nazwa w parserze strukturalnym: `unknown_294`.

Wiadomości: 1124. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | sint32 | — | źródło | 1124 | 0 |
| 1 | unknown_1 | — | — | sint32 | — | źródło | 1124 | 0 |
| 2 | unknown_2 | — | — | sint32 | — | źródło | 1124 | 0 |
| 3 | unknown_3 | — | — | uint16 | — | źródło | 1124 | 0 |
| 4 | unknown_4 | — | — | uint16 | — | źródło | 1124 | 0 |
| 5 | unknown_5 | — | — | uint16 | — | źródło | 1124 | 0 |
| 6 | unknown_6 | — | — | uint16 | — | źródło | 1124 | 0 |
| 7 | unknown_7 | — | — | uint16 | — | źródło | 1124 | 0 |
| 8 | unknown_8 | — | — | uint16 | — | źródło | 1124 | 0 |
| 9 | unknown_9 | — | — | enum | — | źródło | 1124 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1124 | 0 |

## 297: respiration_rate

Nazwa w parserze strukturalnym: `respiration_rate`.

Wiadomości: 1192112. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | respiration_rate | respiration_rate | breaths/min | sint16 | — | źródło | 1192112 | 0 |
| 253 | timestamp | timestamp | — | uint32 | — | źródło | 1192112 | 0 |

## 326: unknown_326

Nazwa w parserze strukturalnym: `unknown_326`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint32 | — | źródło | 9 | 0 |
| 1 | unknown_1 | — | — | uint32 | — | źródło | 9 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 9 | 0 |

## 327: unknown_327

Nazwa w parserze strukturalnym: `unknown_327`.

Wiadomości: 22. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 22 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 22 | 0 |
| 2 | unknown_2 | — | — | uint8 | — | źródło | 22 | 0 |
| 3 | unknown_3 | — | — | uint32 | — | źródło | 22 | 0 |
| 4 | unknown_4 | — | — | uint32 | — | źródło | 22 | 0 |
| 5 | unknown_5 | — | — | uint32 | — | źródło | 22 | 0 |
| 6 | unknown_6 | — | — | enum | — | źródło | 22 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 22 | 0 |

## 330: unknown_330

Nazwa w parserze strukturalnym: `unknown_330`.

Wiadomości: 833. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | enum | — | źródło | 833 | 0 |
| 1 | unknown_1 | — | — | uint32 | — | źródło | 833 | 0 |
| 2 | unknown_2 | — | — | sint8 | — | źródło | 833 | 0 |
| 3 | unknown_3 | — | — | uint32 | — | źródło | 833 | 0 |

## 339: unknown_339

Nazwa w parserze strukturalnym: `unknown_339`.

Wiadomości: 1960. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint32 | — | źródło | 1960 | 0 |
| 1 | unknown_1 | — | — | uint16 | — | źródło | 1960 | 0 |
| 2 | unknown_2 | — | — | uint16 | — | źródło | 1960 | 0 |
| 3 | unknown_3 | — | — | uint16 | — | źródło | 1960 | 0 |
| 4 | unknown_4 | — | — | uint16 | — | źródło | 1960 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1960 | 0 |

## 346: sleep_assessment

Nazwa w parserze strukturalnym: `sleep_assessment`.

Wiadomości: 838. Kategorie: SLEEP_DATA.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | combined_awake_score | combined_awake_score | — | uint8 | — | źródło | 838 | 0 |
| 1 | awake_time_score | awake_time_score | — | uint8 | — | źródło | 838 | 0 |
| 2 | awakenings_count_score | awakenings_count_score | — | uint8 | — | źródło | 838 | 0 |
| 3 | deep_sleep_score | deep_sleep_score | — | uint8 | — | źródło | 838 | 3 |
| 4 | sleep_duration_score | sleep_duration_score | — | uint8 | — | źródło | 838 | 0 |
| 5 | light_sleep_score | light_sleep_score | — | uint8 | — | źródło | 838 | 3 |
| 6 | overall_sleep_score | overall_sleep_score | — | uint8 | — | źródło | 838 | 0 |
| 7 | sleep_quality_score | sleep_quality_score | — | uint8 | — | źródło | 838 | 0 |
| 8 | sleep_recovery_score | sleep_recovery_score | — | uint8 | — | źródło | 838 | 0 |
| 9 | rem_sleep_score | rem_sleep_score | — | uint8 | — | źródło | 838 | 3 |
| 10 | sleep_restlessness_score | sleep_restlessness_score | — | uint8 | — | źródło | 838 | 0 |
| 11 | awakenings_count | awakenings_count | — | uint8 | — | źródło | 838 | 0 |
| 12 | unknown_12 | — | — | enum | — | źródło | 838 | 0 |
| 13 | unknown_13 | — | — | enum | — | źródło | 838 | 0 |
| 14 | interruptions_score | interruptions_score | — | uint8 | — | źródło | 838 | 0 |
| 15 | average_stress_during_sleep | average_stress_during_sleep | — | uint16 | — | źródło | 838 | 0 |
| 16 | unknown_16 | — | — | enum | — | źródło | 838 | 0 |

## 355: unknown_355

Nazwa w parserze strukturalnym: `unknown_355`.

Wiadomości: 4425. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint16 | — | źródło | 4425 | 0 |
| 1 | unknown_1 | — | — | uint16 | — | źródło | 4425 | 0 |
| 2 | unknown_2 | — | — | uint16 | — | źródło | 4425 | 0 |

## 356: unknown_356

Nazwa w parserze strukturalnym: `unknown_356`.

Wiadomości: 1065. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 364 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 220 | 0 |
| 2 | unknown_2 | — | — | uint32 | — | źródło | 1065 | 0 |
| 3 | unknown_3 | — | — | uint32 | — | źródło | 1065 | 0 |
| 4 | unknown_4 | — | — | uint16 | — | źródło | 220 | 0 |
| 5 | unknown_5 | — | — | uint8 | — | źródło | 1063 | 0 |
| 6 | unknown_6 | — | — | uint8 | — | źródło | 1063 | 0 |
| 7 | unknown_7 | — | — | uint16 | — | źródło | 206 | 0 |
| 8 | unknown_8 | — | — | uint8 | — | źródło | 206 | 0 |
| 10 | unknown_10 | — | — | uint16 | — | źródło | 206 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 845 | 0 |
| 12 | unknown_12 | — | — | enum | — | źródło | 845 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1065 | 0 |

## 357: unknown_357

Nazwa w parserze strukturalnym: `unknown_357`.

Wiadomości: 1070. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 1070 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 1070 | 0 |
| 2 | unknown_2 | — | — | uint16 | — | źródło | 1070 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1070 | 0 |

## 369: unknown_369

Nazwa w parserze strukturalnym: `unknown_369`.

Wiadomości: 1451. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 1447 | 0 |
| 1 | unknown_1 | — | — | enum | — | źródło | 1451 | 0 |
| 2 | unknown_2 | — | — | enum | — | źródło | 1451 | 0 |
| 3 | unknown_3 | — | — | enum | — | źródło | 1451 | 0 |
| 4 | unknown_4 | — | — | uint8 | — | źródło | 1038 | 0 |
| 5 | unknown_5 | — | — | uint8 | — | źródło | 1451 | 0 |
| 6 | unknown_6 | — | — | enum | — | źródło | 1451 | 0 |
| 7 | unknown_7 | — | — | uint16 | — | źródło | 1451 | 0 |
| 8 | unknown_8 | — | — | uint8 | — | źródło | 1451 | 0 |
| 9 | unknown_9 | — | — | enum | — | źródło | 1451 | 0 |
| 10 | unknown_10 | — | — | uint8 | — | źródło | 1451 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 1451 | 0 |
| 12 | unknown_12 | — | — | uint8 | — | źródło | 1451 | 0 |
| 13 | unknown_13 | — | — | enum | — | źródło | 1451 | 0 |
| 14 | unknown_14 | — | — | uint8 | — | źródło | 1451 | 0 |
| 15 | unknown_15 | — | — | enum | — | źródło | 1451 | 0 |
| 16 | unknown_16 | — | — | uint8 | — | źródło | 1451 | 0 |
| 17 | unknown_17 | — | — | enum | — | źródło | 1451 | 0 |
| 18 | unknown_18 | — | — | enum | — | źródło | 1451 | 0 |
| 19 | unknown_19 | — | — | enum | — | źródło | 1300 | 0 |
| 20 | unknown_20 | — | — | uint32 | — | źródło | 1451 | 0 |
| 21 | unknown_21 | — | — | uint16 | — | źródło | 1447 | 0 |
| 22 | unknown_22 | — | — | uint16 | — | źródło | 1445 | 0 |
| 25 | unknown_25 | — | — | enum | — | źródło | 1450 | 0 |
| 26 | unknown_26 | — | — | enum | — | źródło | 1450 | 0 |
| 27 | unknown_27 | — | — | enum | — | źródło | 1450 | 0 |
| 28 | unknown_28 | — | — | enum | — | źródło | 1449 | 0 |
| 29 | unknown_29 | — | — | enum | — | źródło | 1448 | 0 |
| 30 | unknown_30 | — | — | enum | — | źródło | 1449 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1451 | 0 |

## 370: hrv_status_summary

Nazwa w parserze strukturalnym: `hrv_status_summary`.

Wiadomości: 838. Kategorie: HRV_STATUS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | weekly_average | weekly_average | ms | uint16 | — | źródło | 838 | 3 |
| 1 | last_night_average | last_night_average | ms | uint16 | — | źródło | 838 | 10 |
| 2 | last_night_5_min_high | last_night_5_min_high | ms | uint16 | — | źródło | 838 | 9 |
| 3 | baseline_low_upper | baseline_low_upper | ms | uint16 | — | źródło | 838 | 18 |
| 4 | baseline_balanced_lower | baseline_balanced_lower | ms | uint16 | — | źródło | 838 | 18 |
| 5 | baseline_balanced_upper | baseline_balanced_upper | ms | uint16 | — | źródło | 838 | 18 |
| 6 | status | status | — | enum | — | źródło | 838 | 0 |
| 7 | unknown_7 | — | — | enum | — | źródło | 838 | 0 |
| 8 | unknown_8 | — | — | uint32 | — | źródło | 838 | 18 |
| 253 | timestamp | timestamp | — | uint32 | — | źródło | 838 | 0 |

## 371: hrv_value

Nazwa w parserze strukturalnym: `hrv_value`.

Wiadomości: 73938. Kategorie: HRV_STATUS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | value | value | ms | uint16 | — | źródło | 73938 | 549 |
| 253 | timestamp | timestamp | — | uint32 | — | źródło | 73938 | 0 |

## 378: unknown_378

Nazwa w parserze strukturalnym: `unknown_378`.

Wiadomości: 1130. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 1124 | 0 |
| 1 | unknown_1 | — | — | enum | — | źródło | 1130 | 0 |
| 2 | unknown_2 | — | — | enum | — | źródło | 1130 | 0 |
| 3 | unknown_3 | — | — | uint16 | — | źródło | 1130 | 0 |
| 4 | unknown_4 | — | — | uint16 | — | źródło | 1130 | 0 |
| 5 | unknown_5 | — | — | uint8 | — | źródło | 1111 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1130 | 0 |

## 382: unknown_382

Nazwa w parserze strukturalnym: `unknown_382`.

Wiadomości: 838. Kategorie: SLEEP_DATA.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint32 | — | źródło | 838 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 838 | 0 |
| 2 | unknown_2 | — | — | uint8 | 200 | źródło | 838 | 0 |

## 384: unknown_384

Nazwa w parserze strukturalnym: `unknown_384`.

Wiadomości: 848. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 848 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 848 | 0 |
| 2 | unknown_2 | — | — | uint8 | — | źródło | 848 | 0 |
| 3 | unknown_3 | — | — | uint16 | — | źródło | 840 | 0 |
| 4 | unknown_4 | — | — | sint8 | — | źródło | 848 | 0 |
| 5 | unknown_5 | — | — | sint32 | — | źródło | 848 | 0 |
| 6 | unknown_6 | — | — | sint32 | — | źródło | 848 | 0 |
| 7 | unknown_7 | — | — | sint32 | — | źródło | 848 | 0 |
| 8 | unknown_8 | — | — | uint32 | — | źródło | 848 | 0 |
| 9 | unknown_9 | — | — | uint32 | — | źródło | 848 | 0 |
| 10 | unknown_10 | — | — | sint16 | — | źródło | 848 | 0 |
| 11 | unknown_11 | — | — | uint32 | — | źródło | 848 | 0 |
| 12 | unknown_12 | — | — | sint16 | — | źródło | 848 | 0 |
| 14 | unknown_14 | — | — | uint8 | — | źródło | 848 | 14 |
| 15 | unknown_15 | — | — | uint8 | — | źródło | 836 | 14 |
| 16 | unknown_16 | — | — | uint8 | — | źródło | 848 | 14 |
| 17 | unknown_17 | — | — | enum | — | źródło | 848 | 14 |
| 18 | unknown_18 | — | — | uint32 | — | źródło | 846 | 14 |
| 19 | unknown_19 | — | — | sint8 | — | źródło | 837 | 14 |
| 20 | unknown_20 | — | — | sint8 | — | źródło | 848 | 14 |
| 21 | unknown_21 | — | — | uint8 | — | źródło | 848 | 14 |
| 22 | unknown_22 | — | — | sint16 | — | źródło | 821 | 14 |
| 23 | unknown_23 | — | — | sint8 | — | źródło | 848 | 14 |
| 24 | unknown_24 | — | — | uint16 | — | źródło | 848 | 0 |
| 25 | unknown_25 | — | — | sint8 | — | źródło | 848 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 848 | 0 |

## 394: unknown_394

Nazwa w parserze strukturalnym: `unknown_394`.

Wiadomości: 9. Kategorie: ACTIVITY.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | enum | — | źródło | 9 | 0 |
| 1 | unknown_1 | — | — | uint32 | — | źródło | 9 | 0 |
| 2 | unknown_2 | — | — | uint32 | — | źródło | 9 | 0 |
| 3 | unknown_3 | — | — | uint32 | — | źródło | 9 | 9 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 9 | 0 |

## 397: unknown_397

Nazwa w parserze strukturalnym: `unknown_397`.

Wiadomości: 1200908. Kategorie: SKIN_TEMP.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | unknown_1 | — | — | float32 | — | źródło | 1200908 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1200908 | 0 |

## 398: skin_temp_overnight

Nazwa w parserze strukturalnym: `skin_temp_overnight`.

Wiadomości: 833. Kategorie: SKIN_TEMP.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | local_timestamp | local_timestamp | — | uint32 | — | źródło | 833 | 0 |
| 1 | average_deviation | average_deviation | — | float32 | — | źródło | 833 | 2 |
| 2 | average_7_day_deviation | average_7_day_deviation | — | float32 | — | źródło | 833 | 2 |
| 3 | unknown_3 | — | — | uint8 | — | źródło | 833 | 0 |
| 4 | nightly_value | nightly_value | — | float32 | — | źródło | 748 | 0 |
| 253 | timestamp | timestamp | — | uint32 | — | źródło | 833 | 0 |

## 402: unknown_402

Nazwa w parserze strukturalnym: `unknown_402`.

Wiadomości: 1140. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint8 | — | źródło | 467 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 467 | 0 |
| 2 | unknown_2 | — | — | uint8 | — | źródło | 467 | 0 |
| 3 | unknown_3 | — | — | enum | — | źródło | 1140 | 0 |
| 4 | unknown_4 | — | — | enum | — | źródło | 1140 | 0 |
| 5 | unknown_5 | — | — | enum | — | źródło | 1140 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1140 | 0 |

## 403: unknown_403

Nazwa w parserze strukturalnym: `unknown_403`.

Wiadomości: 1140. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint16 | — | źródło | 1111 | 0 |
| 1 | unknown_1 | — | — | enum | — | źródło | 1140 | 0 |
| 2 | unknown_2 | — | — | enum | — | źródło | 1140 | 0 |
| 3 | unknown_3 | — | — | uint16 | — | źródło | 1140 | 0 |
| 4 | unknown_4 | — | — | uint16 | — | źródło | 1140 | 0 |
| 5 | unknown_5 | — | — | uint16 | — | źródło | 1140 | 0 |
| 6 | unknown_6 | — | — | uint16 | — | źródło | 1140 | 0 |
| 7 | unknown_7 | — | — | uint16 | — | źródło | 1140 | 0 |
| 8 | unknown_8 | — | — | uint16 | — | źródło | 1140 | 0 |
| 9 | unknown_9 | — | — | uint16 | — | źródło | 1140 | 0 |
| 10 | unknown_10 | — | — | uint16 | — | źródło | 1140 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1140 | 0 |

## 404: unknown_404

Nazwa w parserze strukturalnym: `unknown_404`.

Wiadomości: 3726. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | enum | — | źródło | 1649 | 0 |
| 1 | unknown_1 | — | — | enum | — | źródło | 1649 | 0 |
| 2 | unknown_2 | — | — | enum | — | źródło | 2077 | 0 |
| 3 | unknown_3 | — | — | uint16 | — | źródło | 3726 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 3726 | 0 |

## 407: unknown_407

Nazwa w parserze strukturalnym: `unknown_407`.

Wiadomości: 2538. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | enum | — | źródło | 2538 | 0 |
| 1 | unknown_1 | — | — | uint16 | — | źródło | 2538 | 0 |
| 2 | unknown_2 | — | — | sint8 | — | źródło | 2538 | 0 |
| 3 | unknown_3 | — | — | enum | — | źródło | 2538 | 0 |
| 4 | unknown_4 | — | — | enum | — | źródło | 2538 | 2538 |
| 5 | unknown_5 | — | — | enum | — | źródło | 2538 | 2538 |
| 6 | unknown_6 | — | — | enum | — | źródło | 2538 | 0 |
| 7 | unknown_7 | — | — | uint32 | — | źródło | 2538 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 2538 | 0 |

## 408: unknown_408

Nazwa w parserze strukturalnym: `unknown_408`.

Wiadomości: 19946. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | enum | — | źródło | 19946 | 0 |
| 1 | unknown_1 | — | — | uint16 | — | źródło | 19946 | 6015 |
| 2 | unknown_2 | — | — | uint16 | — | źródło | 19946 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 19946 | 0 |

## 410: unknown_410

Nazwa w parserze strukturalnym: `unknown_410`.

Wiadomości: 1124. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint16 | — | źródło | 1124 | 0 |
| 1 | unknown_1 | — | — | uint16 | — | źródło | 1124 | 0 |
| 2 | unknown_2 | — | — | uint8 | — | źródło | 1124 | 0 |
| 3 | unknown_3 | — | — | uint8 | — | źródło | 1124 | 0 |
| 4 | unknown_4 | — | — | uint8 | — | źródło | 1124 | 0 |
| 5 | unknown_5 | — | — | uint8 | — | źródło | 1124 | 0 |
| 6 | unknown_6 | — | — | uint8 | — | źródło | 1124 | 0 |
| 252 | unknown_252 | — | — | uint8 | — | źródło | 1124 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 1124 | 0 |

## 412: nap_event

Nazwa w parserze strukturalnym: `unknown_412`.

Wiadomości: 9. Kategorie: NAP.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | start_time | seconds | uint32 | — | źródło | 9 | 0 |
| 1 | unknown_1 | start_timezone_offset | minutes | sint16 | — | źródło | 9 | 0 |
| 2 | unknown_2 | end_time | seconds | uint32 | — | źródło | 9 | 0 |
| 3 | unknown_3 | end_timezone_offset | minutes | sint16 | — | źródło | 9 | 0 |
| 4 | unknown_4 | feedback | — | enum | — | źródło | 9 | 0 |
| 5 | unknown_5 | is_deleted | — | enum | — | źródło | 9 | 9 |
| 6 | unknown_6 | source | — | enum | — | źródło | 9 | 0 |
| 7 | unknown_7 | update_timestamp | — | uint32 | — | źródło | 9 | 0 |
| 253 | unknown_253 | timestamp | — | uint32 | — | źródło | 9 | 0 |
| 254 | unknown_254 | message_index | — | uint16 | — | źródło | 9 | 9 |

## 430: unknown_430

Nazwa w parserze strukturalnym: `unknown_430`.

Wiadomości: 28. Kategorie: METRICS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | sint32 | — | źródło | 28 | 0 |
| 1 | unknown_1 | — | — | sint32 | — | źródło | 28 | 0 |
| 2 | unknown_2 | — | — | sint32 | — | źródło | 28 | 0 |
| 3 | unknown_3 | — | — | sint32 | — | źródło | 28 | 0 |
| 4 | unknown_4 | — | — | uint16 | — | źródło | 28 | 0 |
| 5 | unknown_5 | — | — | uint16 | — | źródło | 28 | 0 |
| 6 | unknown_6 | — | — | uint32 | — | źródło | 28 | 0 |
| 7 | unknown_7 | — | — | uint8 | — | źródło | 9 | 0 |
| 8 | unknown_8 | — | — | uint8 | — | źródło | 9 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 28 | 0 |

## 470: sleep_disruption_severity_period

Nazwa w parserze strukturalnym: `unknown_470`.

Wiadomości: 2005. Kategorie: SLEEP_DISRUPTIONS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | severity | — | enum | — | źródło | 2005 | 761 |
| 253 | unknown_253 | timestamp | — | uint32 | — | źródło | 2005 | 0 |
| 254 | unknown_254 | message_index | — | uint16 | — | źródło | 2005 | 0 |

## 471: sleep_disruption_overnight_severity

Nazwa w parserze strukturalnym: `unknown_471`.

Wiadomości: 451. Kategorie: SLEEP_DISRUPTIONS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | severity | — | enum | — | źródło | 451 | 10 |
| 253 | unknown_253 | timestamp | — | uint32 | — | źródło | 451 | 0 |

## 484: unknown_484

Nazwa w parserze strukturalnym: `unknown_484`.

Wiadomości: 3376. Kategorie: WELLNESS.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint16 | — | źródło | 3376 | 0 |

## 521: unknown_521

Nazwa w parserze strukturalnym: `unknown_521`.

Wiadomości: 383. Kategorie: SLEEP_DATA.

| Nr pola | Nazwa parsera | Nazwa SDK | Jednostka | Typ raw | Długości tablic | Pochodzenie | Wystąpienia | Nieważne całe pola |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: |
| 0 | unknown_0 | — | — | uint32 | — | źródło | 383 | 0 |
| 1 | unknown_1 | — | — | uint8 | — | źródło | 383 | 0 |
| 2 | unknown_2 | — | — | sint32 | — | źródło | 383 | 0 |
| 3 | unknown_3 | — | — | uint32 | — | źródło | 383 | 0 |
| 4 | unknown_4 | — | — | sint16 | — | źródło | 383 | 0 |
| 5 | unknown_5 | — | — | uint32 | — | źródło | 383 | 0 |
| 6 | unknown_6 | — | — | sint16 | — | źródło | 383 | 0 |
| 7 | unknown_7 | — | — | sint8 | — | źródło | 383 | 0 |
| 8 | unknown_8 | — | — | uint16 | — | źródło | 383 | 7 |
| 9 | unknown_9 | — | — | uint16 | — | źródło | 383 | 0 |
| 10 | unknown_10 | — | — | uint16 | — | źródło | 383 | 0 |
| 11 | unknown_11 | — | — | enum | — | źródło | 383 | 0 |
| 253 | unknown_253 | — | — | uint32 | — | źródło | 383 | 0 |
