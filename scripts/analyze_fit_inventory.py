"""Stream FITs from ZIPs; retain schema/count metadata, never measurement payloads.

Source rules: docs/02-source-validation.md. Local reports are not product docs.
"""

import argparse
import importlib.metadata
import json
import time
import warnings
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import fitdecode
from garmin_fit_sdk import Decoder, Profile, Stream

from garmin_database.adapters.outbound.filesystem.files import atomic_json

ROOT = Path(__file__).resolve().parents[1]


def enrich_public_profile(report):
    for row in report["fields"]:
        enrich_field(row)
    stored = [row for row in report["fields"] if not row["expanded"]]
    named = sum(
        row["count"] for row in stored if row["parser_named"] or row["sdk_name"]
    )
    report["summary"]["public_profile_named_occurrence_percent"] = (
        round(100 * named / report["summary"]["stored_field_occurrences"], 2)
        if report["summary"]["stored_field_occurrences"]
        else 0
    )
    report["summary"]["public_profile_unknown_stored_variants"] = sum(
        not row["parser_named"] and not row["sdk_name"] for row in stored
    )
    return report


def decode_inventory(payload):
    messages = Counter()
    fields = {}
    times = []
    versions = []
    with warnings.catch_warnings(record=True) as notices:
        with fitdecode.FitReader(
            payload,
            keep_raw_chunks=True,
            check_crc=fitdecode.CrcCheck.RAISE,
            error_handling=fitdecode.ErrorHandling.RAISE,
        ) as reader:
            for frame in reader:
                if isinstance(frame, fitdecode.FitHeader):
                    versions.append(int.from_bytes(frame.chunk.bytes[2:4], "little"))
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                number = frame.global_mesg_num
                messages[number] += 1
                for field in frame.fields:
                    record_field(fields, frame, field)
                    if has_known_time(field):
                        times.append(field.value.isoformat())
    for row in fields.values():
        for key in ("base_types", "byte_sizes", "array_lengths", "value_types"):
            row[key] = sorted(row[key])
    return {
        "messages": dict(messages),
        "fields": list(fields.values()),
        "min_time": min(times) if times else None,
        "max_time": max(times) if times else None,
        "profile_versions": versions,
        "warnings": len(notices),
    }


def sdk_check(payload):
    seen = Counter()

    def listener(number, message):
        seen[number] += 1

    _, errors = Decoder(Stream.from_byte_array(bytearray(payload))).read(
        apply_scale_and_offset=False,
        convert_datetimes_to_dates=False,
        convert_types_to_strings=False,
        expand_sub_fields=False,
        expand_components=False,
        merge_heart_rates=False,
        mesg_listener=listener,
    )
    return {
        "messages": dict(seen),
        "errors": [type(error).__name__ for error in errors],
    }


