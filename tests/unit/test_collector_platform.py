"""Boundary behavior for platform APIs using synthetic credentials and handles."""

import ctypes
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
import pytest

from garmin_database.adapters.outbound import collector_runtime
from garmin_database.adapters.outbound.scheduler import windows, windows_access
from garmin_database.application.errors import LoginFailed, SessionRequired

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("code,changed_user", [(0, False), (1223, False), (0, True)])
def test_windows_credential_dialog_clears_buffer_and_checks_identity(
    monkeypatch, code, changed_user
):
    buffers = []

    def prompt(*args):
        buffers.append(args[6])
        args[6].value = "synthetic-private-password"
        if changed_user:
            args[4].value = "other-account"
        return code

    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(credui=SimpleNamespace(CredUIPromptForCredentialsW=prompt)),
        raising=False,
    )
    if code or changed_user:
        with pytest.raises((ValueError, RuntimeError)):
            windows.credential("garmin")
    else:
        assert windows.credential("garmin") == "synthetic-private-password"
    assert buffers[0].value == ""


@pytest.mark.parametrize("accepted,exit_code", [(True, 0), (True, 1), (False, 0)])
def test_elevation_passes_only_command_arguments_and_closes_handle(
    monkeypatch, accepted, exit_code
):
    close = Mock()

    def launch(pointer):
        request = pointer._obj
        assert request.lpVerb == "runas"
        assert "schedule apply" in request.lpParameters
        request.hProcess = 4
        return accepted

    def status(handle, pointer):
        pointer._obj.value = exit_code
        return 1

    shell = SimpleNamespace(ShellExecuteExW=launch)
    kernel = SimpleNamespace(
        WaitForSingleObject=Mock(return_value=0),
        GetExitCodeProcess=status,
        CloseHandle=close,
    )
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name, **_: shell if name == "shell32" else kernel,
        raising=False,
    )
    if not accepted or exit_code:
        with pytest.raises((PermissionError, RuntimeError)):
            windows_access.elevate(
                ["collector.exe", "--config", "C:/config.json", "schedule", "apply"]
            )
    else:
        windows_access.elevate(
            ["collector.exe", "--config", "C:/config.json", "schedule", "apply"]
        )
    assert close.call_count == int(accepted)


def test_auth_acl_excludes_status_reader(tmp_path, monkeypatch):
    from garmin_database.application.collector_models import CollectorConfig

    config = CollectorConfig(
        str(tmp_path / "data"),
        str(tmp_path / "state"),
        str(tmp_path / "state/auth/session.bin"),
        run_as="service",
        status_reader="operator",
    )
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(windows_access.subprocess, "run", run)
    windows_access.prepare_paths(config, tmp_path / "config.json")
    calls = [call.args[0] for call in run.call_args_list]
    auth_call = next(
        command for command in calls if command[1] == str(tmp_path / "state/auth")
    )
    assert "service:(OI)(CI)F" in auth_call
    assert not any("operator" in argument for argument in auth_call)
    run.return_value.returncode = 1
    with pytest.raises(PermissionError):
        windows_access.prepare_paths(config, tmp_path / "config.json")


@pytest.mark.parametrize(
    "error,outcome",
    [
        (psycopg.OperationalError("private"), "database_error"),
        (SessionRequired(), "auth_required"),
        (LoginFailed("session_save", "LOCAL_SESSION"), "session_error"),
        (PermissionError("private"), "session_error"),
        (RuntimeError("private"), "interrupted"),
    ],
)
def test_runtime_classification_never_exposes_error(error, outcome):
    runtime = collector_runtime.CollectorRuntime(None, None, None)
    assert runtime.classify(error) == outcome


def test_runtime_windows_boot_time_uses_64_bit_counter(monkeypatch):
    def tick():
        return 90000

    monkeypatch.setattr(collector_runtime, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(kernel32=SimpleNamespace(GetTickCount64=tick)),
        raising=False,
    )
    runtime = collector_runtime.CollectorRuntime(None, None, None)
    runtime.now = lambda: datetime(2026, 10, 30, 10, tzinfo=timezone.utc)
    assert (runtime.now() - runtime.boot_at()).total_seconds() == 90


def test_runtime_linux_clock_and_missing_boot_record(monkeypatch):
    runtime = collector_runtime.CollectorRuntime(None, None, None)
    monkeypatch.setattr(collector_runtime, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(
        collector_runtime,
        "Path",
        lambda _: SimpleNamespace(read_text=lambda: "btime 100\n"),
    )
    assert runtime.boot_at().timestamp() == 100
    monkeypatch.setattr(
        collector_runtime,
        "Path",
        lambda _: SimpleNamespace(read_text=lambda: "other 100\n"),
    )
    with pytest.raises(RuntimeError):
        runtime.boot_at()
