"""Coordinate local configuration, native registration and offline diagnostics."""

import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from garmin_database.adapters.outbound.collector_runtime import CollectorRuntime
from garmin_database.application.errors import BusyError


def collector_command():
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
        return [str(binary)]
    return [
        os.path.abspath(sys.executable),
        "-m",
        "garmin_database.bootstrap.collector",
    ]


class ScheduleManager:
    def __init__(self, files, scheduler=None, *, manage_access=True):
        self.files = files
        self.manage_access = manage_access
        if scheduler is None:
            if os.name == "nt":
                from .windows import WindowsScheduler

                scheduler = WindowsScheduler(collector_command(), files.config_path)
            else:
                from .systemd import SystemdScheduler

                scheduler = SystemdScheduler(collector_command(), files.config_path)
        self.scheduler = scheduler

    def runtime(self, config, synchronize):
        return CollectorRuntime(self.files, config, synchronize)

    def status(self, config=None):
        config = config or self.files.load_config()
        state = self.files.load_state(config)
        task = self.scheduler.status(config)
        # Derive next time instead of displaying a stale value saved by an old run.
        next_run = (
            config.schedule.next_after(datetime.now(timezone.utc)).isoformat()
            if config.enabled and task["enabled"]
            else None
        )
        try:
            session_present = Path(config.session_path).is_file()
        except PermissionError:
            session_present = None
        return {
            "schedule": task,
            "config_revision": config.revision,
            "state": asdict(state),
            "next_run": next_run,
            "session_present": session_present,
        }

    def apply(self, config):
        config.validate()
        if os.name == "nt" and self.manage_access:
            import ctypes
            import getpass

            from .windows_access import elevate, prepare_paths

            if not config.status_reader:
                config.status_reader = (
                    os.environ.get("USERDOMAIN", ".") + "\\" + getpass.getuser()
                )
                self.files.save_config(config)

            if not ctypes.windll.shell32.IsUserAnAdmin():
                elevate(
                    [
                        *collector_command(),
                        "--config",
                        str(self.files.config_path),
                        "schedule",
                        "apply",
                    ]
                )
                return
            prepare_paths(config, self.files.config_path)
        self.scheduler.apply(config)
        with self.files.lock(config):
            state = self.files.load_state(config)
            state.applied_revision = config.revision
            self.files.save_state(config, state)
        if (
            self.manage_access
            and os.name != "nt"
            and os.geteuid() == 0
            and config.run_as
        ):
            import pwd

            account = pwd.getpwnam(config.run_as)
            for name in ("status.json", "collector.lock"):
                os.chown(Path(config.state_dir) / name, account.pw_uid, account.pw_gid)

    def prepare_key(self, config):
        if os.name == "nt":
            raise ValueError("Windows używa DPAPI; osobny klucz nie jest potrzebny")
        from garmin_database.adapters.outbound.security.linux_session import prepare_key

        prepare_key(config.credential_path)

    def login(self, config, session_factory, email, password, mfa, stop):
        from garmin_database.adapters.outbound.garmin.client import GarminSource

        store = session_factory(config)
        try:
            with self.files.lock(config), store.lock():
                GarminSource(store).login(email, password, mfa, stop=stop)
                state = self.files.load_state(config)
                state.auth_required = False
                state.auth_generation = None
                self.files.save_state(config, state)
        except BusyError:
            raise
