import os
import threading
from datetime import date
from types import SimpleNamespace

import pytest
from fixtures import archive, fit_bytes

from garmin_database.auth import GarminSource, SessionRequired, SessionStore
from garmin_database.exporter import Exporter
from garmin_database.importer import Importer
from garmin_database.query import Queries
from garmin_database.storage import Database
from garmin_database.sync import Sync, error_status, retry_after
from garmin_database.util import Cancelled, atomic_json


@pytest.mark.unit
@pytest.mark.parametrize(
    "type_name,status",
    [
        ("GarminAuthenticationError", 401),
        ("TooManyRequestsError", 429),
        ("ValueError", None),
    ],
)
def test_safe_error_classification(type_name, status):
    error = type(type_name, (Exception,), {})("sensitive body")
    assert error_status(error) == status


@pytest.mark.integration
def test_indexes_migration_and_crash_marker(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with db.connect() as c:
        profile = c.execute(
            "INSERT INTO decoder_profiles(parser_name,parser_version,profile_version,options_json) VALUES('test','1','1','{}') RETURNING id"
        ).fetchone()[0]
        c.execute(
            "INSERT INTO decode_runs(profile_id,started_at,status) VALUES(%s,'test','running')",
            (profile,),
        )
    db.initialize()
    with db.connect() as c:
        assert (
            c.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 3
        )
        assert (
            c.execute("SELECT status FROM decode_runs").fetchone()[0] == "interrupted"
        )
        c.execute("SET LOCAL enable_seqscan = off")
        plan = c.execute(
            "EXPLAIN SELECT * FROM fit_fields WHERE field_definition_id=1 AND message_definition_id=1"
        ).fetchall()
        assert any("fields_definition_context" in x[0] for x in plan)


@pytest.mark.integration
def test_future_schema_is_refused(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with db.connect() as c:
        c.execute("INSERT INTO schema_migrations VALUES(99,'test',%s)", ("a" * 64,))
    with pytest.raises(ValueError):
        db.initialize()


@pytest.mark.integration
def test_cancel_rolls_back_reprocessing(tmp_path, monkeypatch):
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path)
    importer = Importer(db)
    importer.archive(path)
    import garmin_database.importer as module

    original = module.check_stop
    calls = 0

    def stop_midway(stop):
        nonlocal calls
        calls += 1
        if calls == 5:
            raise Cancelled()
        original(stop)

    monkeypatch.setattr(module, "check_stop", stop_midway)
    with pytest.raises(Cancelled):
        importer.archive(path, force=True)
    assert db.status()["fields"] == 8
    with db.connect(readonly=True) as c:
        assert c.execute("SELECT status FROM file_decodes").fetchone()[0] == "complete"


@pytest.mark.integration
def test_decode_failure_keeps_previous_result(tmp_path, monkeypatch):
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path)
    importer = Importer(db)
    importer.archive(path)

    def fail(*args):
        raise ValueError("unsafe response text")

    monkeypatch.setattr(importer, "decode", fail)
    assert importer.archive(path, force=True) == 1
    assert db.status()["fields"] == 8


@pytest.mark.integration
def test_local_archive_change_is_refused(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path)
    importer = Importer(db)
    importer.archive(path)
    archive(tmp_path, payload=fit_bytes(values=[(1100000000, 70, 0, 1)]))
    with pytest.raises(ValueError):
        importer.archive(path)
    assert db.status()["fields"] == 8


@pytest.mark.integration
def test_legacy_metadata_recovery(tmp_path):
    atomic_json(
        tmp_path / "collection.json",
        {
            "days": {
                "2024-01-01": {
                    "status": "not_found_unverified",
                    "attempts": 1,
                    "http_status": 404,
                }
            }
        },
    )
    db = Database(tmp_path)
    assert (
        Sync(db).run(
            date(2024, 1, 1), date(2024, 1, 1), threading.Event(), local_only=True
        )
        == 0
    )
    assert db.status()["days"] == {"not_found_unverified": 1}


@pytest.mark.integration
def test_invalid_local_zip_does_not_download(tmp_path):
    path = tmp_path / "raw/2024-01-01.zip"
    path.parent.mkdir()
    path.write_bytes(b"broken")
    db = Database(tmp_path)
    assert (
        Sync(db, None, 0).run(date(2024, 1, 1), date(2024, 1, 1), threading.Event())
        == 1
    )
    assert db.status()["days"] == {"local_invalid": 1}


@pytest.mark.integration
def test_network_retries_are_bounded_and_secret_free(tmp_path):
    class Source:
        calls = 0

        def download_health_snapshot(self, day):
            self.calls += 1
            raise RuntimeError("HTTP 503 private-token")

    class NoSleep:
        def wait(self, duration):
            return False

        def is_set(self):
            return False

    source = Source()
    db = Database(tmp_path)
    assert Sync(db, source, 0).run(date(2024, 1, 1), date(2024, 1, 10), NoSleep()) == 5
    assert source.calls == 15
    with db.connect() as c:
        assert all(
            "private" not in str(dict(x))
            for x in c.execute("SELECT * FROM import_days")
        )


