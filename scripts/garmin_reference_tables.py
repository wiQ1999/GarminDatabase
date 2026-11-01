"""Daily/weekly table cells and accessible scalar chart summaries."""

import re
from datetime import date

from scripts.garmin_html import Node
from scripts.garmin_reference import HR, NUMBER, PL_MONTHS, STRESS, numeric_card


def month_day(text, default_month=None):
    match = re.fullmatch(r"\s*([^\W\d_]+)?\s*(\d{1,2})\s*", text)
    if not match:
        raise ValueError("table_date_format")
    month = PL_MONTHS[match[1][:3]] if match[1] else default_month
    return month, int(match[2])


def table_range(label, begin, end):
    explicit = list(map(int, re.findall(r",\s*(\d{4})", label)))
    clean = re.sub(r",\s*\d{4}", "", label)
    pieces = clean.split("-")
    first = month_day(pieces[0])
    last = month_day(pieces[-1], first[0])
    years = explicit[:1] or range(begin.year, end.year + 1)
    for year in years:
        last_year = explicit[-1] if explicit else year + int(last < first)
        a, b = date(year, *first), date(last_year, *last)
        if begin <= a <= b <= end:
            return a, b
    raise ValueError("table_date_outside_visible_range")


def table_metric(subject, header):
    mapping = {
        ("sleep", "Wynik"): (
            "sleep_assessment.overall_sleep_score",
            "source_daily_last",
            "source",
        ),
        ("sleep", "Śr. wynik"): (
            "sleep_assessment.overall_sleep_score",
            "source_daily_last",
            "weekly_mean_of_daily_source_scores",
        ),
        ("hr", "Spoczynkowe"): (
            "monitoring_hr_data.current_day_resting_heart_rate",
            "source_daily_last",
            "source",
        ),
        ("hr", "Wysokie"): (HR, "maximum", "source_sampling_or_scope_may_differ"),
        ("stress", "Śr."): (STRESS, "mean", "different_aggregation_possible"),
    }
    return mapping.get(
        (subject, header),
        (None, "unavailable", "no_stored_equivalent_or_no_documented_conversion"),
    )


def row_cells(row, tag):
    return [c for c in row.children if isinstance(c, Node) and c.tag == tag]


def table_row_cards(row, headers, subject, begin, end, index):
    cells = row_cells(row, "td")
    if not cells:
        return []
    label = cells[0].text()
    a, b = table_range(label, begin, end)
    cards = []
    for header, cell in zip(headers[1:], cells[1:]):
        text = cell.text()
        key, operation, reason = table_metric(subject, header)
        fraction = re.search(r"[.,](\d+)", text)
        cards.append(
            dict(
                index=index + len(cards),
                label=f"Tabela {label} · {header}",
                parameter=key,
                operation=operation,
                reason=reason,
                value=numeric_card(text),
                precision=len(fraction[1]) if fraction else 0,
                range_start=a.isoformat(),
                range_end=b.isoformat(),
            )
        )
    return cards


def data_tables(page):
    for table in (n for n in page.root.walk() if n.tag == "table"):
        headers = [n.text() for n in table.walk() if n.tag == "th"]
        if headers and headers[0] == "Data":
            yield table, headers


def table_cards(page, subject, begin, end):
    if begin is None:
        return []
    cards = []
    for table, headers in data_tables(page):
        for row in (n for n in table.walk() if n.tag == "tr"):
            cards.extend(
                table_row_cards(row, headers, subject, begin, end, len(cards) + 1)
            )
    return cards


def accessible_cards(page):
    metrics = {
        "Średnia z 7 dni": (
            "hrv_status_summary.weekly_average",
            "source_daily_last",
            "source",
        ),
        "Śr. SpO₂": (
            "spo2_data.reading_spo2",
            "mean",
            "different_aggregation_possible",
        ),
        "Poziom stresu": (STRESS, "mean", "different_aggregation_possible"),
    }
    result = []
    for node in page.root.walk():
        match = re.fullmatch(
            rf"\s*({NUMBER})%?\s*(.*?)\. Highcharts interactive chart\.",
            node.attrs.get("aria-label", ""),
        )
        if not match or match[2] not in metrics:
            continue
        key, operation, reason = metrics[match[2]]
        result.append(
            dict(
                index=len(result) + 1,
                label="Podsumowanie dostępności · " + match[2],
                parameter=key,
                operation=operation,
                reason=reason,
                value=float(match[1].replace(",", ".")),
                precision=0,
            )
        )
    return result
