"""Offline reference extraction. Never execute scripts embedded in saved HTML."""

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime

from scripts.garmin_html import MONTHS, PHASES, ZONE, SavedPage

HR = "monitoring.heart_rate"
RESP = "respiration_rate.respiration_rate"
SPO2 = "spo2_data.reading_spo2"
STRESS = "stress_level.stress_level_value"
SLEEP = "sleep_level.sleep_level"
HRV = "hrv_value.value"
PL_MONTHS = dict(
    zip("Sty Lut Mar Kwi Maj Cze Lip Sie Wrz Paź Lis Gru".split(), range(1, 13))
)
EN_TIME = re.compile(
    r"\w+,\s*(\d{1,2})\s+([A-Za-z]{3}),\s*(\d{1,2}):(\d{2})(?::(\d{2}))?,\s*(.*)"
)
PL_DAY = re.compile(
    r"(Sty|Lut|Mar|Kwi|Maj|Cze|Lip|Sie|Wrz|Paź|Lis|Gru)\s+(\d{1,2}),\s*(.*)"
)
NUMBER = r"[-+]?\d+(?:[.,]\d+)?"
SOURCE_CARDS = {
    "Ocena jakości snu": "sleep_assessment.overall_sleep_score",
    "Śr. ocena jakości snu": "sleep_assessment.overall_sleep_score",
    "Średnia nocna": "hrv_status_summary.last_night_average",
    "Śr. HRV w ciągu nocy": "hrv_status_summary.last_night_average",
    "Najwyższa średnia 5-minutowa": "hrv_status_summary.last_night_5_min_high",
    "Śr. HRV z 7 dni": "hrv_status_summary.weekly_average",
    "Śr. tętno spoczynkowe z 7 dni": "monitoring_hr_data.resting_heart_rate",
    "Spoczynkowe": "monitoring_hr_data.current_day_resting_heart_rate",
    "Tętno spoczynkowe": "monitoring_hr_data.current_day_resting_heart_rate",
    "Średnie spoczynkowe": "monitoring_hr_data.current_day_resting_heart_rate",
    "Średnie tętno spoczynkowe": "monitoring_hr_data.current_day_resting_heart_rate",
    "Zmiana średniej temperatury skóry": "skin_temp_overnight.average_deviation",
}


def ancestors(node):
    while node is not None:
        yield node
        node = node.parent


def display_dates(text, year):
    parts = re.findall(r"([^\W\d_]+)\s+(\d{1,2})(?:,\s*(\d{4}))?", text)
    try:
        return [
            date(int(y or year), PL_MONTHS[m[:3].capitalize()], int(d))
            for m, d, y in parts
        ]
    except (KeyError, TypeError, ValueError):
        return []


def visible_range(page, filename):
    years = re.findall(r"\d{4}", filename)
    year = int(years[-1]) if years else None
    labels = [
        n.text()
        for n in page.root.walk()
        if n.has_class("NavigationComponent_datePickerContainer")
    ]
    if labels:
        dates = display_dates(labels[0], year)
        if dates:
            return dates[0], dates[-1], labels[0], "visible_picker"
    for node in page.root.walk():
        if node.has_class("ui-datepicker-trigger"):
            match = re.search(r",\s*([^\W\d_]+)\s+(\d+),\s*(\d{4})", node.text())
            if match:
                dates = display_dates(match[0], year)
                if dates:
                    return dates[0], dates[0], node.text(), "visible_picker"
    return None, None, "brak daty w widoku", "unavailable"


def topic(page):
    headings = [n.text() for n in page.root.walk() if n.tag in {"h1", "h2", "h3"}]
    for title, key in [
        ("Sen", "sleep"),
        ("Status HRV", "hrv"),
        ("Tętno", "hr"),
        ("Stres", "stress"),
        ("Oddech", "respiration"),
        ("Saturacja", "spo2"),
    ]:
        if title in headings:
            return key
    return "unrelated_or_incomplete"


def point_metric(suffix, context, subject):
    if suffix == "HRV":
        return HRV, "sample"
    if suffix.startswith("stress:"):
        return STRESS, "sample_or_status"
    if suffix in PHASES:
        return SLEEP, "phase_display"
    if "pulseOxYAxis" in context:
        return SPO2, "sample_or_resampled"
    if "respirationYAxis" in context:
        return RESP, "bin_statistic"
    if subject == "respiration" and suffix.startswith("Średnia podczas"):
        return RESP, "sleep_or_awake_mean"
    return None, "unmapped"


def parse_reference_point(label, year, context, subject):
    match = EN_TIME.fullmatch(label)
    if match and match[2] in MONTHS:
        instant = datetime(
            year,
            MONTHS[match[2]],
            int(match[1]),
            int(match[3]),
            int(match[4]),
            int(match[5] or 0),
            tzinfo=ZONE,
        )
        tail = match[6]
    else:
        match = PL_DAY.fullmatch(label)
        if not match:
            return None
        instant = datetime(year, PL_MONTHS[match[1]], int(match[2]), tzinfo=ZONE)
        tail = match[3]
    value = re.fullmatch(rf"({NUMBER})\.\s+(.+?)\.?", tail)
    if value is None:
        return None
    suffix = value[2].rstrip(".")
    key, method = point_metric(suffix, context, subject)
    if key is None:
        return None
    number = PHASES[suffix] if suffix in PHASES else float(value[1].replace(",", "."))
    return dict(time=instant.isoformat(), value=number, parameter=key, method=method)


def window_card_metric(label):
    mapping = {
        "Śr. tętno w nocy": HR,
        "Śr. SpO₂": SPO2,
        "Średnia częstotliwość oddechu": RESP,
        "Średnia podczas snu": RESP,
        "Średnia podczas wybudzenia": RESP,
    }
    key = mapping.get(label)
    return (key, "mean", "sleep_awake_scope_differs_from_calendar_day") if key else None


