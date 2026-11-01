"""Difference classification; numeric measurements are kept out of the report."""

import math
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime

from garmin_database.adapters.outbound.postgres.queries import bounds
from garmin_database.domain.aggregation import MEAN_PARAMETERS
from scripts.garmin_reference import HR, HRV, RESP, SLEEP, SPO2, STRESS, ZONE

FALLBACK = {
    "hr": [
        HR,
        "monitoring_hr_data.current_day_resting_heart_rate",
        "monitoring_hr_data.resting_heart_rate",
    ],
    "hrv": [
        HRV,
        "hrv_status_summary.last_night_average",
        "hrv_status_summary.last_night_5_min_high",
        "hrv_status_summary.weekly_average",
    ],
    "respiration": [RESP],
    "spo2": [SPO2],
    "stress": [STRESS],
    "sleep": ["sleep_assessment.overall_sleep_score"],
}


def selected_keys(ref, catalog):
    keys = {p["parameter"] for p in ref["points"]} | {
        p["parameter"] for p in ref["cards"] if p["parameter"]
    }
    keys.update(FALLBACK.get(ref["topic"], []))
    return sorted(keys & catalog.keys())


def numeric(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def equal(a, b):
    return numeric(a) and numeric(b) and math.isclose(a, b, rel_tol=0, abs_tol=1e-7)


def row_point(row, parameter):
    if row["validity"] != "valid" or not numeric(row["value"]):
        return None
    if row["time"]:
        return datetime.fromisoformat(row["time"]).timestamp(), row["value"]
    if parameter["representation"] == "source_summary":
        day = date.fromisoformat(row["requested_day"])
        return bounds(day, day)[0] / 1000, row["value"]
    return None


def export_daily(data):
    return [dict(zip(data["history"]["columns"], r)) for r in data["history"]["data"]]


def daily_mean_points(rows):
    return [
        (
            bounds(date.fromisoformat(r["day"]), date.fromisoformat(r["day"]))[0]
            / 1000,
            r["mean"],
        )
        for r in rows or []
        if numeric(r["mean"])
    ]


def channel_points(data, key, channel, begin, end, parameter):
    if channel == "chart":
        return [(t / 1000, v) for t, v, _ in data["chart"] if numeric(v)]
    if begin != end and key in MEAN_PARAMETERS:
        rows = data["mcp"] if channel == "mcp" else export_daily(data)
        return daily_mean_points(rows)
    return [
        point
        for r in data[channel] or []
        if (point := row_point(r, parameter)) is not None
    ]


def interval_diagnostic(reference, actual):
    ordered = sorted(set(actual))
    times = [t for t, _ in ordered]
    matched = 0
    for point in reference:
        instant = datetime.fromisoformat(point["time"]).timestamp()
        index = bisect_right(times, instant) - 1
        if 0 <= index < len(times) - 1 and times[index + 1] - times[index] <= 43200:
            matched += equal(point["value"], ordered[index][1])
    return matched


def shifted_matches(reference, indexed, shift):
    return sum(
        any(
            equal(p["value"], v)
            for v in indexed.get(
                datetime.fromisoformat(p["time"]).timestamp() + shift, []
            )
        )
        for p in reference
    )


def compare_points(reference, actual, phase=False):
    indexed = defaultdict(list)
    for t, v in actual:
        indexed[t].append(v)
    shifts = {
        str(shift): shifted_matches(reference, indexed, shift)
        for shift in (0, -7200, -3600, 3600, 7200)
    }
    same_time = sum(
        datetime.fromisoformat(p["time"]).timestamp() in indexed for p in reference
    )
    result = dict(
        reference_points=len(reference),
        exact=shifts["0"],
        missing_timestamp=len(reference) - same_time,
        differing_value=same_time - shifts["0"],
        shift_diagnostic=shifts,
    )
    if phase:
        result["bounded_state_continuation_diagnostic"] = interval_diagnostic(
            reference, actual
        )
    return result


def observation_day(row):
    return (
        datetime.fromisoformat(row["time"]).astimezone(ZONE).date().isoformat()
        if row["time"]
        else row["requested_day"]
    )


def source_card_observations(data, channel):
    if channel == "chart":
        return [
            (datetime.fromtimestamp(t / 1000, ZONE).date().isoformat(), v)
            for t, v, _ in data["chart"]
            if numeric(v)
        ]
    return [
        (observation_day(r), r["value"])
        for r in data[channel] or []
        if r["validity"] == "valid" and numeric(r["value"])
    ]


def conflicting_source_days(data, channel):
    days = defaultdict(set)
    for day, value in source_card_observations(data, channel):
        days[day].add(value)
    return sum(len(values) > 1 for values in days.values())


def source_card_value(data, channel, begin, end):
    observations = source_card_observations(data, channel)
    latest = dict(observations)
    value = sum(latest.values()) / len(latest) if latest else None
    return (
        value,
        "last_per_day_then_unweighted_mean"
        if begin != end
        else "last_valid_source_observation",
    )


def reduce_values(values, operation):
    if not values:
        return None
    reducers = {"mean": lambda x: sum(x) / len(x), "minimum": min, "maximum": max}
    return reducers[operation](values)


def weighted_card_mean(daily):
    valid = [r for r in daily if r["mean"] is not None and r["valid_count"]]
    count = sum(r["valid_count"] for r in valid)
    return sum(r["mean"] * r["valid_count"] for r in valid) / count if count else None


def export_card_value(data, operation):
    daily = export_daily(data)
    if operation == "mean":
        return weighted_card_mean(daily), "weighted_export_daily_history"
    values = [r[operation] for r in daily if r.get(operation) is not None]
    return reduce_values(
        values, operation
    ), "export_daily_history" if values else "no_numeric_data"


def plot_card_value(data, card):
    values = [
        v
        for _, v, _ in data["chart"]
        if numeric(v) and not (card["parameter"] == STRESS and v < 0)
    ]
    return reduce_values(
        values, card["operation"]
    ), "derived_from_plot_points" if values else "no_numeric_data"


def daily_card_value(data, operation, channel):
    reducer, field = operation.split("_daily_")
    if channel == "chart":
        if field != "mean":
            return None, "daily_extrema_not_in_plot"
        values = [v for _, v, _ in data["chart"] if numeric(v)]
    else:
        daily = export_daily(data) if channel == "export" else data["mcp"] or []
        values = [r[field] for r in daily if numeric(r.get(field))]
    return reduce_values(values, reducer), operation


def card_value(data, card, channel, begin, end):
    operation = card["operation"]
    if operation == "source_daily_last":
        return source_card_value(data, channel, begin, end)
    if "_daily_" in operation:
        return daily_card_value(data, operation, channel)
    if channel == "mcp":
        return data.get("mcp_period", {}).get(operation), data.get(
            "mcp_period_method", "get_period_stats"
        )
    if channel == "export":
        return export_card_value(data, operation)
    return plot_card_value(data, card)


def compare_card(data, card, channel, begin, end):
    if "range_start" in card:
        begin, end = (
            date.fromisoformat(card["range_start"]),
            date.fromisoformat(card["range_end"]),
        )
        data = scoped_card_data(data, begin, end)
    actual, method = card_value(data, card, channel, begin, end)
    if actual is None:
        return dict(status="no_channel_value", method=method)
    exact = equal(actual, card["value"])
    rounded = equal(round(actual, card["precision"]), card["value"])
    result = dict(
        status="exact"
        if exact
        else "display_rounding_match"
        if rounded
        else "different",
        method=method,
        semantic_constraint=card["reason"],
    )
    conflicts = (
        conflicting_source_days(data, channel)
        if card["operation"] == "source_daily_last"
        else 0
    )
    if conflicts:
        result.update(
            status="ambiguous_source_observations",
            conflicting_days=conflicts,
            last_candidate_status=result["status"],
            method="no_canonical_source_selection",
            candidate_method=method,
        )
    return result


def scoped_observations(rows, begin, end):
    return [
        r
        for r in rows or []
        if begin.isoformat() <= observation_day(r) <= end.isoformat()
    ]


def scoped_mcp(data, begin, end):
    records = data["mcp"] or []
    if records and "day" in records[0]:
        daily = [r for r in records if begin.isoformat() <= r["day"] <= end.isoformat()]
        stats = dict(
            mean=weighted_card_mean(daily),
            minimum=reduce_values(
                [r["minimum"] for r in daily if r["minimum"] is not None], "minimum"
            ),
            maximum=reduce_values(
                [r["maximum"] for r in daily if r["maximum"] is not None], "maximum"
            ),
        )
        return daily, stats
    return scoped_observations(records, begin, end), dict(
        mean=None, minimum=None, maximum=None
    )


def scoped_card_data(data, begin, end):
    result = dict(data)
    result["chart"] = [
        (t, v, label)
        for t, v, label in data["chart"]
        if begin <= datetime.fromtimestamp(t / 1000, ZONE).date() <= end
    ]
    result["export"] = scoped_observations(data["export"], begin, end)
    result["mcp"], result["mcp_period"] = scoped_mcp(data, begin, end)
    result["mcp_period_method"] = "get_daily_scoped_to_table_row"
    if "day" in data["history"]["columns"]:
        daily = [
            r
            for r in export_daily(data)
            if begin.isoformat() <= r["day"] <= end.isoformat()
        ]
        result["history"] = dict(
            data["history"],
            data=[[r[c] for c in data["history"]["columns"]] for r in daily],
        )
    return result


def metric_availability(bundle, key, channel):
    if key not in bundle["data"]:
        return "metric_not_stored"
    if channel == "mcp" and bundle["data"][key]["mcp"] is None:
        return "not_exposed"
    return None


def point_variant(points, bundle, key, channel, begin, end, parameter):
    missing = metric_availability(bundle, key, channel)
    if missing:
        return dict(status=missing)
    actual = channel_points(bundle["data"][key], key, channel, begin, end, parameter)
    return compare_points(points, actual, phase=key == SLEEP)


def point_feature(ref, bundle, catalog, key, method, points):
    begin, end = ref["start"], ref["end"]
    return dict(
        kind="points",
        label=method,
        parameter=key,
        points_outside_visible_dates=sum(
            not begin <= datetime.fromisoformat(p["time"]).date() <= end for p in points
        ),
        channels={
            channel: point_variant(
                points, bundle, key, channel, begin, end, catalog.get(key)
            )
            for channel in ["chart", "mcp", "export"]
        },
    )


def card_variant(ref, bundle, card, channel):
    key = card["parameter"]
    if not key or key not in bundle["data"]:
        return dict(status="no_stored_equivalent")
    if card["value"] is None:
        return dict(status="reference_not_numeric")
    missing = metric_availability(bundle, key, channel)
    if missing:
        return dict(status=missing)
    return compare_card(bundle["data"][key], card, channel, ref["start"], ref["end"])


def card_feature(ref, bundle, card):
    feature = {k: v for k, v in card.items() if k not in {"value", "precision"}}
    feature.update(
        kind="card",
        channels={
            channel: card_variant(ref, bundle, card, channel)
            for channel in ["chart", "mcp", "export"]
        },
    )
    return feature


def unavailable_feature(label, status):
    return dict(
        kind="reference",
        label=label,
        parameter=None,
        channels={k: dict(status=status) for k in ["chart", "mcp", "export"]},
    )


def source_differences(ref, bundle, catalog):
    output = {k: v for k, v in ref.items() if k not in {"points", "cards"}}
    output.update(
        start=ref["start"].isoformat() if ref["start"] else None,
        end=ref["end"].isoformat() if ref["end"] else None,
        features=[],
    )
    if bundle is None:
        output["channel_status"] = dict.fromkeys(
            ["chart", "mcp", "export"], "reference_view_or_date_unavailable"
        )
        output["features"] = [
            unavailable_feature(
                "Nieprawidłowy lub niekompletny materiał referencyjny",
                "reference_view_or_date_unavailable",
            )
        ]
        return output
    output.update(
        channel_audit=bundle["parameters"],
        export_directory=bundle["export_directory"],
        export_month_directory=bundle.get("export_month_directory"),
        revision=bundle["revision"],
    )
    groups = defaultdict(list)
    for point in ref["points"]:
        groups[(point["parameter"], point["method"])].append(point)
    output["features"] = [
        point_feature(ref, bundle, catalog, key, method, points)
        for (key, method), points in sorted(groups.items())
    ]
    output["features"].extend(card_feature(ref, bundle, card) for card in ref["cards"])
    if not output["features"]:
        output["features"].append(
            unavailable_feature(
                "Wykres bez liczbowych danych referencyjnych w DOM",
                "no_exact_reference_values",
            )
        )
    return output
