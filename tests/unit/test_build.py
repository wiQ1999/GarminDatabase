"""Runtime data needed by frozen TLS, independent of private Garmin sessions."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts import build

pytestmark = pytest.mark.unit


def execute_collector_spec(monkeypatch):
    """Execute the declarative spec without importing build-time dependencies."""
    hooks = ModuleType("PyInstaller.utils.hooks")
    hooks.collect_all = lambda name: ([], [], [name])
    hooks.collect_data_files = lambda name: [(name, ".")]
    hooks.copy_metadata = lambda name: [(name + ".dist-info", ".")]
    for name in ("PyInstaller", "PyInstaller.utils"):
        package = ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
    entries = []

    def analysis(scripts, **kwargs):
        return SimpleNamespace(
            scripts=scripts,
            pure=[],
            binaries=kwargs["binaries"],
            datas=kwargs["datas"],
            options=kwargs,
        )

    def executable(*args, **kwargs):
        entries.append(kwargs)
        return kwargs

    namespace = dict(
        SPECPATH=str(Path(build.__file__).parent),
        Analysis=analysis,
        PYZ=lambda *args: None,
        EXE=executable,
        COLLECT=lambda *args, **kwargs: args,
    )
    spec = Path(build.__file__).with_name("collector_windows.spec")
    exec(compile(spec.read_text(encoding="utf-8"), str(spec), "exec"), namespace)
    assert {e["name"]: e["console"] for e in entries} == {
        "GarminDatabaseCollector": True,
        "GarminDatabaseCollectorTask": False,
    }
    assert namespace["a"].options["excludes"] == ["PySide6", "mcp"]
    assert namespace["coll"][:2] == tuple(entries)
    return namespace["a"].datas


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
    if build.sys.platform == "win32":
        assert Path(collector[-1]).name == "collector_windows.spec"
        datas = execute_collector_spec(monkeypatch)
        assert ((str(resource), ".") in datas) == managed_runtime
        commands = commands[:-1]
    else:
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
    if build.sys.platform == "win32":
        assert Path(commands[0][-1]).name == "collector_windows.spec"
        execute_collector_spec(monkeypatch)
    else:
        assert commands[0][commands[0].index("--name") + 1] == "GarminDatabaseCollector"
