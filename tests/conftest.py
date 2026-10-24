import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

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
    schema = "garmin_test_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        monkeypatch.setenv(
            "GARMIN_DATABASE_DSN",
            make_conninfo(dsn, options=f"-c search_path={schema}"),
        )
        try:
            yield
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
