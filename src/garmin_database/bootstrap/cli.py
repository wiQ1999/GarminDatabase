"""CLI composition root; no Qt."""

from garmin_database.adapters.inbound.cli.commands import main as run
from garmin_database.adapters.outbound.filesystem.settings_json import SettingsStore
from garmin_database.bootstrap.dependencies import Services


def main(argv=None):
    from garmin_database.adapters.inbound.cli.stdio import configure_stdio

    configure_stdio()
    return run(argv, settings_store=SettingsStore(), services_factory=Services)


if __name__ == "__main__":
    raise SystemExit(main())
