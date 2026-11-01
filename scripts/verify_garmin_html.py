"""Compare saved Garmin HTML with read-only SQL/chart/MCP; report counts only."""

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.queries import Queries
from garmin_database.application.mcp_metrics import MCP_PARAMETERS
from garmin_database.bootstrap.mcp import create_service
from scripts.garmin_html import MONTHS, PHASES, ZONE, SavedPage
from scripts.garmin_reference import visible_range

POINT = re.compile(
    r"\w+,\s*(\d{1,2})\s+([A-Za-z]{3}),\s*(\d{1,2}):(\d{2})(?::(\d{2}))?,\s*(-?\d+(?:\.\d+)?)\.\s+(.+)"
)
CARDS = {
    "Ocena jakości snu": "sleep_assessment.overall_sleep_score",
    "Średnia nocna": "hrv_status_summary.last_night_average",
    "Najwyższa średnia 5-minutowa": "hrv_status_summary.last_night_5_min_high",
    "Spoczynkowe": "monitoring_hr_data.current_day_resting_heart_rate",
    "Tętno spoczynkowe": "monitoring_hr_data.current_day_resting_heart_rate",
    "Śr. tętno spoczynkowe z 7 dni": "monitoring_hr_data.resting_heart_rate",
}


@dataclass(frozen=True)
class Observation:
    instant: datetime
    value: float
    parameter: str


def parse_point(label, year):
    match = POINT.fullmatch(label)
    if not match or match[2] not in MONTHS:
        return None
    suffix = match[7].rstrip(".")
    key, value = None, float(match[6])
    if suffix == "HRV":
        key = "hrv_value.value"
    elif suffix.startswith("stress:"):
        key = "stress_level.stress_level_value"
    elif suffix in PHASES:
        key, value = "sleep_level.sleep_level", PHASES[suffix]
    if key is None:
        return None
    return Observation(
        datetime(
            year,
            MONTHS[match[2]],
            int(match[1]),
            int(match[3]),
            int(match[4]),
            int(match[5] or 0),
            tzinfo=ZONE,
        ),
        value,
        key,
    )


def same_number(left, right):
    return isinstance(right, (int, float)) and math.isclose(left, right, abs_tol=1e-7)


def read_mcp(service, begin, end, key):
    result, cursor = [], None
    while True:
        page = service.source_history(
            begin.isoformat(), end.isoformat(), key, cursor, limit=500
        )
        result.extend(dict(zip(page["columns"], row)) for row in page["data"])
        cursor = page["next_cursor"]
        if cursor is None:
            return result


def utc_signature(row):
    instant = (
        datetime.fromisoformat(row["time"]).astimezone(ZoneInfo("UTC")).isoformat()
        if row["time"]
        else None
    )
    return instant, row["value"], row["validity"], row["requested_day"]


def timed_numeric(row):
    return (
        row["time"]
        and row["validity"] == "valid"
        and isinstance(row["value"], (int, float))
    )


def compare_channels(queries, service, parameter, begin, end):
    rows = list(queries.rows(parameter, begin, end))
    mcp = read_mcp(service, begin, end, parameter["key"])
    expected = [utc_signature(r) for r in rows]
    actual = [utc_signature(r) for r in mcp]
    chart = []
    for offset in range((end - begin).days + 1):
        day = begin + timedelta(days=offset)
        chart.extend(queries.chart(parameter, day, day)[0])
    sql_points = [
        (int(datetime.fromisoformat(r["time"]).timestamp() * 1000), r["value"])
        for r in rows
        if timed_numeric(r)
    ]
    chart_points = [(stamp, value) for stamp, value, _ in chart if value is not None]
    timed_chart = Counter(chart_points)
    chart_match = all(
        timed_chart[p] >= count for p, count in Counter(sql_points).items()
    )
    return rows, dict(
        sql_rows=len(rows), mcp_equal=expected == actual, timed_chart_equal=chart_match
    )


def compare_points(points, rows):
    index = {}
    for row in rows:
        if row["time"] and row["validity"] == "valid":
            stamp = int(datetime.fromisoformat(row["time"]).timestamp())
            index.setdefault(stamp, []).append(row["value"])
    shifts = {}
    for shift in (0, -7200, -3600, 3600, 7200):
        matched = sum(
            any(
                same_number(p.value, v)
                for v in index.get(int(p.instant.timestamp()) + shift, [])
            )
            for p in points
        )
        shifts[str(shift)] = matched
    return dict(
        html_points=len(points),
        exact_matches=shifts["0"],
        time_shift_diagnostics=shifts,
    )


