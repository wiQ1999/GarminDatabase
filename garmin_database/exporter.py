"""Stream JSON without loading an entire history into memory."""

import json
import os
import re
import tempfile
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from .fit import dumps
from .query import Queries
from .util import atomic_json, check_stop, dates


def parameter_filename(key):
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", key) and ".." not in key:
        return key + ".json"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key).strip(".")[:100] or "parameter"
    return safe + "-" + sha256(key.encode()).hexdigest()[:12] + ".json"


class Exporter:
    def __init__(self, db):
        self.db = db
        self.queries = Queries(db)

    def series(self, stream, param, start, end, stop, conn):
        meta = dict(
            schema_version=1,
            parameter=param["key"],
            unit=param["unit"],
            representation=param["representation"],
            **{"from": start.isoformat(), "to": end.isoformat()},
            columns=["time", "value", "source", "validity"],
            validity_labels={
                "v": "valid",
                "i": "invalid",
                "p": "partial_invalid",
                "e": "decode_error",
            },
            **self.queries.coverage(start, end, conn),
        )
        if param["enum"]:
            meta["value_labels"] = param["enum"]
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

    def generate(
        self,
        output,
        parameters,
        start,
        end,
        recent_days=90,
        stop=None,
        full_samples=False,
        progress=lambda *a: None,
    ):
        list(dates(start, end))
        if recent_days < 1:
            raise ValueError("Okres szczegółowy musi być dodatni")
        output = Path(output).resolve()
        output.mkdir(parents=True, exist_ok=True)
        if output == self.db.root.resolve() or output.is_relative_to(
            (self.db.root / "raw").resolve()
        ):
            raise ValueError("Eksport musi mieć osobny katalog")
        manifest = output / ".garmin-export.json"
        old = (
            json.loads(manifest.read_text(encoding="utf-8"))
            if manifest.exists()
            else {"files": []}
        )
        generated = []
        sizes = {}

        def write(name, writer):
            check_stop(stop)
            path = output / name
            # Never replace an unrelated file occupying an application filename.
            if path.exists() and name not in old.get("files", []):
                raise FileExistsError(
                    "Plik docelowy nie należy do poprzedniego eksportu"
                )
            fd, temp = tempfile.mkstemp(prefix=".export-", suffix=".tmp", dir=output)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                    writer(stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                check_stop(stop)
                os.replace(temp, path)
                generated.append(name)
                sizes[name] = path.stat().st_size
                # Track ownership after each completed file, including cancellation.
                atomic_json(
                    manifest,
                    {
                        "schema_version": 1,
                        "files": sorted(set(old.get("files", []) + generated)),
                    },
                )
            finally:
                Path(temp).unlink(missing_ok=True)

        with self.db.connect(readonly=True) as c:
            c.execute("BEGIN")  # consistent snapshot while import continues
            for index, param in enumerate(parameters, 1):
                progress(param["key"], "eksport", index, len(parameters))
                if param["representation"] == "source_summary" or full_samples:
                    write(
                        parameter_filename(param["key"]),
                        lambda s, p=param: self.series(s, p, start, end, stop, c),
                    )
            recent_start = max(start, end - timedelta(days=recent_days - 1))

            def recent(stream):
                missing = [
                    p["key"]
                    for p in parameters
                    if p["representation"] != "source_summary"
                ]
                stream.write(
                    '{"schema_version":1,"missing_source_summaries":'
                    + dumps(missing)
                    + ',"series":['
                )
                for index, param in enumerate(parameters):
                    if index:
                        stream.write(",")
                    self.series(stream, param, recent_start, end, stop, c)
                stream.write("]}")

            write("recent.json", recent)
        for name in old.get("files", []):
            # Only simple names recorded by this exporter can be cleaned up.
            if (
                name not in generated
                and Path(name).name == name
                and name.endswith(".json")
            ):
                (output / name).unlink(missing_ok=True)
        atomic_json(manifest, {"schema_version": 1, "files": generated})
        return sizes
