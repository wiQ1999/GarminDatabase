"""Native scheduler contracts, offline status and safe registration arguments."""

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.scheduler.manager import (
    ScheduleManager,
    collector_command,
)
from garmin_database.adapters.outbound.scheduler.windows import WindowsScheduler

pytestmark = pytest.mark.unit


@pytest.fixture
def setup(tmp_path):
    files = CollectorFiles(tmp_path / "collector.json")
    config = replace(
        files.defaults(tmp_path / "data"),
        state_dir=str(tmp_path / "state"),
        session_path=str(tmp_path / "auth/session.bin"),
        run_as="garmin",
        enabled=True,
    )
    files.save_config(config)
    return files, config


def test_windows_xml_is_noninteractive_fixed_and_does_not_catch_up(setup):
    files, config = setup
    scheduler = WindowsScheduler(
        [r"C:\Program Files\Garmin\collector.exe"], files.config_path
    )
    root = ET.fromstring(scheduler.render(config))

    def text(name):
        return root.find(".//{*}" + name).text

    assert text("MultipleInstancesPolicy") == "IgnoreNew"
    assert text("StartWhenAvailable") == "false"
    assert text("LogonType") == "Password"
    assert text("Interval") == "PT120M"
    assert text("ExecutionTimeLimit") == "PT0S"
    assert text("RunLevel") == "LeastPrivilege"
    assert "run --scheduled" in text("Arguments")
    assert root.find(".//{*}BootTrigger") is None
    assert root.find(".//{*}LogonTrigger") is None
    long = ET.fromstring(scheduler.render(replace(config, interval_minutes=525600)))
    assert long.find(".//{*}Interval").text == "PT1440M"


def test_windows_password_only_in_registration_pipe(setup):
    files, config = setup
    run = Mock(return_value=SimpleNamespace(returncode=0))
    grant = Mock()
    scheduler = WindowsScheduler(
        ["collector.exe"],
        files.config_path,
        run=run,
        prompt=lambda _: "synthetic-secret",
        grant_batch=grant,
    )
    scheduler.apply(config)
    grant.assert_called_once_with(config.run_as)
    args, kwargs = run.call_args
    assert "synthetic-secret" not in repr(args)
    assert json.loads(kwargs["input"])["password"] == "synthetic-secret"
    run.return_value.returncode = 1
    with pytest.raises(RuntimeError, match="zarejestrować"):
        scheduler.apply(config)
    with pytest.raises(ValueError):
        scheduler.render(replace(config, run_as=""))
    run.reset_mock()
    grant.side_effect = PermissionError("synthetic policy failure")
    with pytest.raises(PermissionError):
        scheduler.apply(config)
    run.assert_not_called()


@pytest.mark.parametrize("returncode,expected", [(0, True), (3, False), (1, None)])
def test_windows_status_does_not_request_credentials(setup, returncode, expected):
    files, config = setup
    prompt = Mock(side_effect=AssertionError("credential requested"))
    run = Mock(
        return_value=SimpleNamespace(
            returncode=returncode,
            stdout=json.dumps(
                {"installed": True, "enabled": True, "revision_matches": True}
            ),
        )
    )
    scheduler = WindowsScheduler(
        ["collector.exe"], files.config_path, run=run, prompt=prompt
    )
    if expected is None:
        with pytest.raises(RuntimeError):
            scheduler.status(config)
    else:
        assert scheduler.status(config)["installed"] is expected
    prompt.assert_not_called()


