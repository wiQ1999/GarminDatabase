"""Polish explanations based on public Garmin documentation, not guessed physiology."""

from dataclasses import dataclass, replace

from garmin_database.domain.aggregation import MEAN_PARAMETERS

VERSION = 1
REVIEWED_ON = "2026-10-25"
SOURCES = {
    "hr": (
        "Garmin: Heart Rate Monitoring",
        "https://www.garmin.com/en-US/garmin-technology/health-science/heart-rate-monitoring/",
    ),
    "hrv": (
        "Garmin: HRV Status",
        "https://www.garmin.com/en-US/garmin-technology/health-science/hrv-status/",
    ),
    "rhr": (
        "Garmin: How Is Resting Heart Rate Calculated?",
        "https://support.garmin.com/en-AU/?faq=F8YKCB4CJd5PG0DR9ICV3A",
    ),
    "stress": (
        "Garmin: Stress Tracking",
        "https://www.garmin.com/en-CA/garmin-technology/health-science/stress-tracking/",
    ),
    "stress_scale": (
        "Garmin: What Is the Stress Level Feature?",
        "https://support.garmin.com/en-HK/?faq=WT9BmhjacO4ZpxbCc0EKn9",
    ),
    "respiration": (
        "Garmin: Respiration Rate",
        "https://www.garmin.com/en-GB/garmin-technology/health-science/respiration-rate/",
    ),
    "respiration_gaps": (
        "Garmin: Using the Respiration Rate Feature",
        "https://support.garmin.com/da-DK/?faq=2yEgS0Pax53UDqUH7q4WC6",
    ),
    "spo2": (
        "Garmin: Pulse Ox",
        "https://www.garmin.com/en-US/garmin-technology/health-science/pulse-ox/",
    ),
    "spo2_modes": (
        "Garmin: Top FAQs for Pulse Ox",
        "https://support.garmin.com/en-IN/?faq=SK2Y9a9aBp5D6n4sXmPBG7",
    ),
    "sleep": (
        "Garmin: Sleep Tracking",
        "https://www.garmin.com/en-IE/garmin-technology/health-science/sleep-tracking/",
    ),
    "sleep_sensors": (
        "Garmin: Advanced Sleep Monitoring",
        "https://support.garmin.com/en-AU/navionics/faq/mBRMf4ks7XAQ03qtsbI8J6/",
    ),
    "naps": (
        "Garmin: Tracking Naps",
        "https://support.garmin.com/in-ID/?faq=2icqqZFq3YAX5K9VGU2CQ9",
    ),
    "skin": (
        "Garmin: Skin Temperature",
        "https://support.garmin.com/id-ID/?faq=RDXq6E5Iaq9rD1l1kTObf6",
    ),
    "skin_accuracy": (
        "Garmin: Activity Tracking and Fitness Metric Accuracy",
        "https://www.garmin.com/en-IE/legal/atdisclaimer/",
    ),
    "steps": (
        "Garmin: Counting Steps",
        "https://support.garmin.com/en-IN/?faq=z1TfJCqajl8ZEZey72gg98",
    ),
    "calories": (
        "Garmin: Calorie Terminology",
        "https://support.garmin.com/en-CA/?faq=lkl4cwCLlK7ox362uGQEV7",
    ),
    "calorie_method": (
        "Garmin: Tracking Calories",
        "https://support.garmin.com/it-IT/?faq=lkl4cwCLlK7ox362uGQEV7",
    ),
    "minutes": (
        "Garmin: Intensity Minutes",
        "https://support.garmin.com/en-US/aviation/faq/pNU9nnDzzGAHmEavp9rpY8/",
    ),
    "minutes_method": (
        "Garmin: How Are Intensity Minutes Earned?",
        "https://support.garmin.com/en-US/?faq=pNU9nnDzzGAHmEavp9rpY8&productID=707538&tab=",
    ),
    "elevation": (
        "Garmin: tactix 8, elevation and floors",
        "https://www8.garmin.com/manuals/webhelp/GUID-EA668398-46E4-42E4-8163-12F6CB299F0E/EN-US/GUID-C950F63E-2687-4B1D-AAF7-F67CE6B05EFF.html",
    ),
    "distance": (
        "Garmin: Step Distance and Stride Length",
        "https://support.garmin.com/en-AU/?faq=ky5UNByyYh9iXay7mvbnt9&productID=583562&tab=",
    ),
    "fit": (
        "Garmin FIT SDK: public profile",
        "https://github.com/garmin/fit-python-sdk/blob/main/garmin_fit_sdk/profile.py",
    ),
    "fit_protocol": (
        "Garmin: FIT Protocol, common fields",
        "https://developer.garmin.com/fit/protocol/",
    ),
}


