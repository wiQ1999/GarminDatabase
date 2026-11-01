"""Disposable PostgreSQL schemas shared by tests and packaged smoke checks."""

from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


@contextmanager
def isolated_schema(dsn, prefix="garmin_test_"):
    schema = prefix + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        if admin.info.dbname == "garmin":
            raise ValueError("Wskaż osobną bazę testową, poza bazą aplikacji garmin")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            yield make_conninfo(dsn, options=f"-c search_path={schema}")
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
