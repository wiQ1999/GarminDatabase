"""Compare complete synthetic imports with a Git baseline in isolated test schemas."""

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.support.fixtures import archive, fit_bytes  # noqa: E402


def baseline_importer(ref):
    revision = (
        subprocess.check_output(
            ["git", "rev-parse", "--verify", "--end-of-options", ref + "^{commit}"],
            cwd=ROOT,
        )
        .decode()
        .strip()
    )
    source = subprocess.check_output(
        [
            "git",
            "show",
            revision + ":src/garmin_database/adapters/outbound/postgres/imports.py",
        ],
        cwd=ROOT,
    )
    module = ModuleType("garmin_baseline_imports")
    exec(compile(source, "<trusted Git baseline>", "exec"), module.__dict__)
    return revision, module.Importer


@contextmanager
def isolated_database(dsn):
    schema = "garmin_bench_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        if admin.info.dbname == "garmin":
            raise ValueError("Wskaż osobną bazę testową")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            with tempfile.TemporaryDirectory(dir=ROOT / "test-results") as folder:
                db = Database(
                    folder, make_conninfo(dsn, options=f"-c search_path={schema}")
                )
                db.initialize()
                yield db
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def fingerprint(db):
    digest = hashlib.sha256()
    count = 0
    with (
        db.connect(readonly=True) as conn,
        conn.cursor(name="benchmark_fields") as cursor,
    ):
        cursor.itersize = 1000
        for row in cursor.execute("""SELECT ff.sha256,m.message_index,md.definition_index,fd.field_order,
            md.global_message_num,md.local_message_num,md.byte_order,md.byte_offset,
            fd.field_num,fd.namespace,fd.developer_data_index,fd.base_type_id,fd.size_bytes,
            c.stable_key,c.profile_metadata_json,m.byte_offset,m.byte_length,m.record_header,
            m.compressed_time_offset,m.time_unix_ms,m.time_basis,m.time_field_num,m.time_resolution_json,
            f.value_kind,f.integer_value,f.real_value,f.text_value,f.json_value,f.validity
            FROM fit_fields f JOIN fit_messages m ON m.id=f.message_id
            JOIN file_decodes d ON d.id=m.file_decode_id JOIN fit_files ff ON ff.id=d.fit_file_id
            JOIN field_definitions fd ON fd.id=f.field_definition_id
            JOIN message_definitions md ON md.id=m.message_definition_id
            JOIN field_catalog c ON c.id=f.resolved_catalog_id
            WHERE d.is_active=1 ORDER BY ff.sha256,m.message_index,fd.field_order"""):
            digest.update(
                json.dumps(list(row), separators=(",", ":"), allow_nan=False).encode()
            )
            count += 1
    return digest.hexdigest(), count


def measure(dsn, importer_type, payloads):
    with isolated_database(dsn) as db:
        paths = [
            archive(db.root, f"2024-06-{19 + i:02d}", payload)
            for i, payload in enumerate(payloads)
        ]
        importer = importer_type(db)
        begin = time.perf_counter()
        failures = sum(importer.archive(path) for path in paths)
        elapsed = time.perf_counter() - begin
        if failures:
            raise AssertionError("Import syntetyczny zakończył się błędami")
        signature, count = fingerprint(db)
        return elapsed, signature, count


def compare(dsn, baseline, messages, repeats):
    payloads = [
        fit_bytes(
            values=[
                (1100000000 + day * 86400 + i, 60 + i % 30, (43776 + i) % 65536, i)
                for i in range(messages)
            ]
        )
        for day in range(2)
    ]
    runs = {"baseline": [], "current": []}
    signatures = set()
    for repeat in range(repeats):
        order = ("baseline", "current") if repeat % 2 == 0 else ("current", "baseline")
        for mode in order:
            elapsed, signature, count = measure(
                dsn, baseline if mode == "baseline" else Importer, payloads
            )
            if count != messages * 8:
                raise AssertionError("Nieprawidłowa liczba pól")
            signatures.add(signature)
            runs[mode].append(elapsed)
            print(
                f"{messages} messages/day, {mode}, run {repeat + 1}: {elapsed:.3f}s",
                flush=True,
            )
    if len(signatures) != 1:
        raise AssertionError("Zmiana wartości lub metadanych fizycznych FIT")
    medians = {mode: statistics.median(values) for mode, values in runs.items()}
    return dict(
        days=2,
        messages_per_day=messages,
        fields=messages * 8,
        runs=runs,
        medians=medians,
        speedup=medians["baseline"] / medians["current"],
        identical_physical_data=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--messages", type=int, nargs="+", default=[3000, 12000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--min-speedup", type=float, default=2.0)
    args = parser.parse_args()
    if args.repeats < 3 or any(n < 1 for n in args.messages):
        parser.error("Wymagane co najmniej trzy powtórzenia i dodatnie rozmiary")
    dsn = os.environ.get("GARMIN_TEST_DATABASE_DSN")
    if not dsn:
        parser.error("Ustaw GARMIN_TEST_DATABASE_DSN na osobną bazę testową")
    (ROOT / "test-results").mkdir(exist_ok=True)
    revision, baseline = baseline_importer(args.baseline_ref)
    results = [compare(dsn, baseline, count, args.repeats) for count in args.messages]
    report = dict(
        baseline_revision=revision,
        python=sys.version.split()[0],
        minimum_speedup=args.min_speedup,
        datasets=results,
    )
    path = ROOT / "test-results/import-benchmark.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all(r["speedup"] >= args.min_speedup for r in results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("Benchmark failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