@dataclass(frozen=True)
class Explanation:
    meaning: str
    measurement: str
    limitations: str
    sources: tuple[str, ...]
    evidence: str = "manufacturer_explanation"


DESCRIPTIONS = {
    "monitoring.heart_rate": Explanation(
        "Częstość pracy serca w uderzeniach na minutę (bpm).",
        "Garmin opisuje optyczny pomiar PPG na nadgarstku; podczas aktywności możliwy jest też pas mierzący sygnał elektryczny serca.",
        "To pole FIT nie potwierdza czujnika konkretnej próbki. Algorytm średnich aplikacji nie odrzuca zerowego tętna; średnia próbek jest inną statystyką niż tętno spoczynkowe.",
        ("hr",),
    ),
    "hrv_value.value": Explanation(
        "Pięciominutowa statystyka HRV RMSSD w milisekundach, zgodnie z definicją pola FIT.",
        "Zmienność odstępów między uderzeniami serca; Garmin opisuje nocny pomiar na podstawie sygnału optycznego Elevate.",
        "Średnia dostępnych pięciominutowych wartości nie musi być równa źródłowej średniej nocnej ani statusowi HRV w Garmin Connect.",
        ("hrv", "fit"),
    ),
    "stress_level.stress_level_value": Explanation(
        "Oszacowanie fizjologicznego poziomu stresu na skali Garmin 0–100.",
        "Algorytm Garmin wykorzystuje przede wszystkim tętno i HRV z optycznego czujnika. Nie jest to bezpośredni pomiar konkretnej emocji.",
        "0–25: odpoczynek, 26–50: niski, 51–75: średni, 76–100: wysoki. Ruch może uniemożliwić ocenę; ujemne kody nie są poziomem stresu.",
        ("stress", "stress_scale"),
    ),
    "respiration_rate.respiration_rate": Explanation(
        "Szacowana liczba pełnych oddechów na minutę.",
        "Garmin wykorzystuje zmiany odstępów między uderzeniami serca związane z oddychaniem (HRV). Źródło sygnału zależy od urządzenia i trybu.",
        "Ruch może powodować luki. Profil nie objaśnia ujemnych wartości; nie oznaczają ujemnej liczby oddechów. Obecny algorytm średnich aplikacji ich nie odrzuca.",
        ("respiration", "respiration_gaps", "fit"),
    ),
    "spo2_data.reading_spo2": Explanation(
        "Szacowana saturacja obwodowa SpO₂: procent wysycenia krwi tlenem.",
        "Pulse Ox korzysta ze światła czerwonego i podczerwonego oraz czujnika optycznego urządzenia.",
        "Tryb pomiaru, ruch i dopasowanie zegarka wpływają na dostępność odczytów. Średnia całej doby nie jest wyłącznie średnią podczas snu.",
        ("spo2",),
    ),
    "spo2_data.mode": Explanation(
        "Tryb zarejestrowania odczytu Pulse Ox; kod kategorii, nie wartość saturacji.",
        "Garmin rozróżnia w FIT m.in. odczyt punktowy, ciągły, okresowy i stan off_wrist.",
        "Dostępność trybów zależy od modelu. Nie należy uśredniać kodów kategorii.",
        ("spo2_modes", "fit"),
    ),
    "spo2_data.reading_confidence": Explanation(
        "Źródłowe pole pewności odczytu SpO₂ w profilu FIT.",
        "Wartość oceny zapisywana przez urządzenie; publiczny profil nie podaje pełnego algorytmu jej wyznaczania.",
        "Nie należy zakładać, że jest to procent, prawdopodobieństwo ani kliniczna dokładność pomiaru.",
        ("fit",),
        "fit_profile_only",
    ),
    "monitoring_hr_data.resting_heart_rate": Explanation(
        "W tym polu FIT Garmin zapisuje 7-dniową średnią kroczącą tętna spoczynkowego.",
        "Dobowa wartość spoczynkowa Garmin bazuje na najniższej średniej z 30 minut w ciągu 24 godzin; pole łączy kolejne dni.",
        "Nie utożsamiać z dzisiejszym tętnem spoczynkowym ani średnią wszystkich pomiarów tętna.",
        ("rhr", "fit"),
    ),
    "monitoring_hr_data.current_day_resting_heart_rate": Explanation(
        "Tętno spoczynkowe dla bieżącego dnia zapisane przez Garmin.",
        "Według Garmin dobowe RHR wyznacza najniższa 30-minutowa średnia z okresu 24 godzin.",
        "To osobna statystyka względem średniej kroczącej 7 dni i średniej próbek chwilowego tętna.",
        ("rhr", "fit"),
    ),
    "sleep_level.sleep_level": Explanation(
        "Faza snu rozpoznana przez Garmin: czuwanie, sen płytki, głęboki, REM lub brak możliwości oceny.",
        "Algorytm łączy sygnał optyczny tętna/HRV oraz dane ruchu z akcelerometru; dostępne funkcje zależą od urządzenia.",
        "Są to kategorie estymowane przez urządzenie. Arytmetyczna średnia kodów faz nie opisuje snu.",
        ("sleep_sensors", "fit"),
    ),
    "sleep_assessment.average_stress_during_sleep": Explanation(
        "Źródłowa średnia stresu podczas snu obliczona przez Garmin.",
        "Stres jest estymowany z HR/HRV; definicja FIT tego pola wyłącza okresy czuwania w oknie snu.",
        "To gotowa nocna statystyka producenta. Publiczne materiały nie ujawniają pełnego wzoru ani wszystkich reguł ważenia.",
        ("stress", "fit"),
    ),
}

