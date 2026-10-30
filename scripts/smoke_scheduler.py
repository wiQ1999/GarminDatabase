"""Native CI acceptance: disposable account/task, encrypted session, no Garmin API.

Requires admin/root and GARMIN_TEST_DATABASE_DSN, never application resources.
Every account, task, schema and directory belongs exclusively to this smoke run.
"""

import argparse
import ctypes
import getpass
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.scheduler.manager import ScheduleManager


def powershell(script, payload):
    result = subprocess.run(
        [
            shutil.which("pwsh.exe") or "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; $p=ConvertFrom-Json ([Console]::In.ReadToEnd()); try { "
            + script
            + " } catch { [Console]::Error.WriteLine(($_.CategoryInfo.Reason + ':' + $_.FullyQualifiedErrorId + ':' + $_.InvocationInfo.MyCommand.Name)); exit 1 }",
        ],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        # Only this isolated smoke uses generated credentials. Never print the
        # PowerShell exception message, command source, payload or password.
        category = result.stderr.strip().splitlines()[-1] if result.stderr else "unknown"
        if not re.fullmatch(r"[A-Za-z0-9_.:, -]{1,240}", category):
            category = "unknown"
        raise RuntimeError("Native Windows smoke operation failed: " + category)
    return result.stdout


def create_account(name, base):
    if os.name == "nt":
        password = secrets.token_urlsafe(24) + "aA1!"
        powershell(
            "$s=ConvertTo-SecureString $p.password -AsPlainText -Force; $null=New-LocalUser -Name $p.name -Password $s; Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $p.name",
            {"name": name, "password": password},
        )
        return os.environ["COMPUTERNAME"] + "\\" + name, password
    subprocess.run(
        [
            "useradd",
            "--system",
            "--user-group",
            "--create-home",
            "--home-dir",
            str(base / "home"),
            name,
        ],
        check=True,
        capture_output=True,
    )
    return name, None


def scheduler(files, command, config, password, probe):
    if os.name == "nt":
        from garmin_database.adapters.outbound.scheduler.windows import (
            NS,
            WindowsScheduler,
        )

        class ProbeScheduler(WindowsScheduler):
            def render(self, config):
                root = ET.fromstring(super().render(config))
                action = ET.Element("{" + NS + "}Exec")
                ET.SubElement(action, "{" + NS + "}Command").text = sys.executable
                ET.SubElement(
                    action, "{" + NS + "}Arguments"
                ).text = subprocess.list2cmdline(
                    ["-I", str(probe), str(files.config_path)]
                )
                root.find("{" + NS + "}Actions").insert(0, action)
                return ET.tostring(root, encoding="unicode")

        return ProbeScheduler(command, files.config_path, prompt=lambda _: password)
    from garmin_database.adapters.outbound.scheduler.systemd import (
        SystemdScheduler,
        quote,
    )

    class ProbeScheduler(SystemdScheduler):
        def render(self, config):
            service, timer = super().render(config)
            pre = " ".join(
                quote(v)
                for v in [sys.executable, "-I", str(probe), str(files.config_path)]
            )
            service = service.replace(
                "\nExecStart=", "\nExecStartPre=" + pre + "\nExecStart="
            )
            return service, timer

    return ProbeScheduler(command, files.config_path)


def cleanup_task(instance):
    if os.name == "nt":
        powershell(
            "$s=New-Object -ComObject 'Schedule.Service'; $s.Connect(); try { $t=$s.GetFolder('\\').GetTask($p.name); $t.Stop(0); for($i=0; $i -lt 100 -and $t.State -eq 4; $i++){ Start-Sleep -Milliseconds 100 }; $s.GetFolder('\\').DeleteTask($p.name,0) } catch {}",
            {"name": "GarminDatabase-" + instance},
        )
    else:
        for suffix in ("timer", "service"):
            subprocess.run(
                [
                    "systemctl",
                    "disable",
                    "--now",
                    "garmin-database-" + instance + "." + suffix,
                ],
                capture_output=True,
                timeout=30,
            )
            Path(
                "/etc/systemd/system", "garmin-database-" + instance + "." + suffix
            ).unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=30)


