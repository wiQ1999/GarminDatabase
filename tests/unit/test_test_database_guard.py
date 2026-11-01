from unittest.mock import MagicMock

import pytest

from tests.support import postgresql


def test_test_helper_rejects_application_database_before_any_ddl(monkeypatch):
    connection = MagicMock()
    connection.info.dbname = "garmin"
    connection.__enter__.return_value = connection
    monkeypatch.setattr(postgresql.psycopg, "connect", lambda *a, **k: connection)
    with pytest.raises(ValueError, match="osobną bazę"):
        with postgresql.isolated_schema("synthetic"):
            pytest.fail("Application database must not be used")
    connection.execute.assert_not_called()
