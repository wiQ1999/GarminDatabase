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
    assert len(commands) == 2
    for command in commands:
        arguments = [
            command[i + 1] for i, value in enumerate(command) if value == "--add-data"
        ]
        assert (str(resource) + ":." in arguments) == managed_runtime
