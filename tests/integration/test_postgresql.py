"""PostgreSQL guarantees are tested against the real server, without SQLite."""

import os
from hashlib import sha256
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.adapters.outbound.postgres.queries import Queries
from garmin_database.bootstrap.cli import main
from tests.support.fixtures import archive


@pytest.mark.unit
@pytest.mark.parametrize(
    "dsn",
    [
        "password=private-secret dbname=garmin",
        "postgresql://garmin:private-secret@localhost/garmin",
        "invalid-dsn",
        None,
        42,
    ],
)
def test_connection_settings_reject_invalid_or_plaintext_passwords(tmp_path, dsn):
    settings = Settings(database_dsn=dsn)
    path = tmp_path / "settings.json"
    with pytest.raises(ValueError) as error:
        settings.save(path)
    assert "private-secret" not in str(error.value)
    assert not path.exists()


@pytest.mark.unit
def test_connection_settings_roundtrip_without_secret(tmp_path):
    settings = Settings(
        database_dsn="host=localhost port=5432 dbname=garmin user=garmin sslmode=verify-full"
    )
    path = tmp_path / "settings.json"
    settings.save(path)
    assert Settings.load(path).database_dsn == settings.database_dsn


@pytest.mark.integration
def test_readonly_snapshot_cannot_write_and_closes(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with db.connect(readonly=True) as reader:
        assert (
            reader.execute("SHOW transaction_isolation").fetchone()[0]
            == "repeatable read"
        )
        assert reader.execute("SHOW transaction_read_only").fetchone()[0] == "on"
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            reader.execute("DELETE FROM import_days")
        reader.rollback()
    assert reader.closed
    with db.connect() as writer:
        writer.execute(
            "INSERT INTO import_days VALUES('2024-01-01','empty_zip',0,NULL,NULL,NULL,NULL)"
        )
    assert writer.closed
    assert db.status()["days"] == {"empty_zip": 1}


@pytest.mark.integration
def test_transaction_failure_rolls_back_all_rows(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with pytest.raises(psycopg.IntegrityError):
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO import_days(day,download_status) VALUES('2024-01-01','empty_zip')"
            )
            conn.execute(
                "INSERT INTO archives(day,relative_path,sha256,size_bytes,acquisition_origin) VALUES('2024-01-02','missing','a',0,'webapi')"
            )
    assert conn.closed
    assert db.status()["days"] == {}


@pytest.mark.integration
def test_advisory_lock_protects_same_database_with_different_data_directories(tmp_path):
    first = Database(tmp_path / "first")
    second = Database(tmp_path / "second")
    first.initialize()
    with first.writer_lock():
        with first.writer_lock():
            assert first.status()["archives"] == 0
        with pytest.raises(RuntimeError, match="Inny proces"):
            with second.writer_lock():
                pytest.fail("second writer must be refused")
        with pytest.raises(RuntimeError):
            second.initialize()
        with pytest.raises(RuntimeError):
            Importer(second).archive(archive(second.root))
    with second.writer_lock():
        pass


@pytest.mark.integration
def test_lock_is_released_after_exception(tmp_path):
    first = Database(tmp_path / "first")
    with pytest.raises(ValueError):
        with first.writer_lock():
            raise ValueError("synthetic interruption")
    with Database(tmp_path / "other").writer_lock():
        pass


@pytest.mark.integration
def test_schema_migrations_are_atomic_and_retryable(tmp_path, monkeypatch):
    db = Database(tmp_path)
    original = Path.read_text

    def broken_sql(path, *args, **kwargs):
        source = original(path, *args, **kwargs)
        return (
            source + "\nSELECT definitely_missing_column;"
            if path.name == "003_summaries.sql"
            else source
        )

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", broken_sql)
        with pytest.raises(psycopg.errors.UndefinedColumn):
            db.initialize()
    with db.connect(readonly=True) as conn:
        assert (
            conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0]
            is None
        )
    db.initialize()
    assert db.status()["fields"] == 0