HRV_METHOD = "Źródłowa statystyka nocnego HRV. Garmin opisuje pomiar optyczny i porównanie z osobistym zakresem bazowym."
HRV_LIMIT = "Wartość oblicza Garmin; pełna personalizacja i dostępność zależą od urządzenia oraz historii pomiarów."
for field, meaning in {
    "weekly_average": "7-dniowa średnia nocnego RMSSD zapisana przez Garmin.",
    "last_night_average": "Średnie RMSSD z ostatniej nocy, wyznaczone przez Garmin.",
    "last_night_5_min_high": "Najwyższa pięciominutowa wartość RMSSD ostatniej nocy.",
    "baseline_balanced_lower": "Dolna granica osobistego zakresu zrównoważonego HRV.",
    "baseline_balanced_upper": "Górna granica osobistego zakresu zrównoważonego HRV.",
    "baseline_low_upper": "Górna granica zakresu niskiego HRV w osobistej wartości bazowej.",
    "status": "Klasyfikacja statusu HRV względem osobistej bazy; kod kategorii, nie pomiar w ms.",
}.items():
    DESCRIPTIONS["hrv_status_summary." + field] = Explanation(
        meaning, HRV_METHOD, HRV_LIMIT, ("hrv", "fit")
    )

SLEEP_METHOD = "Gotowy wynik algorytmu Garmin. Analiza snu wykorzystuje tętno, HRV i ruch; dokładne wagi składowych nie są publiczne."
SLEEP_LIMIT = (
    "Skala oceny 0–100 (wyżej oznacza lepiej), nie czas ani procent długości fazy."
)
for field, meaning in {
    "overall_sleep_score": "Łączna ocena jakości i długości snu.",
    "sleep_quality_score": "Ocena jakości snu: struktura faz, HRV i przebudzenia.",
    "sleep_duration_score": "Składowa oceny snu oznaczona przez Garmin jako sleep_duration_score.",
    "deep_sleep_score": "Ocena ilości snu głębokiego.",
    "light_sleep_score": "Ocena ilości snu płytkiego.",
    "rem_sleep_score": "Ocena ilości snu REM.",
    "awake_time_score": "Ocena czasu czuwania pomiędzy okresami snu.",
    "awakenings_count_score": "Ocena liczby przebudzeń przerywających sen.",
    "combined_awake_score": "Ocena łącząca awake_time_score i awakenings_count_score; w FIT ich średnia.",
    "sleep_recovery_score": "Ocena stresu i regeneracji podczas snu.",
    "sleep_restlessness_score": "Ocena niespokojności i ruchu podczas snu.",
    "interruptions_score": "Ocena przerw w śnie.",
}.items():
    DESCRIPTIONS["sleep_assessment." + field] = Explanation(
        meaning, SLEEP_METHOD, SLEEP_LIMIT, ("sleep", "fit")
    )
DESCRIPTIONS["sleep_assessment.awakenings_count"] = Explanation(
    "Liczba przebudzeń podczas snu zapisana przez Garmin.",
    SLEEP_METHOD,
    "Liczba zdarzeń, nie ocena 0–100. Pełne kryteria detekcji pojedynczego przebudzenia nie są podane w profilu FIT.",
    ("sleep_sensors", "fit"),
)