def extreme_card_metric(label, subject):
    kinds = {"hr": HR, "respiration": RESP, "stress": STRESS}
    if label == "Średnia wysokiego" and subject == "hr":
        return HR, "mean_daily_maximum", "source_sampling_or_scope_may_differ"
    if label in {"Wysokie", "Najwyższa"} and subject in kinds:
        return kinds[subject], "maximum", "source_sampling_or_scope_may_differ"
    if label in {"Najniższa", "Najniższa częstotliwość oddechu", "Najniższe SpO2"}:
        key = (
            SPO2
            if "SpO2" in label
            else RESP
            if subject in {"respiration", "sleep"}
            else STRESS
        )
        return key, "minimum", "source_sampling_or_scope_may_differ"
    return None


def card_metric(label, subject):
    if label in SOURCE_CARDS:
        return SOURCE_CARDS[label], "source_daily_last", "source"
    if label == "Średni poziom stresu":
        return (
            (
                "sleep_assessment.average_stress_during_sleep",
                "source_daily_last",
                "source",
            )
            if subject == "sleep"
            else (STRESS, "mean", "different_aggregation_possible")
        )
    return (
        window_card_metric(label)
        or extreme_card_metric(label, subject)
        or (
            None,
            "unavailable",
            "no_equivalent_stored_metric_or_no_documented_conversion",
        )
    )


def numeric_card(text):
    match = re.fullmatch(
        rf"\s*({NUMBER})\s*(?:ms|bpm|%|brpm|oddechów/min|°C)?\s*", text
    )
    return float(match[1].replace(",", ".")) if match else None


def parse_reference_range(label, year, context, subject):
    match = EN_TIME.fullmatch(label)
    if not match or match[2] not in MONTHS:
        return []
    values = re.fullmatch(
        rf"low:\s*({NUMBER}),\s*high:\s*({NUMBER})\.\s*(.+?)\.?", match[6]
    )
    if not values:
        return []
    key, method = point_metric(values[3].rstrip("."), context, subject)
    if not key:
        return []
    instant = datetime(
        year,
        MONTHS[match[2]],
        int(match[1]),
        int(match[3]),
        int(match[4]),
        int(match[5] or 0),
        tzinfo=ZONE,
    )
    return [
        dict(
            time=instant.isoformat(),
            value=float(values[i].replace(",", ".")),
            parameter=key,
            method=method + "_" + side,
        )
        for i, side in [(1, "minimum"), (2, "maximum")]
    ]


def reference_points(page, year, subject):
    points, unparsed = [], Counter()
    for node in page.root.walk():
        if not node.has_class("highcharts-point") or not node.attrs.get("aria-label"):
            continue
        context = " ".join(
            n.attrs.get("aria-label", "") for n in ancestors(node.parent)
        )
        label = node.attrs["aria-label"]
        point = parse_reference_point(label, year, context, subject)
        if point:
            points.append(point)
            continue
        ranges = parse_reference_range(label, year, context, subject)
        if ranges:
            points.extend(ranges)
        else:
            unparsed[re.sub(NUMBER, "#", label)] += 1
    return points, dict(unparsed)


def reference_cards(page, subject, period=False):
    cards = []
    for index, (name, text) in enumerate(page.cards(), 1):
        key, operation, reason = card_metric(name, subject)
        if (
            period
            and subject == "stress"
            and operation in {"mean", "minimum", "maximum"}
        ):
            operation += "_daily_mean"
        fraction = re.search(r"[.,](\d+)", text)
        cards.append(
            dict(
                index=index,
                label=name,
                parameter=key,
                operation=operation,
                reason=reason,
                value=numeric_card(text),
                precision=len(fraction[1]) if fraction else 0,
            )
        )
    return cards


def filename_day_mismatch(declared, begin, end):
    if begin is None or not re.match(r"\d{4}_\d{2}_\d{2}-[a-z]+$", declared):
        return False
    named = date(*map(int, declared[:10].split("_")))
    return begin != named or end != named


def reference_issues(path, subject, begin, end):
    declared = path.stem
    issues = []
    if subject == "unrelated_or_incomplete":
        issues.append("brak oczekiwanego widoku danych")
    if subject == "sleep" and "stres" in declared:
        issues.append("nazwa wskazuje stres, DOM zawiera sen")
    if filename_day_mismatch(declared, begin, end):
        issues.append("data/noc w DOM różni się od nazwy pliku")
    if begin and "09_04-10_31" in declared and begin != date(2026, 9, 4):
        issues.append("DOM nie obejmuje deklarowanego początku 4 września")
    return issues


def reference(path):
    from scripts.garmin_reference_tables import accessible_cards, table_cards

    page = SavedPage()
    page.feed(path.read_text(encoding="utf-8"))
    begin, end, label, origin = visible_range(page, path.name)
    subject = topic(page)
    points, unparsed = reference_points(page, (end or date(2026, 1, 1)).year, subject)
    identity = json.dumps(
        dict(
            topic=subject,
            start=str(begin),
            end=str(end),
            points=points,
            cards=list(page.cards()),
            tables=[n.text() for n in page.root.walk() if n.tag == "table"],
        ),
        sort_keys=True,
        ensure_ascii=False,
    )
    return dict(
        file=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        content_sha256=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        topic=subject,
        start=begin,
        end=end,
        visible_range=label,
        range_origin=origin,
        reference_issues=reference_issues(path, subject, begin, end),
        points=points,
        cards=reference_cards(page, subject, begin != end)
        + table_cards(page, subject, begin, end)
        + accessible_cards(page),
        unparsed_point_formats=unparsed,
    )
