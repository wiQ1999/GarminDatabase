"""CLI routing and offline operation; no personal configuration or sessions."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.inbound.collector.commands import main
from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.application.collector_models import CollectorState
from garmin_database.bootstrap.collector import create_manager

pytestmark = pytest.mark.unit


@pytest.fixture
def cli(tmp_path):
    files = CollectorFiles(tmp_path / "config.json")
    config = replace(
        files.defaults(tmp_path / "data"),
        state_dir=str(tmp_path / "state"),
        session_path=str(tmp_path / "session.bin"),
    )
    files.save_config(config)
    scheduler = Mock()
    scheduler.status.return_value = {
        "installed": False,
        "enabled": False,
        "revision_matches": False,
    }
    manager = create_manager(files, scheduler, manage_access=False)

    def invoke(args):
        return main(
            args,
            files_factory=lambda _: files,
            manager_factory=lambda _: manager,
            session_factory=Mock(),
            synchronize=Mock(side_effect=AssertionError("unexpected sync")),
        )

    return SimpleNamespace(invoke=invoke, files=files, manager=manager)


@pytest.mark.parametrize(
    "command",
    [["run", "--scheduled"], ["status", "--json"], ["logs"], ["schedule", "status"]],
)
def test_offline_commands_do_not_connect_sql_or_garmin(cli, command, capsys):
    assert cli.invoke(command) == 0
    assert "private" not in capsys.readouterr().out


@pytest.mark.parametrize("command", [["status", "--json"], ["schedule", "status"]])
def test_cli_status_presents_warsaw_without_rewriting_state(cli, command, capsys):
    config = cli.files.load_config()
    state = CollectorState(started_at="2026-07-15T23:30:00Z")
    cli.files.save_state(config, state)
    assert cli.invoke(command) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"]["started_at"] == "2026-07-16T01:30:00+02:00"
    assert cli.files.load_state(config).started_at == state.started_at


def test_init_never_overwrites_configuration(cli):
    original = cli.files.config_path.read_bytes()
    assert cli.invoke(["init"]) == 1
    assert cli.files.config_path.read_bytes() == original
    cli.files.config_path.unlink()
    assert cli.invoke(["init"]) == 0
    assert cli.files.load_config().interval_minutes == 120


def test_enable_and_disable_are_separate_from_save(cli):
    assert cli.invoke(["schedule", "enable"]) == 0
    assert cli.files.load_config().enabled
    assert cli.invoke(["schedule", "disable"]) == 0
    assert not cli.files.load_config().enabled


def test_scheduled_run_returns_safe_error_if_registration_outdated(
    cli, monkeypatch, capsys
):
    config = cli.files.load_config()
    config.enabled = True
    cli.files.save_config(config)
    runtime = cli.manager.runtime(config, Mock())
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)
    runtime.now = lambda: now
    runtime.boot_at = lambda: now - timedelta(days=1)
    monkeypatch.setattr(cli.manager, "runtime", lambda *a: runtime)
    assert cli.invoke(["run", "--scheduled"]) == 2
    assert "config_error" in capsys.readouterr().out


def test_login_never_prompts_in_scheduled_or_noninteractive_context(cli, monkeypatch):
    from garmin_database.adapters.inbound.collector import commands

    monkeypatch.setattr(commands.sys.stdin, "isatty", lambda: False)
    assert cli.invoke(["login"]) == 1


def test_install_preserves_settings_and_registers_saved_config(cli):
    assert cli.invoke(["install", "--account", "synthetic", "--interval", "30"]) == 0
    config = cli.files.load_config()
    assert config.run_as == "synthetic" and config.interval_minutes == 30
    assert not config.enabled
    cli.manager.scheduler.apply.assert_called_once_with(config)
    assert cli.invoke(["install", "--enable"]) == 0
    assert cli.files.load_config().enabled


def test_install_creates_missing_section_and_rejects_bad_cycle(cli):
    cli.files.config_path.unlink()
    assert cli.invoke(["install", "--interval", "1"]) == 1
    assert not cli.files.config_path.exists()
    assert cli.invoke(["install"]) == 0


def test_install_preserves_existing_global_file_with_custom_name(cli, tmp_path):
    from garmin_database.adapters.outbound.filesystem.settings_json import Settings

    cli.files.config_path.unlink()
    Settings(
        data_dir=str(tmp_path / "archive"),
        database_dsn="host=existing",
        download_from="2025-02-03",
        refresh_seconds=45,
    ).save(cli.files.config_path)
    assert cli.invoke(["install", "--interval", "30"]) == 0
    saved = Settings.load(cli.files.config_path)
    assert saved.data_dir == str(tmp_path / "archive")
    assert saved.database_dsn == "host=existing"
    assert saved.download_from == "2025-02-03" and saved.refresh_seconds == 45
    assert saved.collector["interval_minutes"] == 30


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows interactive mode")
def test_install_can_switch_to_current_account_without_password(cli):
    from garmin_database.adapters.outbound.filesystem.collector_files import (
        current_account,
    )

    config = cli.files.load_config()
    cli.files.save_config(
        replace(config, run_as="SYNTHETIC\\other", windows_logon="password")
    )
    assert cli.invoke(["install", "--logon", "interactive"]) == 0
    configured = cli.files.load_config()
    assert (
        configured.run_as == current_account()
        and configured.windows_logon == "interactive"
    )