@pytest.mark.skipif(os.name == "nt", reason="systemd is a Linux deployment adapter")
def test_systemd_render_matches_real_calendar_parser_and_hardening(setup, tmp_path):
    from garmin_database.adapters.outbound.scheduler.systemd import SystemdScheduler

    files, config = setup
    scheduler = SystemdScheduler(
        ["/opt/garmin/.venv/bin/python", "-m", "garmin_database.bootstrap.collector"],
        files.config_path,
        unit_dir=tmp_path,
    )
    service, timer = scheduler.render(config)
    assert "Type=oneshot" in service and "TimeoutStartSec=0" in service
    assert "LoadCredentialEncrypted=garmin-session-key:" in service
    assert 'garmin-session-key:"' not in service
    assert "NoNewPrivileges=true" in service
    assert "Persistent=false" in timer and "OnBootSec" not in timer
    result = subprocess.run(
        ["systemd-analyze", "calendar", "*-*-* *:*:00 UTC"], capture_output=True
    )
    assert result.returncode == 0
    with pytest.raises(ValueError):
        scheduler.render(replace(config, run_as="root; command"))
    with pytest.raises(ValueError):
        scheduler.render(replace(config, credential_path=""))


@pytest.mark.skipif(os.name == "nt", reason="systemd registration requires Linux")
def test_systemd_apply_status_failure_and_disabled_do_not_start_sync(
    setup, tmp_path, monkeypatch
):
    from garmin_database.adapters.outbound.scheduler import systemd

    files, config = setup
    credential = tmp_path / "session-key.cred"
    credential.write_bytes(b"sealed-synthetic-key")
    config = replace(config, credential_path=str(credential))
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(systemd.os, "chown", lambda *args: None)
    monkeypatch.setattr(
        systemd.pwd, "getpwnam", lambda _: SimpleNamespace(pw_uid=1000, pw_gid=1000)
    )
    scheduler = systemd.SystemdScheduler(
        ["/opt/collector"], files.config_path, unit_dir=tmp_path / "units", run=run
    )
    assert not scheduler.status(config)["installed"]
    scheduler.apply(config)
    assert files.config_path.stat().st_mode & 0o777 == 0o640
    assert scheduler.status(config) == {
        "installed": True,
        "enabled": True,
        "revision_matches": True,
    }
    assert "start" not in [arg for call in run.call_args_list for arg in call.args[0]]
    assert not scheduler.status(replace(config, interval_minutes=90))[
        "revision_matches"
    ]
    disabled = replace(config, enabled=False)
    scheduler.apply(disabled)
    assert any(call.args[0][1:3] == ["disable", "--now"] for call in run.call_args_list)
    run.return_value.returncode = 1
    assert not scheduler.status(config)["enabled"]
    with pytest.raises(RuntimeError):
        scheduler.apply(config)
    credential.unlink()
    with pytest.raises(FileNotFoundError):
        scheduler.apply(config)


def test_manager_status_works_without_sql_and_records_only_applied_revision(
    setup, monkeypatch
):
    import psycopg

    files, config = setup
    monkeypatch.setattr(
        psycopg, "connect", Mock(side_effect=AssertionError("SQL used for status"))
    )
    scheduler = Mock()
    scheduler.status.return_value = {
        "installed": True,
        "enabled": True,
        "revision_matches": True,
    }
    manager = ScheduleManager(files, scheduler, manage_access=False)
    manager.apply(config)
    status = manager.status()
    assert status["state"]["applied_revision"] == config.revision
    assert status["next_run"] is not None
    scheduler.apply.side_effect = RuntimeError("synthetic failure")
    newer = replace(config, interval_minutes=90)
    with pytest.raises(RuntimeError):
        manager.apply(newer)
    assert files.load_state(config).applied_revision == config.revision
    config.enabled = False
    assert manager.status(config)["next_run"] is None


def test_command_preserves_virtualenv_interpreter_path(monkeypatch, tmp_path):
    from garmin_database.adapters.outbound.scheduler import manager

    interpreter = str(tmp_path / ".venv/bin/python")
    monkeypatch.setattr(manager.sys, "executable", interpreter)
    assert collector_command()[0] == interpreter
    monkeypatch.setattr(manager.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        manager.sys, "executable", str(tmp_path / "GarminDatabase/GarminDatabase")
    )
    assert "GarminDatabaseCollector" in collector_command()[0]