for field, meaning in {
    "average_deviation": "Średnie nocne odchylenie temperatury skóry od wartości bazowej (°C w opisie profilu).",
    "average_7_day_deviation": "Średnie odchylenie nocnej temperatury skóry z 7 dni (°C w opisie profilu).",
    "nightly_value": "Końcowa nocna wartość temperatury w źródłowym polu FIT nightly_value.",
}.items():
    DESCRIPTIONS["skin_temp_overnight." + field] = Explanation(
        meaning,
        "Kompatybilne urządzenie rejestruje temperaturę skóry podczas snu i buduje osobistą bazę.",
        "Temperatura skóry nie jest temperaturą wnętrza ciała. Wpływają na nią warunki snu i dopasowanie urządzenia; nightly_value nie należy samodzielnie utożsamiać z odchyleniem.",
        ("skin", "skin_accuracy", "fit"),
    )

for field, meaning in {
    "active_time": "Skumulowany czas aktywności zapisany w monitoringu FIT, w sekundach.",
    "duration_min": "Czas trwania w minutach zapisany w komunikacie monitoring.",
    "duration": "Czas trwania w sekundach zapisany w komunikacie monitoring.",
    "cycles": "Skumulowane cykle ruchu; ich znaczenie zależy od typu aktywności.",
    "distance": "Skumulowany dystans monitoringu, w metrach, powiązany z typem aktywności.",
    "intensity": "Źródłowa wartość intensywności ruchu w monitoringu FIT.",
    "activity_type": "Kategoria aktywności przypisana przez urządzenie.",
    "current_activity_type_intensity": "Złożone pole FIT opisujące bieżący typ aktywności i intensywność od poprzedniej wiadomości.",
}.items():
    DESCRIPTIONS["monitoring." + field] = Explanation(
        meaning,
        "Wartość generowana przez urządzenie w monitoringu; sam zapis FIT nie wskazuje wszystkich użytych czujników ani reguł algorytmu.",
        "Kontekst activity_type ma znaczenie. Nie należy sumować kolejnych stanów licznika ani zakładać pomiaru GPS z samej nazwy pola.",
        ("fit",),
        "fit_profile_only",
    )
DESCRIPTIONS["monitoring.distance"] = Explanation(
    "Skumulowany dystans monitoringu, w metrach, powiązany z typem aktywności.",
    "Garmin opisuje szacowanie dystansu kroków z liczby kroków i długości kroku. Nagrywane aktywności mogą używać innych źródeł, m.in. GPS.",
    "Sam ten zapis FIT nie potwierdza użycia GPS. Nie należy sumować kolejnych stanów licznika; znaczenie ma kontekst activity_type.",
    ("distance", "fit"),
)
DESCRIPTIONS["skin_temp_overnight.nightly_value"] = replace(
    DESCRIPTIONS["skin_temp_overnight.nightly_value"],
    limitations="Publiczny profil określa to jako końcową wartość nocną, ale nie podaje jednostki ani pełnego przeliczenia. Nie utożsamiamy jej z temperaturą wnętrza ciała ani odchyleniem od bazy.",
    evidence="fit_profile_only",
)
DESCRIPTIONS["sleep_assessment.sleep_duration_score"] = replace(
    DESCRIPTIONS["sleep_assessment.sleep_duration_score"], evidence="fit_profile_only"
)
DESCRIPTIONS["monitoring.steps"] = Explanation(
    "Licznik kroków z monitoringu Garmin.",
    "Garmin opisuje rozpoznawanie powtarzalnego ruchu przez akcelerometr; w FIT kroki są subpolem licznika cykli zależnym od aktywności.",
    "Ruch rąk może zmieniać zliczanie. Kolejne stany licznika nie są niezależnymi porcjami kroków do sumowania.",
    ("steps", "fit"),
)
for field, meaning in {
    "active_calories": "Energia zużyta na aktywność i ruch, w kcal.",
    "calories": "Skumulowany licznik kalorii w monitoringu FIT, zależny od activity_type.",
}.items():
    DESCRIPTIONS["monitoring." + field] = Explanation(
        meaning,
        "Garmin szacuje wydatek energii algorytmicznie na podstawie dostępnych danych urządzenia i profilu użytkownika.",
        "Kalorie aktywne, spoczynkowe i kalorie z nagranej aktywności to różne pojęcia. Nie sumować kolejnych stanów licznika.",
        ("calories", "calorie_method", "fit"),
    )
for field, meaning in {
    "moderate_activity_minutes": "Licznik minut umiarkowanej aktywności.",
    "vigorous_activity_minutes": "Licznik minut intensywnej aktywności; Garmin zalicza je podwójnie do celu minut intensywności.",
}.items():
    DESCRIPTIONS["monitoring." + field] = Explanation(
        meaning,
        "Garmin porównuje tętno z tętnem spoczynkowym lub ustawionymi strefami; zależnie od urządzenia możliwe są też dane tempa kroków.",
        "Wymagany czas wysiłku zależy od modelu. Podwójny wkład do celu nie oznacza podwojenia fizycznego czasu ruchu.",
        ("minutes", "minutes_method"),
    )