def diagnostics(instance, state):
    print(
        "Native smoke outcome:",
        state.outcome,
        "started:",
        state.started_at,
        "slot:",
        state.claimed_slot,
    )
    if os.name == "nt":
        print(
            powershell(
                "$s=New-Object -ComObject 'Schedule.Service'; $s.Connect(); $t=$s.GetFolder('\\').GetTask($p.name); @{state=$t.State; result=[long]$t.LastTaskResult; now=[datetime]::UtcNow.ToString('o'); next=$t.NextRunTime.ToUniversalTime().ToString('o'); last=$t.LastRunTime.ToUniversalTime().ToString('o'); xml=$t.Xml} | ConvertTo-Json; Get-WinEvent -LogName 'Microsoft-Windows-TaskScheduler/Operational' -MaxEvents 100 -ErrorAction SilentlyContinue | ForEach-Object { $e=[xml]$_.ToXml(); if($e.Event.EventData.Data | Where-Object { $_.Name -eq 'TaskName' -and $_.'#text' -eq ('\\' + $p.name) }) { @{id=$_.Id; data=$e.Event.EventData.OuterXml} | ConvertTo-Json -Compress } }",
                {"name": "GarminDatabase-" + instance},
            )
        )
    else:
        result = subprocess.run(
            [
                "journalctl",
                "--unit=garmin-database-" + instance + ".service",
                "--no-pager",
                "-n",
                "40",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        # This job has synthetic credentials and cannot call the Garmin API.
        print(result.stdout[-12000:])


def main():
    args = argparse.ArgumentParser()
    args.add_argument("executable", type=Path, nargs="?")
    args.add_argument("--preflight", action="store_true")
    options = args.parse_args()
    if options.executable is None and not options.preflight:
        args.error("executable is required unless --preflight is selected")
    binary = options.executable.resolve() if options.executable else None
    dsn = os.environ.get("GARMIN_TEST_DATABASE_DSN")
    if not dsn:
        raise RuntimeError("Separate GARMIN_TEST_DATABASE_DSN is required")
    admin = (
        ctypes.windll.shell32.IsUserAnAdmin() if os.name == "nt" else os.geteuid() == 0
    )
    if not admin:
        raise PermissionError("Native smoke requires an isolated admin/root CI runner")
    nonce = uuid4().hex[:10]
    name, schema = "gdbci" + nonce, "garmin_native_" + nonce
    base = (Path(os.environ["PROGRAMDATA"]) if os.name == "nt" else Path("/opt")) / (
        "garmin-ci-" + nonce
    )
    base.mkdir(mode=0o755)
    if os.name == "nt" and not options.preflight:
        subprocess.run(
            ["wevtutil.exe", "sl", "Microsoft-Windows-TaskScheduler/Operational", "/e:true"],
            check=True,
            capture_output=True,
        )
    created = False
    try:
        account, password = create_account(name, base)
        created = True
        if options.preflight:
            print("Native scheduler account preflight OK")
            return
        program = base / "program"
        shutil.copytree(binary.parent, program)
        source = base / "source"
        shutil.copytree(
            Path(__file__).resolve().parents[1] / "src",
            source,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        probe = base / "session-probe.py"
        probe.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            + f"sys.path.insert(0,{str(source)!r})\n"
            + "from garmin_database.bootstrap.collector import session_store\n"
            + "from garmin_database.application.collector_models import CollectorConfig\n"
            + "config=CollectorConfig(**json.loads(Path(sys.argv[1]).read_text()))\n"
            + "store=session_store(config)\n"
            + "with store.lock():\n store.save('synthetic-native-session')\n assert store.load()=='synthetic-native-session'\n store.clear()\n"
            + "(Path(config.state_dir)/'session-probe.ok').write_text('ok')\n",
            encoding="utf-8",
        )
        if os.name == "nt":
            for directory in (program, source):
                subprocess.run(
                    [
                        "icacls.exe",
                        str(directory),
                        "/grant",
                        account + ":(OI)(CI)RX",
                        "/T",
                    ],
                    capture_output=True,
                    check=True,
                )
        with psycopg.connect(dsn, autocommit=True) as database:
            database.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            try:
                files = CollectorFiles(base / "collector.json")
                config = replace(
                    files.defaults(base / "data"),
                    state_dir=str(base / "state"),
                    session_path=str(base / "state/auth/session.bin"),
                    run_as=account,
                    instance=name,
                    status_reader=(
                        os.environ.get("USERDOMAIN", ".") + "\\" + getpass.getuser()
                    )
                    if os.name == "nt"
                    else "",
                    database_dsn=make_conninfo(dsn, options="-c search_path=" + schema),
                    interval_minutes=15,
                    enabled=True,
                    anchor_at=(datetime.now(timezone.utc) + timedelta(minutes=2))
                    .replace(second=0, microsecond=0)
                    .isoformat(),
                )
                files.save_config(config)
                manager = ScheduleManager(
                    files,
                    scheduler(
                        files, [str(program / binary.name)], config, password, probe
                    ),
                )
                if os.name != "nt":
                    manager.prepare_key(config)
                manager.apply(config)
                deadline = time.monotonic() + 210
                while time.monotonic() < deadline:
                    state = files.load_state(config)
                    if state.outcome == "auth_required":
                        break
                    if state.finished_at and state.outcome not in {
                        "running",
                        "never_run",
                    }:
                        diagnostics(name, state)
                        raise RuntimeError(
                            "Native collector finished with " + state.outcome
                        )
                    time.sleep(1)
                else:
                    diagnostics(name, state)
                    raise RuntimeError("Native scheduled collector did not complete")
                assert (Path(config.state_dir) / "session-probe.ok").read_text() == "ok"
                assert state.auth_required and state.summary["processed_days"] == 1
                assert not Path(config.session_path).exists()
                print(
                    "Native scheduler smoke OK: dedicated account, encrypted session, persistent auth pause"
                )
            finally:
                cleanup_task(name)
                database.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
                )
    finally:
        if created:
            if os.name == "nt":
                powershell("Remove-LocalUser -Name $p.name", {"name": name})
            else:
                subprocess.run(["userdel", name], capture_output=True, check=False)
        shutil.rmtree(base)


if __name__ == "__main__":
    main()
