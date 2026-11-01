"""Collector composition; status and schedule commands never load Garmin or Qt."""

import os
import sys
from pathlib import Path

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

    config = CollectorFiles().resolve_settings(config)
    store = session_store(config)
    with store.lock():
        sync = create_sync(
            Database(config.data_dir, config.database_dsn), GarminSource(store)
        )
        return sync.run_summary(date.fromisoformat(config.download_from), today(), stop)


def collector_command(*, windowless=False):
    if getattr(sys, "frozen", False):
        binary = Path(sys.executable)
        if binary.stem != "GarminDatabaseCollector":
            binary = (
                binary.parent.parent
                / "GarminDatabaseCollector"
                / (
                    "GarminDatabaseCollector.exe"
                    if os.name == "nt"
                    else "GarminDatabaseCollector"
                )
            )
        if windowless and os.name == "nt":
            binary = binary.with_name("GarminDatabaseCollectorTask.exe")
        return [str(binary)]
    interpreter = os.path.abspath(sys.executable)
    if windowless and os.name == "nt":
        interpreter = str(Path(interpreter).with_name("pythonw.exe"))
    return [
        interpreter,
        "-m",
        "garmin_database.bootstrap.collector",
    ]


def collector_source(store):
    from garmin_database.adapters.outbound.garmin.client import GarminSource

    return GarminSource(store)


def create_manager(config_path=None, scheduler=None, *, manage_access=True):
    from garmin_database.adapters.outbound.collector_runtime import CollectorRuntime
    from garmin_database.adapters.outbound.scheduler.registration import (
        NativeRegistration,
    )
    from garmin_database.application.use_cases.manage_collector import CollectorManager

    files = (
        config_path
        if isinstance(config_path, CollectorFiles)
        else CollectorFiles(config_path)
    )
    if scheduler is None:
        if os.name == "nt":
            from garmin_database.adapters.outbound.scheduler.windows import (
                WindowsScheduler,
            )

            scheduler = WindowsScheduler(
                collector_command(windowless=True), files.config_path
            )
        else:
            from garmin_database.adapters.outbound.scheduler.systemd import (
                SystemdScheduler,
            )

            scheduler = SystemdScheduler(collector_command(), files.config_path)
    return CollectorManager(
        files,
        scheduler,
        registration=NativeRegistration(
            files, scheduler, collector_command, manage_access=manage_access
        ),
        runtime_factory=lambda config, sync: CollectorRuntime(files, config, sync),
        source_factory=collector_source,
    )


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