for field, direction in {"ascent": "wznoszenia", "descent": "opadania"}.items():
    DESCRIPTIONS["monitoring." + field] = Explanation(
        "Skumulowana wysokość " + direction + " zapisana w monitoringu, w metrach.",
        "Garmin opisuje barometryczne wykrywanie zmian wysokości na kompatybilnych urządzeniach.",
        "Sam ten zapis nie potwierdza zastosowanego czujnika. Metry wysokości nie są liczbą pięter.",
        ("elevation", "fit"),
    )

for message in ("nap_event", "sleep_disruption_severity_period"):
    DESCRIPTIONS[message + ".message_index"] = Explanation(
        "Techniczny indeks wiadomości FIT, z bitami flag i maską indeksu.",
        "Identyfikator zapisywany przez producenta w pliku; nie pochodzi z pomiaru fizjologicznego.",
        "Nie jest liczbą drzemek, przebudzeń ani poziomem zdrowia.",
        ("fit_protocol", "fit"),
        "fit_profile_only",
    )
for message in (
    "sleep_disruption_overnight_severity",
    "sleep_disruption_severity_period",
):
    DESCRIPTIONS[message + ".severity"] = Explanation(
        "Źródłowa kategoria nasilenia zakłóceń snu: none, low, medium lub high.",
        "Profil FIT definiuje klasy, ale nie ujawnia pełnego algorytmu ani zestawu czujników dla tego pola.",
        "Bez dodatkowego potwierdzenia nie utożsamiamy go z konkretną oceną oddychania lub diagnozą w Garmin Connect.",
        ("fit",),
        "fit_profile_only",
    )
for field, meaning in {
    "feedback": "Źródłowa kategoria informacji zwrotnej o drzemce (m.in. pora, długość i zapotrzebowanie).",
    "source": "Źródło zdarzenia drzemki: automatyczne, ręczne w urządzeniu lub ręczne w Garmin Connect.",
    "is_deleted": "Źródłowa flaga oznaczająca usunięcie zdarzenia drzemki.",
    "start_timezone_offset": "Przesunięcie czasu względem UTC na początku drzemki, w minutach.",
    "end_timezone_offset": "Przesunięcie czasu względem UTC na końcu drzemki, w minutach.",
}.items():
    DESCRIPTIONS["nap_event." + field] = Explanation(
        meaning,
        "Metadane zdarzenia Garmin. Automatyczna detekcja drzemki wykorzystuje okres nieaktywności; zdarzenie może też wprowadzić użytkownik.",
        "Kod metadanych nie jest wartością fizjologiczną; publiczny profil nie ujawnia wszystkich reguł wyznaczania feedback.",
        ("naps", "fit"),
    )


def parameter_description(parameter):
    """Return fresh JSON-compatible metadata; never infer unknown field meaning."""
    key = parameter["key"]
    entry = DESCRIPTIONS.get(
        key,
        Explanation(
            "Brak zweryfikowanego objaśnienia tego parametru w katalogu aplikacji.",
            "Nie ustalono publicznego opisu sposobu pomiaru ani algorytmu dla tego pola.",
            "Nazwa i wartość źródłowa pozostają zachowane; aplikacja nie zgaduje interpretacji.",
            ("fit",),
            "not_documented",
        ),
    )
    if key in MEAN_PARAMETERS:
        presentation = "Dzień w UI pokazuje próbki. MCP i dłuższe okresy używają średniej poprawnych próbek, ważonej ich liczbą, bez ważenia czasem i wypełniania luk. Wynik może różnić się od podsumowania Garmin Connect."
    elif parameter.get("representation") == "source_summary":
        presentation = "Gotowe podsumowanie producenta. Przy nieznanym czasie pomiaru dzień archiwum jest tylko metadanymi, nie potwierdzonym czasem pomiaru."
    else:
        presentation = "UI prezentuje wartości źródłowe. Kody kategorii i stany liczników nie są średnią pomiaru fizjologicznego."
    return dict(
        version=VERSION,
        language="pl-PL",
        reviewed_on=REVIEWED_ON,
        meaning=entry.meaning,
        measurement=entry.measurement,
        limitations=entry.limitations,
        presentation=presentation,
        evidence=entry.evidence,
        sources=[
            dict(title=SOURCES[source][0], url=SOURCES[source][1])
            for source in entry.sources
        ],
    )