class InventoryScan:
    def __init__(self, cache):
        self.cache = cache
        self.active_hashes = set()
        self.catalog = {}
        self.totals = Counter(
            dict.fromkeys(
                (
                    "archive_bytes",
                    "file_occurrences",
                    "uncompressed_bytes",
                    "decoded_file_occurrences",
                    "warning_occurrences",
                ),
                0,
            )
        )
        self.message_counts = Counter()
        self.categories = Counter()
        self.errors = []
        self.sdk_checks = []
        self.signatures = set()
        self.min_time = self.max_time = None
        self.profile_versions = Counter()
        self.archive_dates = []

    def scan_archive(self, path):
        self.archive_dates.append(path.stem)
        self.totals["archive_bytes"] += path.stat().st_size
        with ZipFile(path) as archive:
            for entry in archive.infolist():
                if not entry.is_dir():
                    self.scan_file(path, archive, entry)

    def scan_file(self, path, archive, entry):
        payload = archive.read(entry)
        digest = sha256(payload).hexdigest()
        self.active_hashes.add(digest)
        category = Path(entry.filename).stem.partition("_")[2]
        self.totals["file_occurrences"] += 1
        self.totals["uncompressed_bytes"] += len(payload)
        self.categories[category] += 1
        if digest not in self.cache:
            try:
                self.cache[digest] = decode_inventory(payload)
            except Exception as error:
                self.cache[digest] = {"error": type(error).__name__}
        result = self.cache[digest]
        if "error" in result:
            self.errors.append(
                {
                    "archive": path.name,
                    "entry": entry.filename,
                    "error": result["error"],
                }
            )
            return
        self.merge_file_summary(result)
        signature = tuple(
            sorted(
                (
                    (f["message_num"], f["field_num"], f["name"], f["expanded"])
                    for f in result["fields"]
                )
            )
        )
        if signature not in self.signatures:
            self.signatures.add(signature)
            checked = sdk_check(payload)
            self.sdk_checks.append(
                {
                    "archive": path.name,
                    "category": category,
                    "counts_match": checked["messages"] == result["messages"],
                    "errors": checked["errors"],
                }
            )
        for field in result["fields"]:
            self.merge_field(field, path, category)

    def merge_field(self, field, path, category):
        key = (
            field["message_num"],
            field["field_num"],
            field["developer_index"],
            field["name"],
            field["expanded"],
        )
        if key not in self.catalog:
            self.catalog[key] = dict(field)
            self.catalog[key].update(
                {
                    "count": 0,
                    "null_count": 0,
                    "categories": set(),
                    "first_archive": path.stem,
                    "last_archive": path.stem,
                }
            )
            for name in ("base_types", "byte_sizes", "array_lengths", "value_types"):
                self.catalog[key][name] = set()
        row = self.catalog[key]
        row["count"] += field["count"]
        row["null_count"] += field["null_count"]
        row["categories"].add(category)
        row["last_archive"] = path.stem
        for name in ("base_types", "byte_sizes", "array_lengths", "value_types"):
            row[name].update(field[name])
        for name in ("contains_null_array", "outside_signed_int64"):
            row[name] |= field[name]

    def report(self, archive_files, manifest, start, parser_versions):
        rows = self.catalog_rows()
        fields = field_statistics(rows)
        unresolved = sorted(
            (
                day
                for day, row in manifest["days"].items()
                if row["status"] == "not_found_unverified"
            )
        )
        self.totals["unique_files_decoded"] = sum(
            ("error" not in self.cache[digest] for digest in self.active_hashes)
        )
        summary = {
            "archives": len(archive_files),
            **dict(self.totals),
            "unique_file_hashes": len(self.active_hashes),
            "categories": dict(self.categories),
            "message_types": len(self.message_counts),
            "messages": sum(self.message_counts.values()),
            **fields,
            **archive_period(self.archive_dates),
            "min_known_utc_time": self.min_time,
            "max_known_utc_time": self.max_time,
            "unresolved_days": len(unresolved),
            "fit_decode_errors": len(self.errors),
            "sdk_signature_checks": len(self.sdk_checks),
            "sdk_checks_with_errors": sum(
                (bool(check["errors"]) for check in self.sdk_checks)
            ),
            "sdk_message_count_mismatches": sum(
                (not check["counts_match"] for check in self.sdk_checks)
            ),
            "elapsed_seconds": round(time.monotonic() - start, 1),
        }
        report = {
            "summary": summary,
            "parser_versions": parser_versions,
            "profile_versions": dict(self.profile_versions),
            "message_counts": dict(sorted(self.message_counts.items())),
            "fields": rows,
            "errors": self.errors,
            "sdk_checks": self.sdk_checks,
            "unresolved_dates": unresolved,
        }
        return report

    def merge_file_summary(self, result):
        self.totals["decoded_file_occurrences"] += 1
        self.totals["warning_occurrences"] += result["warnings"]
        self.profile_versions.update(
            (
                ".".join(map(str, version))
                if isinstance(version, (tuple, list))
                else str(version)
                for version in result["profile_versions"]
            )
        )
        self.message_counts.update(result["messages"])
        if result["min_time"]:
            self.min_time = (
                min(self.min_time, result["min_time"])
                if self.min_time
                else result["min_time"]
            )
            self.max_time = (
                max(self.max_time, result["max_time"])
                if self.max_time
                else result["max_time"]
            )

    def catalog_rows(self):
        rows = []
        for original in self.catalog.values():
            row = dict(original)
            for key in (
                "categories",
                "base_types",
                "byte_sizes",
                "array_lengths",
                "value_types",
            ):
                row[key] = sorted(row[key])
            rows.append(row)
        return sorted(
            rows, key=lambda row: (row["message_num"], row["field_num"], row["name"])
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--limit", type=int, help="Only first N archives, for a smoke test"
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("Limit must be positive")
    start = time.monotonic()
    checkpoint = args.data_dir / "fit_inventory_checkpoint.json"
    versions = {
        name: importlib.metadata.version(name)
        for name in ("fitdecode", "garmin-fit-sdk")
    }
    scan = InventoryScan(load_checkpoint(checkpoint, versions))
    paths = sorted((args.data_dir / "raw").glob("*.zip"))
    if args.limit is not None:
        paths = paths[: args.limit]
    for index, path in enumerate(paths, 1):
        scan.scan_archive(path)
        if index % 50 == 0:
            atomic_json(checkpoint, {"parser_versions": versions, "cache": scan.cache})
            print(
                f"{index}/{len(paths)} archives; {len(scan.catalog)} field variants",
                flush=True,
            )
    manifest_path = args.data_dir / "collection.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {"days": {}}
    )
    report = enrich_public_profile(scan.report(paths, manifest, start, versions))
    output = args.data_dir / "fit_inventory.json"
    atomic_json(output, report)
    checkpoint.unlink(missing_ok=True)
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {output}")


