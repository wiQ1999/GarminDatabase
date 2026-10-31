"""Coordinate local configuration, native registration and offline diagnostics."""

import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from garmin_database.adapters.outbound.collector_runtime import CollectorRuntime
from garmin_database.application.errors import BusyError, CollectorInstallIncomplete


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


class ScheduleManager:
    def __init__(self, files, scheduler=None, *, manage_access=True):
        self.files = files
        self.manage_access = manage_access
        if scheduler is None:
            if os.name == "nt":
                from .windows import WindowsScheduler

                scheduler = WindowsScheduler(
                    collector_command(windowless=True), files.config_path
                )
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
        if os.name == "nt" and self.manage_access and self._prepare_windows(config):
            return
        try:
            self.scheduler.apply(config)
        except PermissionError:
            if not self._elevate_on_denial(config):
                raise
            return
        self._record_applied(config)

    def _elevate(self, config):
        from .windows_access import elevate

        elevate(
            [
                *collector_command(),
                "--config",
                str(self.files.config_path),
                "schedule",
                "apply",
            ]
        )
        status = self.scheduler.status(config)
        if status["installed"] is not True or not status["revision_matches"]:
            raise CollectorInstallIncomplete()

    def _elevate_on_denial(self, config):
        if os.name != "nt" or not self.manage_access:
            return False
        import ctypes

        if ctypes.windll.shell32.IsUserAnAdmin():
            return False
        self._elevate(config)
        return True

    def _prepare_windows(self, config):
        if config.windows_logon != "password":
            return False
        import ctypes

        from garmin_database.adapters.outbound.filesystem.collector_files import (
            current_account,
        )

        from .windows_access import prepare_paths

        if not config.status_reader:
            config.status_reader = current_account()
            self.files.save_config(config)
        if not ctypes.windll.shell32.IsUserAnAdmin():
            self._elevate(config)
            return True
        prepare_paths(config, self.files.config_path)
        return False

    def _record_applied(self, config):
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

    def install(self, config):
        """Prepare a new Linux key once and register the saved configuration."""
        if os.name != "nt" and not Path(config.credential_path).exists():
            self.prepare_key(config)
        self.apply(config)

    def prepare_key(self, config):
        if os.name == "nt":
            raise ValueError("Windows używa DPAPI; osobny klucz nie jest potrzebny")
        from garmin_database.adapters.outbound.security.linux_session import prepare_key

        prepare_key(config.credential_path)

    def login(
        self, config, session_factory, email, password, mfa, stop, *, progress=None
    ):
        from garmin_database.adapters.outbound.garmin.client import GarminSource

        store = session_factory(config)
        try:
            with self.files.lock(config), store.lock():
                GarminSource(store).login(
                    email, password, mfa, stop=stop, progress=progress
                )
                state = self.files.load_state(config)
                state.auth_required = False
                state.auth_generation = None
                self.files.save_state(config, state)
        except BusyError:
            raise
