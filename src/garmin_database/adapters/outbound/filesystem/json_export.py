"""Eksport podsumowań i szczegółów: docs/05-export.md."""

import os
import re
import tempfile
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from garmin_database.adapters.outbound.filesystem.files import atomic_json
from garmin_database.application.dto import ExportResult
from garmin_database.application.read_models import aggregation, summary_columns
from garmin_database.domain.aggregation import monthly_summaries, summary_method
from garmin_database.domain.cancellation import Cancelled, check_stop
from garmin_database.domain.values import dumps


def parameter_filename(key):
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", key) and ".." not in key:
        return key + ".json"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key).strip(".")[:100] or "parameter"
    return safe + "-" + sha256(key.encode()).hexdigest()[:12] + ".json"


def export_directory(parent, now=None):
    now = now or datetime.now(ZoneInfo("Europe/Warsaw"))
    base = "GarminDatabase_" + now.strftime("%Y-%m-%d_%H-%M-%S_%f")
    index = 0
    while True:
        candidate = parent / (base + (f"_{index:02d}" if index else ""))
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            index += 1


class JSONExport:
    def __init__(self, data_root):
        self.data_root = Path(data_root)

    def metadata(self, param, start, end, snapshot, kind):
        meta = dict(
            schema_version=2,
            parameter=param["key"],
            unit=param["unit"],
            representation=param["representation"],
            kind=kind,
            **{"from": start.isoformat(), "to": end.isoformat()},
            timezone="Europe/Warsaw",
            calendar_timezone="Europe/Warsaw",
            timestamp_timezone="UTC",
            **snapshot.coverage(start, end),
        )
        if param["enum"]:
            meta["value_labels"] = param["enum"]
        return meta

    def series(self, stream, param, start, end, stop, snapshot, kind):
        meta = self.metadata(param, start, end, snapshot, kind)
        meta.update(
            columns=["time", "value", "source", "validity"],
            validity_labels={
                "v": "valid",
                "i": "invalid",
                "p": "partial_invalid",
                "e": "decode_error",
            },
            summary_origin="garmin"
            if param["representation"] == "source_summary"
            else None,
        )
        stream.write(dumps(meta)[:-1] + ',"data":[')
        first = True
        sources = {}
        source_ids = {}
        for row in snapshot.rows(param, start, end):
            check_stop(stop)
            if not first:
                stream.write(",")
            first = False
            source = row["source"]
            if source not in source_ids:
                key = "s" + str(len(sources) + 1)
                source_ids[source] = key
                sources[key] = {"path": source, "requested_day": row["requested_day"]}
            stream.write(
                dumps(
                    [
                        row["time"],
                        row["value"],
                        source_ids[source],
                        {
                            "valid": "v",
                            "invalid": "i",
                            "partial_invalid": "p",
                            "decode_error": "e",
                        }[row["validity"]],
                    ]
                )
            )
        stream.write('],"sources":' + dumps(sources) + "}")

    def history(self, stream, param, start, end, stop, snapshot, period):
        method = summary_method(param)
        if method == "garmin":
            self.series(stream, param, start, end, stop, snapshot, "history")
            return
        daily = snapshot.daily(param, start, end, stop, publish_cache=True)
        rows = monthly_summaries(daily, start, end) if period == "month" else daily
        columns = summary_columns(param, period)
        meta = self.metadata(param, start, end, snapshot, "history")
        meta.update(
            representation="computed_summary",
            source_representation=param["representation"],
            summary_origin="application",
            aggregation=aggregation(param, period),
            columns=columns,
            data_revision=snapshot.revision,
        )
        stream.write(dumps(meta)[:-1] + ',"data":[')
        for index, row in enumerate(rows):
            check_stop(stop)
            if index:
                stream.write(",")
            stream.write(
                dumps(
                    [
                        row["day"] if column == "month" else row[column]
                        for column in columns
                    ]
                )
            )
        stream.write("]}")

    def generate(
        self,
        output,
        parameters,
        start,
        end,
        recent_days,
        stop,
        summary_period,
        progress,
        snapshot,
    ):
        parent = Path(output).resolve()
        if parent == self.data_root.resolve() or parent.is_relative_to(
            (self.data_root / "raw").resolve()
        ):
            raise ValueError("Eksport musi mieć osobny katalog")
        check_stop(stop)
        parent.mkdir(parents=True, exist_ok=True)
        directory = export_directory(parent)
        sizes = {}
        manifest = dict(
            schema_version=2,
            created_at=datetime.now(ZoneInfo("Europe/Warsaw")).isoformat(),
            status="running",
            history_from=start.isoformat(),
            history_to=end.isoformat(),
            summary_period=summary_period,
            recent_days=recent_days,
            files=sizes,
        )
        atomic_json(directory / "manifest.json", manifest)

        def write(name, writer):
            check_stop(stop)
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(
                prefix=".export-", suffix=".tmp", dir=path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                    writer(stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                check_stop(stop)
                os.replace(temp, path)
                sizes[name] = path.stat().st_size
                atomic_json(directory / "manifest.json", manifest)
            finally:
                Path(temp).unlink(missing_ok=True)

        try:
            recent_start = max(start, end - timedelta(days=recent_days - 1))
            for index, param in enumerate(parameters, 1):
                progress(
                    param["key"], "podsumowania", 2 * index - 1, 2 * len(parameters)
                )
                write(
                    "history/" + parameter_filename(param["key"]),
                    lambda s, p=param: self.history(
                        s, p, start, end, stop, snapshot, summary_period
                    ),
                )
                progress(param["key"], "szczegóły", 2 * index, 2 * len(parameters))
                write(
                    "details/" + parameter_filename(param["key"]),
                    lambda s, p=param: self.series(
                        s, p, recent_start, end, stop, snapshot, "details"
                    ),
                )
        except BaseException as error:
            manifest["status"] = (
                "cancelled"
                if isinstance(error, (Cancelled, KeyboardInterrupt))
                else "failed"
            )
            atomic_json(directory / "manifest.json", manifest)
            raise
        manifest["status"] = "complete"
        atomic_json(directory / "manifest.json", manifest)
        return ExportResult(directory, sizes)