@pytest.mark.integration
def test_schema_checksum_tampering_is_refused(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            "UPDATE schema_migrations SET sql_sha256=%s WHERE version=1", ("0" * 64,)
        )
    with pytest.raises(ValueError, match="suma kontrolna"):
        db.initialize()


@pytest.mark.unit
@pytest.mark.parametrize(
    "name", ["001_initial.sql", "002_query_indexes.sql", "003_summaries.sql"]
)
def test_packaged_schema_exactly_matches_source(name):
    root = Path(__file__).resolve().parents[2]
    assert (root / "schema" / name).read_bytes() == (
        root / "src/garmin_database/resources" / name
    ).read_bytes()


@pytest.mark.integration
def test_schema_migration_checksums_are_recorded(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with db.connect(readonly=True) as conn:
        records = conn.execute(
            "SELECT version,sql_sha256 FROM schema_migrations ORDER BY version"
        ).fetchall()
    root = Path(__file__).resolve().parents[2]
    for (version, digest), name in zip(
        records,
        ("001_initial.sql", "002_query_indexes.sql", "003_summaries.sql"),
        strict=True,
    ):
        assert (
            digest
            == sha256(
                (root / "schema" / name).read_text(encoding="utf-8").encode()
            ).hexdigest()
        )


@pytest.mark.integration
def test_missing_database_never_falls_back_to_sqlite(tmp_path, monkeypatch, capsys):
    dsn = make_conninfo(
        os.environ["GARMIN_DATABASE_DSN"],
        dbname="garmin_missing_database_for_test",
        password="private-test-secret",
    )
    monkeypatch.setenv("GARMIN_DATABASE_DSN", dsn)
    monkeypatch.setattr(Settings, "load", lambda *a: Settings(data_dir=str(tmp_path)))
    assert main(["status"]) == 1
    output = capsys.readouterr().out
    assert "OperationalError" in output and "private-test-secret" not in output
    assert not list(tmp_path.glob("*.sqlite*"))


@pytest.mark.integration
def test_bigint_precision_and_postgresql_catalog(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO fit_files(id,sha256,size_bytes,integrity_status) VALUES(%s,%s,%s,'valid')",
            (2**40, "a" * 64, 2**40),
        )
    with db.connect(readonly=True) as conn:
        assert conn.execute("SELECT id,size_bytes FROM fit_files").fetchone() == (
            2**40,
            2**40,
        )
        assert (
            conn.execute(
                "SELECT data_type FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='fit_messages' AND column_name='time_unix_ms'"
            ).fetchone()[0]
            == "bigint"
        )


@pytest.mark.integration
def test_query_uses_server_cursor_and_closes_on_early_exit(tmp_path):
    from datetime import date

    db = Database(tmp_path)
    db.initialize()
    Importer(db).archive(archive(tmp_path))
    parameter = Queries(db).parameters()[0]
    with db.connect(readonly=True) as conn:
        rows = Queries(db).rows(parameter, date(2024, 1, 1), date(2025, 1, 1), conn)
        assert next(rows)["value"] == 62
        assert (
            conn.execute(
                "SELECT count(*) FROM pg_cursors WHERE name LIKE 'garmin_series_%'"
            ).fetchone()[0]
            == 1
        )
        rows.close()
        assert (
            conn.execute(
                "SELECT count(*) FROM pg_cursors WHERE name LIKE 'garmin_series_%'"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.integration
@pytest.mark.parametrize("invalid_day", ["2024-02-30", "not-a-date", "2024-2-1"])
def test_invalid_archive_days_are_rejected(tmp_path, invalid_day):
    db = Database(tmp_path)
    db.initialize()
    with pytest.raises(psycopg.Error):
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO import_days(day,download_status) VALUES(%s,'empty_zip')",
                (invalid_day,),
            )
