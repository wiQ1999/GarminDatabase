"""Read-only composition root; does not load Qt, Garmin or import/migration services."""

import argparse
import logging

import anyio

from garmin_database.adapters.outbound.filesystem.settings_json import SettingsStore
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.readings import DataAccess
from garmin_database.application.use_cases.read_health import MCPData


def create_service(settings_path=None, **limits):
    return MCPData(
        settings_path,
        settings_store=SettingsStore(),
        readings_factory=lambda settings: DataAccess(
            Database(settings.data_dir, settings.database_dsn)
        ),
        **limits,
    )


def main(argv=None):
    from garmin_database.adapters.inbound.mcp.server import serve

    parser = argparse.ArgumentParser(
        description="GarminDatabase — MCP stdio tylko do odczytu"
    )
    parser.add_argument("--settings-file")
    args = parser.parse_args(argv)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    anyio.run(serve, create_service(args.settings_file))


if __name__ == "__main__":
    main()
