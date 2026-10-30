"""CLI routing and offline operation; no personal configuration or sessions."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.inbound.collector.commands import main
from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.scheduler.manager import ScheduleManager

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
    manager = ScheduleManager(files, scheduler, manage_access=False)

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