def check_point_groups(points, queries, service, catalog):
    checks, channels = {}, {}
    for key in sorted({p.parameter for p in points}):
        if key not in catalog:
            checks[key] = dict(status="missing_parameter")
            continue
        selected = [p for p in points if p.parameter == key]
        begin, end = (
            min(p.instant.date() for p in selected),
            max(p.instant.date() for p in selected),
        )
        rows, channels[key] = compare_channels(
            queries,
            service,
            catalog[key],
            begin - timedelta(days=1),
            min(end + timedelta(days=1), datetime.now(ZONE).date()),
        )
        checks[key] = compare_points(selected, rows)
    return checks, channels


def card_comparison(key, expected, rows):
    values = {r["value"] for r in rows if r["validity"] == "valid"}
    return dict(
        parameter=key,
        matched=len(values) == 1 and same_number(expected, next(iter(values))),
        source_rows=len(rows),
        method="unique_valid_source_observation",
        status="ambiguous_source_observations" if len(values) > 1 else "compared",
    )


def check_cards(path, page, cards, queries, service, catalog):
    card_checks, channels = [], {}
    day, end, _, _ = visible_range(page, path.name)
    if day is not None and day == end:
        for label, text in cards:
            key = CARDS.get(label)
            value = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:ms|bpm)?\s*", text)
            if key not in catalog or value is None:
                continue
            rows, channels[key] = compare_channels(
                queries, service, catalog[key], day, day
            )
            card_checks.append(
                card_comparison(key, float(value[1].replace(",", ".")), rows)
            )
    return card_checks, channels


def check_file(path, queries, service, catalog):
    page = SavedPage()
    page.feed(path.read_text(encoding="utf-8"))
    _, end, _, _ = visible_range(page, path.name)
    labels = [
        n.attrs["aria-label"]
        for n in page.root.walk()
        if n.attrs.get("aria-label") and n.has_class("highcharts-point")
    ]
    points = (
        [p for label in labels if (p := parse_point(label, end.year))] if end else []
    )
    checks, channels = check_point_groups(points, queries, service, catalog)
    cards = list(page.cards())
    card_checks, card_channels = check_cards(
        path, page, cards, queries, service, catalog
    )
    channels.update(card_channels)
    return dict(
        file=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        numeric_aria_points=len(labels),
        comparable_points=len(points),
        cards=len(cards),
        point_checks=checks,
        card_checks=card_checks,
        channels=channels,
        limitations=[
            "SVG bez liczbowej etykiety nie pozwala odzyskać dokładnej wartości.",
            "Średnie snu/czuwania, oceny Garmin i średnie próbek aplikacji mają odrębną semantykę.",
        ],
    )


def report_items(results, section):
    for result in results:
        values = result[section]
        yield from values.values() if isinstance(values, dict) else values


def channel_summary(channels):
    return dict(
        channel_checks=len(channels),
        sql_mcp_equal=bool(channels) and all(c["mcp_equal"] for c in channels),
        sql_timed_chart_equal=bool(channels)
        and all(c["timed_chart_equal"] for c in channels),
    )


def comparison_summary(results):
    channels = list(report_items(results, "channels"))
    points = [p for p in report_items(results, "point_checks") if "html_points" in p]
    cards = list(report_items(results, "card_checks"))
    return dict(
        **channel_summary(channels),
        html_comparable_points=sum(p["html_points"] for p in points),
        html_exact_points=sum(p["exact_matches"] for p in points),
        source_card_checks=len(cards),
        source_card_matches=sum(c["matched"] for c in cards),
        views_without_exact_comparison=sum(not r["channels"] for r in results),
        html_conclusion="requires_semantic_review; no automatic claim of full conformity",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("verification"))
    parser.add_argument("--settings-file", type=Path)
    parser.add_argument(
        "--report", type=Path, default=Path("local-notes/garmin-verification.json")
    )
    args = parser.parse_args(argv)
    settings = Settings.load(args.settings_file)
    original_path = args.settings_file
    original = original_path.read_bytes() if original_path is not None else None
    db = Database(settings.data_dir, settings.database_dsn)
    queries = Queries(db)
    catalog = {p["key"]: p for p in queries.parameters() if p["key"] in MCP_PARAMETERS}
    with TemporaryDirectory(prefix="garmin-verify-") as temp:
        path = Path(temp) / "settings.json"
        replace(
            settings,
            mcp_enabled=True,
            mcp_parameters=sorted(catalog),
            settings_version=2,
            export_parameters=settings.export_parameters or [],
        ).save(path)
        service = create_service(path)
        paths = (
            [args.input] if args.input.is_file() else sorted(args.input.glob("*.html"))
        )
        results = []
        for index, page in enumerate(paths, 1):
            results.append(check_file(page, queries, service, catalog))
            print(json.dumps(dict(checked=index, total=len(paths))), flush=True)
    report = dict(
        files=results,
        summary=comparison_summary(results),
        original_settings_unchanged=original is None
        or original_path.read_bytes() == original,
        report_contains_measurements=False,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                files=len(results),
                channel_checks=sum(len(r["channels"]) for r in results),
                report=str(args.report),
            )
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("Verification failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
