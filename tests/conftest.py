import os

import pytest

from tests.support.postgresql import isolated_schema

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_postgresql(request, monkeypatch, tmp_path):
    """Real PostgreSQL, unique schema per test, never the application's database.

    No SQLite fallback or silent skips: full tests require an explicitly selected
    disposable test database, with permission to create/drop schemas.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    needs_database = (
        "source" in request.fixturenames
        and request.node.module.__name__.endswith("test_mcp")
    )
    if not needs_database and not any(
        request.node.get_closest_marker(m) for m in ("integration", "ui")
    ):
        yield
        return
    dsn = os.environ.get("GARMIN_TEST_DATABASE_DSN")
    if not dsn:
        pytest.fail(
            "Ustaw GARMIN_TEST_DATABASE_DSN na osobną bazę PostgreSQL do testów"
        )
    with isolated_schema(dsn) as scoped:
        monkeypatch.setenv("GARMIN_DATABASE_DSN", scoped)
        yield
