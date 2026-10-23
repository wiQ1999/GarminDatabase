"""Exercise the frozen GUI with a private synthetic PostgreSQL schema."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


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
                ],
                cwd=root,
                env=environment,
                timeout=30,
            )
            if result.returncode or not picture.is_file():
                print("Packaged application failed smoke test", file=sys.stderr)
                return 1
            print("Packaged PostgreSQL smoke test passed")
            return 0
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


if __name__ == "__main__":
    raise SystemExit(main())
