"""Executable dependency rules for Clean Architecture."""

import ast
import subprocess
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/garmin_database"
pytestmark = pytest.mark.unit


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        if isinstance(node, ast.ImportFrom):
            package = ".".join(path.parent.relative_to(PACKAGE.parent).parts)
            yield resolve_name("." * node.level + (node.module or ""), package)


@pytest.mark.parametrize(
    "layer", ["domain", "application", "adapters/inbound", "adapters/outbound"]
)
def test_dependencies_point_towards_core(layer):
    allowed = {
        "domain": ("domain",),
        "application": ("domain", "application"),
        "adapters/inbound": ("domain", "application", "adapters.inbound"),
        "adapters/outbound": ("domain", "application", "adapters.outbound"),
    }[layer]
    for path in (PACKAGE / layer).rglob("*.py"):
        for name in imports(path):
            if name.startswith("garmin_database."):
                assert any(
                    name == "garmin_database." + a
                    or name.startswith("garmin_database." + a + ".")
                    for a in allowed
                ), (path, name)
            elif layer in {"domain", "application"}:
                assert name.partition(".")[0] in sys.stdlib_module_names, (path, name)


def test_mcp_composition_has_no_gui_garmin_or_decoder_dependency(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from garmin_database.bootstrap.mcp import create_service; create_service(); assert not any(n in sys.modules for n in ('PySide6', 'garminconnect', 'fitdecode', 'garmin_fit_sdk'))",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
