"""Exercise the frozen collector offline, without a GUI or private resources."""

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from garmin_database.application.collector_models import CollectorConfig


def main():
    root = Path(__file__).resolve().parents[1]
    (root / "work").mkdir(exist_ok=True)
    binary = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else root
        / "dist/GarminDatabaseCollector"
        / (
            "GarminDatabaseCollector.exe"
            if os.name == "nt"
            else "GarminDatabaseCollector"
        )
    )
    with TemporaryDirectory(prefix="collector-smoke-", dir=root / "work") as directory:
        base = Path(directory)
        config = CollectorConfig(
            str(base / "data"), str(base / "state"), str(base / "auth/session.bin")
        )
        path = base / "collector.json"
        path.write_text(json.dumps(asdict(config)), encoding="utf-8")
        for arguments in (
            ["--help"],
            ["--config", str(path), "status", "--json"],
            ["--config", str(path), "run", "--scheduled"],
        ):
            result = subprocess.run(
                [str(binary), *arguments], capture_output=True, text=True, timeout=30
            )
            if result.returncode:
                print(
                    "Collector smoke failed:",
                    arguments[-1],
                    "exit code",
                    result.returncode,
                )
                # Only synthetic offline configuration is used by this smoke.
                print(result.stdout[-4000:])
                print(result.stderr[-4000:])
                return 1
        assert not (base / "data").exists() and not (base / "state").exists()
    print("Collector smoke OK: offline status, disabled run, no data writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
