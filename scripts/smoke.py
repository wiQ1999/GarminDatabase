"""Exercise the frozen GUI with a private synthetic PostgreSQL schema."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.support.fixtures import archive, fit_bytes  # noqa: E402


def main():
    dsn = os.environ.get("GARMIN_TEST_DATABASE_DSN")
    if not dsn:
        print(
            "Ustaw GARMIN_TEST_DATABASE_DSN na osobną bazę PostgreSQL do testów.",
            file=sys.stderr,
        )
        return 1
    root = Path(__file__).resolve().parents[1]
    executable = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else root
        / "dist/GarminDatabase"
        / ("GarminDatabase.exe" if os.name == "nt" else "GarminDatabase")
    )
    result_dir = root / "test-results" / ("packaged-smoke-" + uuid4().hex)
    result_dir.mkdir(parents=True)
    picture = result_dir / "start.png"
    for day_index, day in enumerate(("2024-06-19", "2024-06-20")):
        payload = fit_bytes(
            values=[
                (
                    1100000000 + day_index * 86400 + i,
                    60 + i % 30,
                    (43776 + i) % 65536,
                    i,
                )
                for i in range(600)
            ]
        )
        archive(result_dir / "data", day, payload)
    schema = "garmin_smoke_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            environment = dict(
                os.environ,
                QT_QPA_PLATFORM="offscreen",
                GARMIN_DATABASE_DSN=make_conninfo(
                    dsn, options=f"-c search_path={schema}"
                ),
            )
            result = subprocess.run(
                [
                    str(executable),
                    "--data-dir",
                    str(result_dir / "data"),
                    "--settings-file",
                    str(result_dir / "settings.json"),
                    "--smoke-screenshot",
                    str(picture),
                    "--smoke-import-from",
                    "2024-06-19",
                    "--smoke-import-to",
                    "2024-06-20",
                ],
                cwd=root,
                env=environment,
                timeout=30,
            )
            readiness = picture.with_suffix(".ui.json")
            if (
                result.returncode
                or not picture.is_file()
                or not readiness.is_file()
                or picture.with_suffix(".error.json").exists()
                or json.loads(readiness.read_text(encoding="utf-8"))
                != {"overview_ready": True, "background_idle": True}
            ):
                print("Packaged application failed smoke test", file=sys.stderr)
                return 1
            with psycopg.connect(environment["GARMIN_DATABASE_DSN"]) as check:
                counts = check.execute("""SELECT count(*),sum(message_count),sum(stored_field_count)
                    FROM file_decodes WHERE is_active=1 AND status='complete'""").fetchone()
                if (
                    counts != (2, 1200, 4800)
                    or check.execute("SELECT count(*) FROM decode_runs").fetchone()[0]
                    != 2
                ):
                    print("Packaged import/resume verification failed", file=sys.stderr)
                    return 1
            print("Packaged PostgreSQL smoke test passed")
            return 0
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


if __name__ == "__main__":
    raise SystemExit(main())
