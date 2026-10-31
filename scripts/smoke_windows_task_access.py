"""Native task ACL regression, no admin requirement, SQL, sessions or network."""

import ctypes
import json
import os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.scheduler.windows import WindowsScheduler


def native(scheduler, script, config):
    result = scheduler._powershell(
        script,
        dict(
            name=scheduler.name(config),
            xml=scheduler.render(config),
            user=config.run_as,
        ),
    )
    if result.returncode:
        raise RuntimeError("Native task access regression failed")
    return result.stdout


def check(base, legacy):
    files = CollectorFiles(base / "collector.json")
    config = replace(
        files.defaults(base / "data"),
        instance="access-test-" + uuid4().hex[:20],
        session_path=str(base / "unused-session.bin"),
        enabled=False,
    )
    scheduler = WindowsScheduler(["unused-collector.exe"], files.config_path)
    created = False
    admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    try:
        if legacy:
            native(
                scheduler,
                r"""$p=ConvertFrom-Json ([Console]::In.ReadToEnd());
$s=New-Object -ComObject 'Schedule.Service';$s.Connect();
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;
$sd='D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGWGXSD;;;'+$sid+')';
$null=$s.GetFolder('\').RegisterTask($p.name,$p.xml,2,$p.user,$null,3,$sd)""",
                config,
            )
            created = True
        try:
            scheduler.apply(config)
        except PermissionError:
            if not legacy or admin:
                raise
            return "legacy_update_requires_elevation"
        created = True
        if legacy:
            if not admin:
                raise AssertionError("Legacy ACL update falsely reported success")
            return "legacy_descriptor_repaired"
        newer = replace(config, interval_minutes=30)
        scheduler.apply(newer)
        status = scheduler.status(newer)
        assert status["installed"] and status["revision_matches"]
        assert status["logon_type"] == 3
        return "new_and_existing_owned_task_readable"
    finally:
        if created:
            native(
                scheduler,
                r"""$p=ConvertFrom-Json ([Console]::In.ReadToEnd());
$s=New-Object -ComObject 'Schedule.Service';$s.Connect();
$s.GetFolder('\').DeleteTask($p.name,0)""",
                config,
            )


def main():
    if os.name != "nt":
        raise RuntimeError("This smoke requires native Windows Task Scheduler")
    root = Path(__file__).resolve().parents[1]
    work = root / "work"
    work.mkdir(exist_ok=True)
    cases = []
    for legacy in (False, True):
        with TemporaryDirectory(prefix="task-access-", dir=work) as directory:
            base = Path(directory).resolve()
            assert base.is_relative_to(work.resolve())
            cases.append(check(base, legacy))
    print(json.dumps(dict(status="passed", cases=cases, synthetic=True)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
