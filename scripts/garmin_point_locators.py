"""Point-level difference locators, without measurement values."""

import csv
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from garmin_database.adapters.outbound.filesystem.json_export import parameter_filename
from garmin_database.application.read_models import PRECISION
from garmin_database.domain.aggregation import MEAN_PARAMETERS
from scripts.garmin_channels import chart_expected, export_rows
from scripts.garmin_differences import channel_points, equal
from scripts.garmin_reference import reference


def load_verified_series(source, key):
    directory = Path(source["export_directory"])
    details = json.loads(
        (directory / "details" / parameter_filename(key)).read_text(encoding="utf-8")
    )
    history = json.loads(
        (directory / "history" / parameter_filename(key)).read_text(encoding="utf-8")
    )
    rows = export_rows(details)
    begin, end = map(date.fromisoformat, (source["start"], source["end"]))
    mcp = rows
    chart = [(t, json.loads(value), "") for t, value in chart_expected(rows, details)]
    if begin != end and key in MEAN_PARAMETERS:
        daily = [dict(zip(history["columns"], r)) for r in history["data"]]
        mcp = [
            dict(
                r,
                mean=round(r["mean"], PRECISION[key])
                if r["mean"] is not None
                else None,
            )
            for r in daily
        ]
        from scripts.garmin_differences import daily_mean_points

        chart = [(t * 1000, v, "") for t, v in daily_mean_points(daily)]
    return dict(chart=chart, mcp=mcp, export=rows, history=history), details, begin, end


def point_mismatch_rows(source, feature, points, actual, variant):
    indexed = defaultdict(list)
    for index, (instant, value) in enumerate(actual, 1):
        indexed[instant].append((index, value))
    matched = 0
    for index, point in points:
        instant = datetime.fromisoformat(point["time"]).timestamp()
        candidates = indexed.get(instant, [])
        if any(equal(point["value"], v) for _, v in candidates):
            matched += 1
            continue
        yield dict(
            source=source["file"],
            parameter=feature["parameter"],
            series_method=feature["label"],
            variant=variant,
            parsed_reference_point=index,
            html_time_assuming_warsaw=point["time"],
            reason="different_value" if candidates else "timestamp_absent",
            normalized_channel_indices=",".join(str(i) for i, _ in candidates),
            export_directory=source["export_directory"],
        )
    assert matched == feature["channels"][variant]["exact"]


def source_locators(source, reference_root):
    ref = reference(reference_root / source["file"])
    assert ref["sha256"] == source["sha256"]
    for feature in source["features"]:
        if feature["kind"] != "points":
            continue
        key = feature["parameter"]
        points = [
            (i, p)
            for i, p in enumerate(ref["points"], 1)
            if p["parameter"] == key and p["method"] == feature["label"]
        ]
        data, parameter, begin, end = load_verified_series(source, key)
        for variant in ["chart", "mcp", "export"]:
            audit_key = "export_details" if variant == "export" else variant
            assert source["channel_audit"][key][audit_key]["equal"]
            actual = channel_points(data, key, variant, begin, end, parameter)
            yield from point_mismatch_rows(source, feature, points, actual, variant)


def write_point_locators(report, output):
    if "reference_root" not in report:
        return
    fields = [
        "source",
        "parameter",
        "series_method",
        "variant",
        "parsed_reference_point",
        "html_time_assuming_warsaw",
        "reason",
        "normalized_channel_indices",
        "export_directory",
    ]
    with (output / "point-differences.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for source in report["sources"]:
            writer.writerows(source_locators(source, Path(report["reference_root"])))
