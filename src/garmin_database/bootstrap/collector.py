"""Collector composition; status and schedule commands never load Garmin or Qt."""

import os

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles


def session_store(config):
    if os.name == "nt":
        from garmin_database.adapters.outbound.security.dpapi_session import (
            SessionStore,
        )
    else:
        from garmin_database.adapters.outbound.security.linux_session import (
            SessionStore,
        )
    return SessionStore(config.session_path)


def synchronize(config, stop):
    from datetime import date

    from garmin_database.adapters.outbound.garmin.client import GarminSource
    from garmin_database.adapters.outbound.postgres.database import Database
    from garmin_database.bootstrap.dependencies import create_sync
    from garmin_database.domain.time import today

    store = session_store(config)
    with store.lock():
        sync = create_sync(
            Database(config.data_dir, config.database_dsn), GarminSource(store)
        )
        return sync.run_summary(date(2024, 1, 1), today(), stop)


def create_manager(config_path=None):
    from garmin_database.adapters.outbound.scheduler.manager import ScheduleManager

    return ScheduleManager(CollectorFiles(config_path))


def main(argv=None):
    from garmin_database.adapters.inbound.cli.stdio import configure_stdio
    from garmin_database.adapters.inbound.collector.commands import main as run

    configure_stdio()
    return run(
        argv,
        files_factory=CollectorFiles,
        manager_factory=create_manager,
        session_factory=session_store,
        synchronize=synchronize,
    )


if __name__ == "__main__":
    raise SystemExit(main())