@pytest.mark.integration
def test_untimed_duplicate_uses_source_in_range(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    importer = Importer(db)
    payload = fit_bytes(346, [(6, 1, 2)], [(70,)])
    importer.archive(archive(tmp_path, "2024-06-19", payload))
    importer.archive(archive(tmp_path, "2024-06-20", payload))
    q = Queries(db)
    p = q.parameters()[0]
    rows = list(q.rows(p, date(2024, 6, 20), date(2024, 6, 20)))
    assert (
        len(rows) == 1
        and rows[0]["time"] is None
        and rows[0]["requested_day"] == "2024-06-20"
    )
    chart, _ = q.chart(p, date(2024, 6, 20), date(2024, 6, 20))
    assert chart[0][1] == 70


@pytest.mark.integration
def test_export_cannot_write_into_originals(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    with pytest.raises(ValueError):
        Exporter(db).generate(
            tmp_path / "raw/subfolder", [], date(2024, 1, 1), date(2024, 1, 1)
        )


@pytest.mark.integration
def test_export_coverage_uses_the_same_read_snapshot(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    q = Queries(db)
    day = date(2024, 1, 1)
    with db.connect(readonly=True) as snapshot:
        snapshot.execute("SELECT count(*) FROM import_days").fetchone()
        with db.connect() as writer:
            writer.execute(
                "INSERT INTO import_days(day,download_status) VALUES('2024-01-01','empty_zip')"
            )
        assert q.coverage(day, day, snapshot)["missing_days"] == ["2024-01-01"]
        assert q.coverage(day, day)["missing_days"] == []


@pytest.mark.skipif(
    os.name != "nt", reason="Windows DPAPI integration requires Windows"
)
@pytest.mark.unit
def test_corrupt_encrypted_session_fails(tmp_path):
    store = SessionStore(tmp_path / "session")
    store.path.write_bytes(b"not encrypted")
    with pytest.raises(OSError):
        store.load()


@pytest.mark.unit
@pytest.mark.parametrize(
    "header,expected",
    [
        ("15", 15),
        ("Sun, 11 Oct 2026 12:01:00 GMT", 60),
        ("invalid", 2),
        ("-3", 2),
        (None, 2),
    ],
)
def test_retry_after_header(header, expected):
    from datetime import datetime, timezone

    error = RuntimeError("private response")
    error.response = SimpleNamespace(headers={"Retry-After": header})
    assert (
        retry_after(error, 2, datetime(2026, 10, 11, 12, tzinfo=timezone.utc))
        == expected
    )


@pytest.mark.integration
def test_retry_after_delays_the_next_request(tmp_path):
    from fixtures import zip_bytes

    class Source:
        calls = 0

        def download_health_snapshot(self, day):
            self.calls += 1
            if self.calls == 1:
                error = RuntimeError("private response")
                error.response = SimpleNamespace(
                    status_code=503, headers={"Retry-After": "15"}
                )
                raise error
            return zip_bytes()

    class Clock:
        delays = []

        def wait(self, delay):
            self.delays.append(delay)
            return False

        def is_set(self):
            return False

    clock = Clock()
    db = Database(tmp_path)
    assert Sync(db, Source(), 0).run(date(2024, 1, 1), date(2024, 1, 1), clock) == 0
    assert clock.delays == [0, 15]
    assert db.status()["files"] == 1


@pytest.mark.unit
def test_missing_session_has_actionable_error_without_api_login(tmp_path):
    calls = []
    api = SimpleNamespace(password=None, login=lambda token: calls.append(token))
    source = GarminSource(SessionStore(tmp_path / "missing-session"), lambda **kw: api)
    with pytest.raises(SessionRequired, match="Ustawienia"):
        source.login()
    assert calls == []


@pytest.mark.unit
def test_cancelled_login_does_not_replace_the_previous_session(tmp_path):
    stop = threading.Event()
    store = SessionStore(tmp_path / "session.bin", lambda value, decrypt=False: value)
    store.save("previous-synthetic-session")
    api = SimpleNamespace(
        password="synthetic-password",
        login=lambda token: stop.set(),
        client=SimpleNamespace(dumps=lambda: "new-synthetic-session"),
    )
    source = GarminSource(store, lambda **kwargs: api)
    with pytest.raises(Cancelled):
        source.login("synthetic@example.invalid", "synthetic-password", stop=stop)
    assert store.load() == "previous-synthetic-session"
    assert source.api is None and api.password is None


@pytest.mark.integration
def test_missing_session_is_not_retried_as_network_error(tmp_path):
    class Source:
        calls = 0

        def download_health_snapshot(self, day):
            self.calls += 1
            raise SessionRequired()

    source = Source()
    db = Database(tmp_path)
    progress = []
    assert (
        Sync(db, source, 0).run(
            date(2024, 1, 1),
            date(2024, 1, 2),
            threading.Event(),
            lambda day, stage, i, total: progress.append(stage),
        )
        == 1
    )
    assert source.calls == 1 and "Ustawienia" in progress[-1]
    with db.connect(readonly=True) as c:
        assert c.execute("SELECT attempts FROM import_days").fetchone()[0] == 1


@pytest.mark.integration
def test_reimport_does_not_add_fictitious_decode_history(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    importer = Importer(db)
    path = archive(tmp_path)
    importer.archive(path)
    with db.connect(readonly=True) as c:
        initial = c.execute("SELECT count(*) FROM decode_runs").fetchone()[0]
    importer.archive(path)
    with db.connect(readonly=True) as c:
        assert c.execute("SELECT count(*) FROM decode_runs").fetchone()[0] == initial
    assert db.status()["fields"] == 8
    importer.archive(path, force=True)
    with db.connect(readonly=True) as c:
        assert (
            c.execute("SELECT count(*) FROM decode_runs").fetchone()[0] == initial + 1
        )
    assert db.status()["fields"] == 8