def load_checkpoint(path, versions):
    cached = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cache = cached.get("cache", {}) if cached.get("parser_versions") == versions else {}
    for result in cache.values():
        if "messages" in result:
            result["messages"] = {
                int(key): count for key, count in result["messages"].items()
            }
    return cache


def enrich_field(row):
    message = Profile["messages"].get(row["message_num"], {})
    modern = message.get("fields", {}).get(row["field_num"], {})
    if row["developer_index"] is not None:
        modern = {}
    variant = next(
        (
            field
            for field in modern.get("sub_fields", [])
            if field["name"] == row["name"]
        ),
        modern,
    )
    row.update(
        {
            "sdk_message_name": message.get("name"),
            "sdk_units": variant.get("units"),
            "sdk_scale": variant.get("scale"),
            "sdk_offset": variant.get("offset"),
        }
    )


def record_field(fields, frame, field):
    number = frame.global_mesg_num
    developer = getattr(field.field_def, "dev_data_index", None)
    key = (
        number,
        field.def_num,
        developer,
        field.name,
        field.is_expanded,
    )
    modern = Profile["messages"].get(number, {}).get("fields", {}).get(field.def_num)
    row = fields.setdefault(
        key,
        {
            "message_num": number,
            "message_name": frame.name,
            "field_num": field.def_num,
            "developer_index": developer,
            "name": field.name,
            "expanded": field.is_expanded,
            "parser_named": field.field is not None,
            "sdk_name": modern.get("name") if modern and developer is None else None,
            "units": field.units,
            "scale": getattr(field.field, "scale", None),
            "offset": getattr(field.field, "offset", None),
            "base_types": set(),
            "byte_sizes": set(),
            "array_lengths": set(),
            "value_types": set(),
            "count": 0,
            "null_count": 0,
            "contains_null_array": False,
            "outside_signed_int64": False,
        },
    )
    row["count"] += 1
    raw = field.raw_value
    row["null_count"] += raw is None
    row["base_types"].add(field.base_type.name)
    if field.field_def:
        row["byte_sizes"].add(field.field_def.size)
    row["value_types"].add(type(raw).__name__)
    if isinstance(raw, (tuple, list)):
        row["array_lengths"].add(len(raw))
        row["contains_null_array"] |= any(value is None for value in raw)
        values = raw
    else:
        values = (raw,)
    row["outside_signed_int64"] |= any(
        isinstance(value, int) and not -(2**63) <= value < 2**63 for value in values
    )


def field_statistics(rows):
    stored = [field for field in rows if not field["expanded"]]
    observed = sum((field["count"] for field in stored))
    named = sum((field["count"] for field in stored if field["parser_named"]))
    return {
        "field_variants": len(rows),
        "stored_field_variants": len(stored),
        "expanded_field_variants": len(rows) - len(stored),
        "stored_field_occurrences": observed,
        "named_field_occurrences": named,
        "named_occurrence_percent": round(100 * named / observed, 2) if observed else 0,
        "unknown_stored_field_variants": sum(
            (not field["parser_named"] for field in stored)
        ),
        "sdk_only_named_variants": sum(
            (not field["parser_named"] and bool(field["sdk_name"]) for field in stored)
        ),
    }


def archive_period(archive_dates):
    consecutive_start = archive_dates[-1] if archive_dates else None
    from datetime import date, timedelta

    if consecutive_start:
        available = set(archive_dates)
        current = date.fromisoformat(consecutive_start)
        while (current - timedelta(days=1)).isoformat() in available:
            current -= timedelta(days=1)
        consecutive_start = current.isoformat()
    return {
        "first_archive": archive_dates[0] if archive_dates else None,
        "last_archive": archive_dates[-1] if archive_dates else None,
        "continuous_archive_history_from": consecutive_start,
    }


def has_known_time(field):
    return isinstance(field.value, datetime) and field.name in {
        "timestamp",
        "time_created",
        "stress_level_time",
        "start_time",
        "end_time",
    }


if __name__ == "__main__":
    main()
