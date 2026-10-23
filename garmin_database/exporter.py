"""Eksport podsumowań i szczegółów: docs/05-export.md."""

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from .fit import dumps
from .query import Queries
from .summaries import ALGORITHM_VERSION, Summaries, monthly_summaries, summary_method
from .util import Cancelled, atomic_json, check_stop, dates


def parameter_filename(key):
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", key) and ".." not in key:
        return key + ".json"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key).strip(".")[:100] or "parameter"
    return safe + "-" + sha256(key.encode()).hexdigest()[:12] + ".json"


@dataclass
class ExportResult:
    directory: Path
    files: dict[str, int]


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


class Exporter:
    def __init__(self, db):
        self.db = db
        self.queries = Queries(db)

    def metadata(self, param, start, end, conn, kind):
        meta = dict(
            schema_version=2,
            parameter=param["key"],
            unit=param["unit"],
            representation=param["representation"],
            kind=kind,
            **{"from": start.isoformat(), "to": end.isoformat()},
            timezone="Europe/Warsaw",
            **self.queries.coverage(start, end, conn),
        )
        if param["enum"]:
            meta["value_labels"] = param["enum"]
        return meta

    def series(self, stream, param, start, end, stop, conn, kind):
        meta = self.metadata(param, start, end, conn, kind)
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
        for row in self.queries.rows(param, start, end, conn):
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

    def history(self, stream, param, start, end, stop, conn, period):
        method = summary_method(param)
        if method == "garmin":
            self.series(stream, param, start, end, stop, conn, "history")
            return
        daily = Summaries(self.db).daily(param, start, end, conn, stop)
        rows = monthly_summaries(daily, start, end) if period == "month" else daily
        columns = ["day"]
        if method == "sample_mean":
            columns += ["mean", "minimum", "maximum"]
        elif method == "value_counts":
            columns += ["value_counts"]
        else:
            columns += ["last_value"]
        columns += [
            "valid_count",
            "invalid_count",
            "excluded_count",
            "untimed_count",
            "first_time",
            "last_time",
            "day_basis",
        ]
        if period == "month":
            columns[0] = "month"
            columns += ["valid_days", "period_from", "period_to"]
        meta = self.metadata(param, start, end, conn, "history")
        meta.update(
            representation="computed_summary",
            source_representation=param["representation"],
            summary_origin="application",
            aggregation=dict(
                method=method,
                period=period,
                algorithm_version=ALGORITHM_VERSION,
                weighting="valid_sample_count" if method == "sample_mean" else None,
                negative_stress_values_excluded=param["key"]
                == "stress_level.stress_level_value",
            ),
            columns=columns,
            data_revision=conn.execute(
                "SELECT revision FROM dataset_state WHERE id=1"
            ).fetchone()[0],
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
        recent_days=90,
        stop=None,
        summary_period="day",
        progress=lambda *a: None,
    ):
        list(dates(start, end))
        if recent_days < 1 or summary_period not in {"day", "month"}:
            raise ValueError("Nieprawidłowy okres szczegółów lub podsumowań")
        if not parameters or len({p["key"] for p in parameters}) != len(parameters):
            raise ValueError("Wybierz niepowtarzające się parametry")
        parent = Path(output).resolve()
        if parent == self.db.root.resolve() or parent.is_relative_to(
            (self.db.root / "raw").resolve()
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
            with self.db.connect(readonly=True) as conn:
                conn.execute("SELECT revision FROM dataset_state").fetchone()
                recent_start = max(start, end - timedelta(days=recent_days - 1))
                for index, param in enumerate(parameters, 1):
                    progress(
                        param["key"], "podsumowania", 2 * index - 1, 2 * len(parameters)
                    )
                    write(
                        "history/" + parameter_filename(param["key"]),
                        lambda s, p=param: self.history(
                            s, p, start, end, stop, conn, summary_period
                        ),
                    )
                    progress(param["key"], "szczegóły", 2 * index, 2 * len(parameters))
                    write(
                        "details/" + parameter_filename(param["key"]),
                        lambda s, p=param: self.series(
                            s, p, recent_start, end, stop, conn, "details"
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
