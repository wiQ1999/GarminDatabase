"""Native registration, elevation and filesystem permissions."""

import os
from pathlib import Path

from garmin_database.application.errors import CollectorInstallIncomplete


class NativeRegistration:
    def __init__(self, files, scheduler, command_factory, *, manage_access=True):
        self.files = files
        self.scheduler = scheduler
        self.command_factory = command_factory
        self.manage_access = manage_access

    def apply(self, config):
        config.validate()
        if os.name == "nt" and self.manage_access and self._prepare_windows(config):
            return True
        try:
            self.scheduler.apply(config)
        except PermissionError:
            if not self._elevate_on_denial(config):
                raise
            return True
        return False

    def _elevate(self, config):
        from .windows_access import elevate

        elevate(
            [
                *self.command_factory(),
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

    def install(self, config):
        """Prepare a new Linux key once and register the saved configuration."""
        if os.name != "nt" and not Path(config.credential_path).exists():
            self.prepare_key(config)
        return self.apply(config)

    def prepare_key(self, config):
        if os.name == "nt":
            raise ValueError("Windows używa DPAPI; osobny klucz nie jest potrzebny")
        from garmin_database.adapters.outbound.security.linux_session import prepare_key

        prepare_key(config.credential_path)

    def after_applied(self, config):
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
