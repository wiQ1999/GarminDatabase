"""Read real chart queries, real MCP stdio pages and production JSON export files."""

import json
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import patch

from garmin_database.adapters.outbound.filesystem.json_export import (
    JSONExport,
    parameter_filename,
)
from garmin_database.adapters.outbound.filesystem.settings_json import SettingsStore
from garmin_database.adapters.outbound.postgres.queries import Queries, bounds
from garmin_database.adapters.outbound.postgres.readings import DataAccess
from garmin_database.adapters.outbound.postgres.summaries import Summaries
from garmin_database.application.mcp_metrics import MCP_PARAMETERS
from garmin_database.application.read_models import (
    DAILY_COLUMNS,
    PERIOD_COLUMNS,
    PRECISION,
    summary_columns,
)
from garmin_database.application.use_cases.export_data import Exporter
from garmin_database.domain.aggregation import (
    MEAN_PARAMETERS,
    has_chart_summary,
    monthly_summaries,
    period_summary,
)
from scripts.garmin_independent_summaries import daily_audit


def stamp(value):
    return (
        datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
        if value
        else None
    )


def scalar(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def signature(row):
    return (
        stamp(row["time"]),
        scalar(row["value"]),
        row["validity"],
        row["requested_day"],
    )


def difference(expected, actual):
    a, b = Counter(expected), Counter(actual)
    return dict(
        expected=sum(a.values()),
        actual=sum(b.values()),
        missing=sum((a - b).values()),
        extra=sum((b - a).values()),
        equal=a == b,
    )


def export_rows(document):
    result = []
    for record in document["data"]:
        row = dict(zip(document["columns"], record))
        source = document["sources"][row["source"]]
        result.append(
            dict(
                time=row["time"],
                value=row["value"],
                validity=document["validity_labels"][row["validity"]],
                requested_day=source["requested_day"],
            )
        )
    return result


def chart_expected(rows, parameter):
    result = []
    for row in rows:
        if row["time"]:
            instant = int(datetime.fromisoformat(row["time"]).timestamp() * 1000)
        elif parameter["representation"] == "source_summary":
            day = date.fromisoformat(row["requested_day"])
            instant = bounds(day, day)[0]
        else:
            continue
        value = (
            row["value"]
            if row["validity"] == "valid" and isinstance(row["value"], (int, float))
            else None
        )
        result.append((instant, scalar(value)))
    return result


class FixedReadings:
    def __init__(self, snapshot):
        self.value = snapshot

    @contextmanager
    def snapshot(self, stop=None):
        yield self.value


class Wire:
    def __init__(self, session):
        self.session = session
        self.calls = Counter()

    async def call(self, name, arguments, revision):
        self.calls[name] += 1
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            raise RuntimeError("mcp_" + name)
        if (
            len(
                result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")
            )
            > 16384
        ):
            raise RuntimeError("mcp_response_limit")
        payload = result.structuredContent
        if payload["data_revision"] != revision:
            raise RuntimeError("dataset_changed")
        return payload

    async def observations(self, key, begin, end, revision):
        records, cursor, seen = [], None, set()
        name = "get_samples" if begin == end else "get_source_history"
        while True:
            args = (
                dict(day=begin.isoformat(), parameter=key, limit=500)
                if begin == end
                else dict(
                    date_from=begin.isoformat(),
                    date_to=end.isoformat(),
                    parameter=key,
                    limit=500,
                )
            )
            if cursor:
                args["cursor"] = cursor
            payload = await self.call(name, args, revision)
            records.extend(
                dict(zip(payload["columns"], row)) for row in payload["data"]
            )
            cursor = payload["next_cursor"]
            if cursor is None:
                return records
            if cursor in seen:
                raise RuntimeError("cursor_cycle")
            seen.add(cursor)

    async def daily(self, key, begin, end, revision):
        records, cursor = [], None
        while True:
            args = dict(
                date_from=begin.isoformat(), date_to=end.isoformat(), metrics=[key]
            )
            if cursor:
                args["cursor"] = cursor
            payload = await self.call("get_daily", args, revision)
            table = payload["series"][0]
            records.extend(dict(zip(table["columns"], row)) for row in table["data"])
            cursor = payload["next_cursor"]
            if cursor is None:
                return records

    async def monthly(self, key, begin, end, revision):
        records, cursor = [], None
        while True:
            args = dict(
                date_from=begin.isoformat(),
                date_to=end.isoformat(),
                metrics=[key],
                period="month",
            )
            if cursor:
                args["cursor"] = cursor
            payload = await self.call("get_history", args, revision)
            table = payload["series"][0]
            records.extend(dict(zip(table["columns"], r)) for r in table["data"])
            cursor = payload["next_cursor"]
            if cursor is None:
                return records


def chart_audit(parameter, begin, end, rows, daily, points):
    if begin != end and not has_chart_summary(parameter):
        return dict(status="unsupported_period", plotted=len(points))
    expected = chart_expected(rows, parameter)
    if begin != end and parameter["key"] in MEAN_PARAMETERS:
        expected = [
            (
                bounds(date.fromisoformat(r["day"]), date.fromisoformat(r["day"]))[0],
                scalar(r["mean"]),
            )
            for r in daily
        ]
    return difference(expected, [(t, scalar(v)) for t, v, _ in points])


def history_audit(parameter, rows, daily, history):
    if "sources" in history:
        return difference(map(signature, rows), map(signature, export_rows(history)))
    columns = summary_columns(parameter, "day")
    return difference(
        (scalar([r[c] for c in columns]) for r in daily), map(scalar, history["data"])
    )


def normalized_daily(row, precision=None):
    return normalized_summary(row, DAILY_COLUMNS, precision)


def normalized_summary(row, columns, precision=None):
    def field(column):
        value = row[column]
        if column in {"first_time", "last_time"}:
            return stamp(value)
        if (
            precision is not None
            and column in {"mean", "minimum", "maximum"}
            and value is not None
        ):
            return round(value, precision)
        return value

    return [field(c) for c in columns]


async def mcp_audit(wire, key, begin, end, revision, rows, daily):
    if key not in MCP_PARAMETERS:
        return None, dict(status="not_exposed_by_public_contract")
    if begin == end or key not in MEAN_PARAMETERS:
        records = await wire.observations(key, begin, end, revision)
        return records, difference(map(signature, rows), map(signature, records))
    records = await wire.daily(key, begin, end, revision)
    precision = PRECISION[key]
    audit = difference(
        (scalar(normalized_daily(r, precision)) for r in daily),
        (scalar(normalized_daily(r)) for r in records),
    )
    audit["rounded_mean_days"] = sum(
        r["mean"] is not None and round(r["mean"], precision) != r["mean"]
        for r in daily
    )
    return records, audit


def read_export(directory, kind, key):
    return json.loads(
        (directory / kind / parameter_filename(key)).read_text(encoding="utf-8")
    )


def monthly_export_audit(parameter, rows, daily, history, begin, end):
    if "sources" in history:
        return difference(map(signature, rows), map(signature, export_rows(history)))
    columns = summary_columns(parameter, "month")
    expected = (
        [r["day"] if c == "month" else r[c] for c in columns]
        for r in monthly_summaries(daily, begin, end)
    )
    return difference(map(scalar, expected), map(scalar, history["data"]))


async def mean_statistics_audit(wire, key, begin, end, revision, daily):
    args = dict(date_from=begin.isoformat(), date_to=end.isoformat(), metrics=[key])
    payload = await wire.call("get_period_stats", args, revision)
    table = payload["series"][0]
    actual = dict(zip(table["columns"], table["data"][0]))
    expected = period_summary(daily, begin, end)
    precision = PRECISION[key]
    period = difference(
        [scalar(normalized_summary(expected, PERIOD_COLUMNS, precision))],
        [scalar(normalized_summary(actual, PERIOD_COLUMNS))],
    )
    months = await wire.monthly(key, begin, end, revision)
    columns = ["month", "mean", "minimum", "maximum", *PERIOD_COLUMNS[5:]]
    expected_months = [
        dict(r, month=r["day"]) for r in monthly_summaries(daily, begin, end)
    ]
    monthly = difference(
        (scalar(normalized_summary(r, columns, precision)) for r in expected_months),
        (scalar(normalized_summary(r, columns)) for r in months),
    )
    return actual, period, monthly


async def collect_parameter(
    snap, parameter, begin, end, directory, month_directory, wire
):
    from garmin_database.adapters.inbound.desktop.chart import prepare_series

    key = parameter["key"]
    rows = list(snap.rows(parameter, begin, end))
    points, _ = Queries(snap.db).chart(parameter, begin, end, snap.conn)
    points, _ = prepare_series(points, parameter.get("enum"))
    details = read_export(directory, "details", key)
    history = read_export(directory, "history", key)
    saved = export_rows(details)
    daily = snap.daily(parameter, begin, end, publish_cache=False)
    mcp, checked_mcp = await mcp_audit(
        wire, key, begin, end, snap.revision, rows, daily
    )
    audit = dict(
        sql_rows=len(rows),
        export_details=difference(map(signature, rows), map(signature, saved)),
        chart=chart_audit(parameter, begin, end, rows, daily, points),
        export_history=history_audit(parameter, rows, daily, history),
        mcp=checked_mcp,
    )
    if key in MEAN_PARAMETERS:
        audit["raw_daily_summary"] = daily_audit(rows, key, daily)
    month_file = read_export(month_directory, "history", key)
    audit["export_month_history"] = monthly_export_audit(
        parameter, rows, daily, month_file, begin, end
    )
    data = dict(
        sql=rows, chart=points, mcp=mcp, export=saved, history=history, daily=daily
    )
    if key in MEAN_PARAMETERS and key in MCP_PARAMETERS:
        (
            data["mcp_period"],
            audit["mcp_period"],
            audit["mcp_monthly"],
        ) = await mean_statistics_audit(wire, key, begin, end, snap.revision, daily)
    return audit, data


async def collect(
    db, settings, private_settings, output, catalog, keys, begin, end, wire
):
    result = dict(start=begin.isoformat(), end=end.isoformat(), parameters={}, data={})
    with (
        DataAccess(db).snapshot() as snap,
        patch.object(Summaries, "publish", return_value=None),
    ):
        result["revision"] = snap.revision
        selected = [catalog[key] for key in sorted(keys) if key in catalog]
        exporter = Exporter(
            FixedReadings(snap),
            JSONExport(settings.data_dir),
            settings,
            SettingsStore(),
            private_settings,
        )
        exported = exporter.generate(
            output,
            selected,
            begin,
            end,
            recent_days=(end - begin).days + 1,
            summary_period="day",
        )
        result["export_directory"] = str(exported.directory)
        month_export = exporter.generate(
            output,
            selected,
            begin,
            end,
            recent_days=(end - begin).days + 1,
            summary_period="month",
        )
        result["export_month_directory"] = str(month_export.directory)
        for index, parameter in enumerate(selected, 1):
            audit, data = await collect_parameter(
                snap,
                parameter,
                begin,
                end,
                exported.directory,
                month_export.directory,
                wire,
            )
            result["parameters"][parameter["key"]] = audit
            result["data"][parameter["key"]] = data
            print(
                json.dumps(dict(phase="channels", checked=index, total=len(selected))),
                flush=True,
            )
    return result
