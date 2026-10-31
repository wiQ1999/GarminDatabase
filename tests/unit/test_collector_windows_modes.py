import json
import os
import xml.etree.ElementTree as ET
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.outbound.filesystem.collector_files import (
    CollectorFiles,
    current_account,
)
from garmin_database.adapters.outbound.filesystem.settings_json import application_dir
from garmin_database.adapters.outbound.scheduler import windows, windows_access
from garmin_database.adapters.outbound.scheduler.manager import (
    ScheduleManager,
    collector_command,
)
from garmin_database.application.errors import CollectorInstallIncomplete


def test_interactive_registration_never_asks_for_password_or_batch_rights(
    tmp_path, monkeypatch
):
    files = CollectorFiles(tmp_path / "collector.json")
    config = replace(
        files.defaults(tmp_path / "data"),
        run_as="synthetic",
        windows_logon="interactive",
    )
    monkeypatch.setattr(windows, "current_account", lambda: "synthetic")
    prompt = Mock(side_effect=AssertionError("No Windows password"))
    grant = Mock(side_effect=AssertionError("No batch logon right"))
    run = Mock(return_value=SimpleNamespace(returncode=0))
    scheduler = windows.WindowsScheduler(
        ["collector.exe"], files.config_path, run=run, prompt=prompt, grant_batch=grant
    )
    scheduler.apply(config)
    root = ET.fromstring(scheduler.render(config))
    assert root.find(".//{*}LogonType").text == "InteractiveToken"
    payload = json.loads(run.call_args.kwargs["input"])
    assert payload["logon"] == 3 and payload["password"] is None
    prompt.assert_not_called()
    grant.assert_not_called()
    run.reset_mock()
    with pytest.raises(ValueError, match="bieżącego konta"):
        scheduler.apply(replace(config, run_as="another-account"))
    run.assert_not_called()


def test_legacy_configuration_keeps_password_mode_and_session(tmp_path):
    files = CollectorFiles(tmp_path / "collector.json")
    value = asdict(files.defaults(tmp_path / "data"))
    value.pop("windows_logon")
    value["schema_version"] = 1
    files.config_path.write_text(json.dumps(value))
    loaded = files.load_config()
    assert loaded.windows_logon == "password" and loaded.schema_version == 1
    assert loaded.session_path == value["session_path"]


@pytest.mark.parametrize(
    "installed,matching,accepted",
    [(None, False, False), (True, False, False), (True, True, True)],
)
def test_elevated_exit_success_requires_readable_current_task(
    tmp_path, monkeypatch, installed, matching, accepted
):
    files = CollectorFiles(tmp_path / "collector.json")
    config = files.defaults(tmp_path / "data")
    scheduler = Mock()
    scheduler.status.return_value = {
        "installed": installed,
        "revision_matches": matching,
    }
    elevation = Mock()
    monkeypatch.setattr(windows_access, "elevate", elevation)
    manager = ScheduleManager(files, scheduler)
    if accepted:
        manager._elevate(config)
    else:
        with pytest.raises(CollectorInstallIncomplete):
            manager._elevate(config)
    elevation.assert_called_once()
    scheduler.status.assert_called_once_with(config)


@pytest.mark.skipif(os.name != "nt", reason="Windows interactive profile")
def test_account_change_preserves_old_files_and_uses_gui_session_by_reference(tmp_path):
    files = CollectorFiles(tmp_path / "settings.json")
    initial = files.defaults(tmp_path / "data", settings_path=files.config_path)
    gui_session = application_dir() / "auth/session.bin"
    assert initial.windows_logon == "interactive" and initial.session_path == str(
        gui_session
    )
    dedicated = files.for_account(initial, "SYNTHETIC\\collector", "password")
    old_session = Path(dedicated.session_path)
    old_session.parent.mkdir(parents=True)
    old_session.write_bytes(b"synthetic-ciphertext-owned-by-another-account")
    current = files.for_account(dedicated, windows_logon="interactive")
    assert current.run_as == current_account()
    assert current.state_dir != dedicated.state_dir and current.session_path == str(
        gui_session
    )
    assert old_session.read_bytes() == b"synthetic-ciphertext-owned-by-another-account"
    assert not gui_session.exists()  # No copying, decrypting or re-encrypting.
    same_account_password = files.for_account(current, current.run_as, "password")
    assert same_account_password.state_dir != current.state_dir
    assert same_account_password.session_path != str(gui_session)
    restored = files.for_account(current, dedicated.run_as, "password")
    assert restored.session_path == dedicated.session_path


@pytest.mark.skipif(os.name != "nt", reason="Windows registration permissions")
def test_current_profile_installs_without_elevation_or_acl_changes(
    tmp_path, monkeypatch
):
    files = CollectorFiles(tmp_path / "collector.json")
    config = files.defaults(tmp_path / "data")
    files.save_config(config)
    blocked = Mock(side_effect=AssertionError("No administrative change"))
    monkeypatch.setattr(windows_access, "elevate", blocked)
    monkeypatch.setattr(windows_access, "prepare_paths", blocked)
    scheduler = Mock()
    manager = ScheduleManager(files, scheduler)
    manager.apply(config)
    scheduler.apply.assert_called_once_with(config)
    assert files.load_state(config).applied_revision == config.revision
    blocked.assert_not_called()


@pytest.mark.skipif(os.name != "nt", reason="Windows executables")
def test_scheduler_uses_windowless_entry_and_console_cli_stays_available(
    tmp_path, monkeypatch
):
    from garmin_database.adapters.outbound.scheduler import manager

    binary = tmp_path / "GarminDatabase/GarminDatabase.exe"
    monkeypatch.setattr(manager.sys, "frozen", True, raising=False)
    monkeypatch.setattr(manager.sys, "executable", str(binary))
    assert collector_command()[0].endswith("GarminDatabaseCollector.exe")
    assert collector_command(windowless=True)[0].endswith(
        "GarminDatabaseCollectorTask.exe"
    )
