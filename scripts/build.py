"""Build an onedir desktop distribution on the current operating system."""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default="dist")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "GarminDatabase",
        "--distpath",
        str(Path(args.destination).resolve()),
        "--specpath",
        str(root / "build"),
        "--collect-all",
        "psycopg_binary",
        "--hidden-import",
        "psycopg_binary",
        "--collect-data",
        "garmin_database",
        "--collect-data",
        "garmin_fit_sdk",
        "--collect-data",
        "fitdecode",
        "--collect-data",
        "tzdata",
        "--copy-metadata",
        "garminconnect",
        "--copy-metadata",
        "fitdecode",
        "--copy-metadata",
        "garmin-fit-sdk",
        "--add-data",
        str(root / "garmin_database/resources") + ":garmin_database/resources",
        str(root / "desktop.py"),
    ]
    result = subprocess.call(command, cwd=root)
    if result:
        return result
    if sys.platform == "win32":
        internal = Path(args.destination).resolve() / "GarminDatabase/_internal"
        for library in ("icuuc.dll", "icudt78.dll"):
            (internal / library).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
