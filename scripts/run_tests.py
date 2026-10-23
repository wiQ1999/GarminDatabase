"""Portable test runner. Requires a separate disposable PostgreSQL database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def main():
    if not os.environ.get("GARMIN_TEST_DATABASE_DSN"):
        print(
            "Ustaw GARMIN_TEST_DATABASE_DSN na osobną bazę PostgreSQL do testów.",
            file=sys.stderr,
        )
        return 1
    root = Path(__file__).resolve().parents[1]
    results = root / "test-results"
    results.mkdir(exist_ok=True)
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "pytest",
            "--basetemp",
            str(results / ("tmp-" + uuid4().hex)),
            "--cov",
            "--cov-branch",
            "--cov-fail-under=85",
            "--cov-report=term-missing",
            "--cov-report=html:test-results/coverage",
            "--junitxml=test-results/results.xml",
            *sys.argv[1:],
        ],
        cwd=root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
