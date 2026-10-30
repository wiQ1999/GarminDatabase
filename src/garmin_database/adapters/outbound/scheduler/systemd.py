"""System units; the minute trigger is a cheap guard for arbitrary UTC intervals."""

import os
import pwd
import re
import subprocess
from pathlib import Path

from garmin_database.adapters.outbound.filesystem.files import atomic_write


def quote(value):
    value = str(value)
    if any(c in value for c in "\n\r\x00"):
        raise ValueError("Nieprawidłowy argument jednostki systemd")
    return (
        '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'
    )


class SystemdScheduler:
    def __init__(
        self,
        command,
        config_path,
        *,
        unit_dir="/etc/systemd/system",
        run=subprocess.run,
    ):
        self.command, self.config_path = command, Path(config_path)
        self.unit_dir, self.run = Path(unit_dir), run

    def name(self, config):
        return "garmin-database-" + config.instance

    def render(self, config):
        if not re.fullmatch(r"[a-z_][a-z0-9_-]*[$]?", config.run_as):
            raise ValueError("Wybierz dedykowane konto Linux")
        if not config.credential_path:
            raise ValueError("Wskaż zaszyfrowane poświadczenie klucza sesji")
        command = " ".join(
            quote(v)
            for v in [
                *self.command,
                "--config",
                str(self.config_path),
                "run",
                "--scheduled",
            ]
        )
        writable = " ".join(
            quote(v)
            for v in dict.fromkeys(
                [
                    config.data_dir,
                    config.state_dir,
                    str(Path(config.session_path).parent),
                ]
            )
        )
        service = f"""[Unit]
Description=GarminDatabase collector {config.revision}
After=network.target

[Service]
Type=oneshot
User={config.run_as}
ExecStart={command}
LoadCredentialEncrypted=garmin-session-key:{quote(config.credential_path)}
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={writable}
TimeoutStartSec=0
TimeoutStopSec=120
"""
        timer = f"""[Unit]
Description=GarminDatabase schedule {config.revision}

[Timer]
OnCalendar=*-*-* *:*:00 UTC
AccuracySec=1s
RandomizedDelaySec=0
Persistent=false
Unit={self.name(config)}.service

[Install]
WantedBy=timers.target
"""
        return service, timer

    def apply(self, config):
        service, timer = self.render(config)
        if not Path(config.credential_path).is_file():
            raise FileNotFoundError("Najpierw przygotuj klucz sesji")
        account = pwd.getpwnam(config.run_as)
        if account.pw_uid == 0:
            raise PermissionError("Kolektor wymaga konta bez uprawnień root")
        for directory in (
            config.state_dir,
            str(Path(config.session_path).parent),
            config.data_dir,
        ):
            path = Path(directory)
            protected = [
                Path(p)
                for p in (
                    "/",
                    "/etc",
                    "/usr",
                    "/proc",
                    "/sys",
                    "/dev",
                    "/var",
                    "/var/lib",
                    "/home",
                    "/opt",
                    "/run",
                    "/tmp",
                )
            ]
            resolved = path.resolve()
            if resolved in protected or any(
                resolved.is_relative_to(Path(p))
                for p in ("/etc", "/usr", "/proc", "/sys", "/dev")
            ):
                raise ValueError("Wybierz wydzielony katalog danych kolektora")
            path.mkdir(parents=True, exist_ok=True)
            os.chown(path, account.pw_uid, account.pw_gid)
        Path(config.state_dir).chmod(0o700)
        Path(config.session_path).parent.chmod(0o700)
        self.unit_dir.mkdir(parents=True, exist_ok=True)
        for suffix, content in (("service", service), ("timer", timer)):
            atomic_write(
                self.unit_dir / f"{self.name(config)}.{suffix}", content.encode()
            )
        self._checked(["systemctl", "daemon-reload"])
        action = "enable" if config.enabled else "disable"
        self._checked(["systemctl", action, "--now", self.name(config) + ".timer"])
        if config.enabled:
            self._checked(["systemctl", "restart", self.name(config) + ".timer"])

    def _checked(self, command):
        result = self.run(command, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError("Nie udało się zastosować harmonogramu systemd")

    def status(self, config):
        path = self.unit_dir / (self.name(config) + ".timer")
        if not path.exists():
            return {"installed": False, "enabled": False, "revision_matches": False}
        result = self.run(
            ["systemctl", "is-active", self.name(config) + ".timer"],
            capture_output=True,
            check=False,
        )
        service = self.unit_dir / (self.name(config) + ".service")
        matches = (
            config.revision in path.read_text()
            and service.is_file()
            and config.revision in service.read_text()
        )
        return {
            "installed": True,
            "enabled": result.returncode == 0,
            "revision_matches": matches,
        }
