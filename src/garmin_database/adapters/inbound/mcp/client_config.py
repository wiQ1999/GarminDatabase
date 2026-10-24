"""Client configuration without loading the protocol SDK or Qt."""

import os
import sys
from pathlib import Path


def application_dir():
    return (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
        / "GarminDatabase"
    )


def client_config(settings_path=None):
    settings_path = str(
        Path(settings_path or application_dir() / "settings.json").resolve()
    )
    if getattr(sys, "frozen", False):
        command = Path(sys.executable).parent.parent / (
            "GarminDatabaseMCP/GarminDatabaseMCP"
            + (".exe" if Path(sys.executable).suffix.lower() == ".exe" else "")
        )
        args = []
    else:
        command = sys.executable
        args = [str(Path(__file__).resolve().parents[3] / "bootstrap/mcp.py")]
    return {
        "mcpServers": {
            "garmin_database": {
                "command": str(command),
                "args": [*args, "--settings-file", settings_path],
            }
        }
    }
