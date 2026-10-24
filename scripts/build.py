"""Build an onedir desktop distribution on the current operating system."""

import argparse
import ssl
import subprocess
import sys
from pathlib import Path


def ssl_runtime_arguments():
    """Bundle the adjacent PEM required by the managed Python SSL module.

    Standard Python has no such file. Preserve the runtime's certificate policy
    when it is present; never bypass the SSLContext constructor or verification.
    See docs/12-running-and-testing.md.
    """
    resource = Path(ssl.__file__).with_name("codex-rejected-cas.pem")
    return ["--add-data", str(resource) + ":."] if resource.is_file() else []


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
        "--icon",
        str(root / "garmin_database/resources/app-icon.ico"),
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
        *ssl_runtime_arguments(),
        str(root / "desktop.py"),
    ]
    result = subprocess.call(command, cwd=root)
    if result:
        return result
    if sys.platform == "win32":
        internal = Path(args.destination).resolve() / "GarminDatabase/_internal"
        for library in ("icuuc.dll", "icudt78.dll"):
            (internal / library).unlink(missing_ok=True)
    mcp_command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--console",
        "--name",
        "GarminDatabaseMCP",
        "--icon",
        str(root / "garmin_database/resources/app-icon.ico"),
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
        "tzdata",
        "--copy-metadata",
        "mcp",
        "--copy-metadata",
        "anyio",
        "--hidden-import",
        "anyio._backends._asyncio",
        "--exclude-module",
        "PySide6",
        "--exclude-module",
        "garminconnect",
        *ssl_runtime_arguments(),
        str(root / "mcp_stdio.py"),
    ]
    return subprocess.call(mcp_command, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
