"""Runtime data needed by frozen TLS, independent of private Garmin sessions."""

import pytest

from scripts import build

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("managed_runtime", [False, True])
def test_ssl_runtime_resource_is_bundled_in_both_programs(
    tmp_path, monkeypatch, managed_runtime
):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    resource = runtime / "codex-rejected-cas.pem"
    if managed_runtime:
        resource.write_text("synthetic-public-certificate-resource")
    monkeypatch.setattr(build.ssl, "__file__", str(runtime / "ssl.py"))
    monkeypatch.setattr(
        build.sys, "argv", ["build", "--destination", str(tmp_path / "dist")]
    )
    commands = []

    def capture(command, cwd):
        commands.append(command)
        return 0

    monkeypatch.setattr(build.subprocess, "call", capture)
    assert build.main() == 0
    assert len(commands) == 3
    collector = commands[-1]
    assert collector[collector.index("--name") + 1] == "GarminDatabaseCollector"
    assert "PySide6" in collector and "mcp" in collector
    for command in commands:
        arguments = [
            command[i + 1] for i, value in enumerate(command) if value == "--add-data"
        ]
        assert (str(resource) + ":." in arguments) == managed_runtime


def test_collector_only_build_does_not_require_desktop_or_mcp(tmp_path, monkeypatch):
    monkeypatch.setattr(
        build.sys,
        "argv",
        ["build", "--only", "collector", "--destination", str(tmp_path)],
    )
    commands = []
    monkeypatch.setattr(
        build.subprocess, "call", lambda command, cwd: commands.append(command) or 0
    )
    assert build.main() == 0
    assert len(commands) == 1
    assert commands[0][commands[0].index("--name") + 1] == "GarminDatabaseCollector"
