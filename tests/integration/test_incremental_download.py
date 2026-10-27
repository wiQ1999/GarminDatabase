import threading
from datetime import date, timedelta
from io import BytesIO
from zipfile import ZipFile

import pytest

from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.application.archive_payload import ArchivePayload
from garmin_database.bootstrap.dependencies import create_sync
from garmin_database.domain.time import dates, today
from tests.support.fixtures import fit_bytes, zip_bytes

pytestmark = pytest.mark.integration


def bundle(items):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, content in items:
            archive.writestr(name, content)
    return stream.getvalue()


def test_network_adds_fit_without_disk_and_without_decoding_unchanged(tmp_path):
    db = Database(tmp_path)
    first = fit_bytes()
    second = fit_bytes(values=[(1100000120, 70, 1, 2)])
    payloads = [
        bundle([("one_WELLNESS.fit", first)]),
        bundle([("two_WELLNESS.fit", second), ("one_WELLNESS.fit", first)]),
        bundle([("one_WELLNESS.fit", first), ("two_WELLNESS.fit", second)]),
    ]

    class Source:
        def download_health_snapshot(self, day):
            return payloads.pop(0)

    source = Source()
    for expected in (1, 2, 2):
        result = create_sync(db, source, 0).run_summary(
            today(), today(), threading.Event()
        )
        assert result.issue_count == 0
        with db.connect(readonly=True) as conn:
            assert (
                conn.execute(
                    "SELECT count(*) FROM file_decodes WHERE is_active=1"
                ).fetchone()[0]
                == expected
            )
            assert (
                conn.execute("SELECT count(*) FROM decode_runs").fetchone()[0]
                == expected
            )
        assert not (tmp_path / "raw").exists()
        assert sync_status(db) == "downloaded"


def test_download_plan_rechecks_last_day_and_failed_earlier_days(tmp_path):
    from garmin_database.adapters.outbound.postgres.import_days import ImportDays

    db = Database(tmp_path)
    db.initialize()
    begin = date(2024, 6, 19)
    importer = Importer(db)
    importer.archive(ArchivePayload(begin.isoformat(), zip_bytes()))
    importer.archive(
        ArchivePayload((begin + timedelta(days=2)).isoformat(), zip_bytes())
    )
    repo = ImportDays(db)
    repo.attempt((begin + timedelta(days=1)).isoformat())
    repo.failed((begin + timedelta(days=1)).isoformat(), 500, "SyntheticError")
    assert repo.download_days(begin, begin + timedelta(days=3)) == list(
        dates(begin + timedelta(days=1), begin + timedelta(days=3))
    )
    assert repo.download_days(begin, begin + timedelta(days=3), True) == list(
        dates(begin, begin + timedelta(days=3))
    )


def test_today_allowed_future_rejected():
    assert list(dates(today(), today())) == [today()]
    with pytest.raises(ValueError):
        list(dates(today(), today() + timedelta(days=1)))


def test_today_remains_partial_even_after_all_received_files_decode(tmp_path):
    from garmin_database.adapters.outbound.postgres.queries import Queries

    db = Database(tmp_path)
    db.initialize()
    Importer(db).archive(ArchivePayload(today().isoformat(), zip_bytes()))
    coverage = Queries(db).coverage(today(), today())
    assert coverage["decode_status"] == "complete"
    assert coverage["unimported_or_partial_days"] == []
    assert coverage["ongoing_days"] == [today().isoformat()]


def test_full_download_retries_unresolved_404(tmp_path):
    from types import SimpleNamespace

    db = Database(tmp_path)

    class Source:
        calls = 0

        def download_health_snapshot(self, day):
            self.calls += 1
            if self.calls == 1:
                error = RuntimeError("synthetic")
                error.response = SimpleNamespace(status_code=404)
                raise error
            return zip_bytes()

    source = Source()
    sync = create_sync(db, source, 0)
    day = date(2024, 6, 19)
    assert sync.run_summary(day, day, threading.Event()).unresolved_days == 1
    assert sync.run_summary(day, day, threading.Event()).unresolved_days == 1
    assert source.calls == 1
    sync.refresh_all = True
    assert sync.run_summary(day, day, threading.Event()).successful_days == 1
    assert source.calls == 2


def test_failed_fit_is_redownloaded_and_memory_released(tmp_path, monkeypatch):
    from types import SimpleNamespace

    db = Database(tmp_path)
    payloads = [zip_bytes(), zip_bytes()]
    source = SimpleNamespace(download_health_snapshot=lambda day: payloads.pop(0))
    sync = create_sync(db, source, 0)
    decode = sync.importer.decode
    calls = []

    def fail_once(*args):
        if not calls:
            calls.append(True)
            raise RuntimeError("synthetic SQL failure")
        return decode(*args)

    monkeypatch.setattr(sync.importer, "decode", fail_once)
    day = date(2024, 6, 19)
    assert sync.run_summary(day, day, threading.Event()).import_errors == 1
    assert not sync.archives.payloads
    assert sync.run_summary(day, day, threading.Event()).successful_days == 1
    assert not sync.archives.payloads
    assert not (tmp_path / "raw").exists()


def sync_status(db):
    with db.connect(readonly=True) as conn:
        return conn.execute(
            "SELECT download_status FROM import_days ORDER BY day DESC LIMIT 1"
        ).fetchone()[0]


def test_unknown_network_failures_stop_after_five_days(tmp_path):
    from types import SimpleNamespace

    calls = []

    def fail(day):
        calls.append(day)
        raise RuntimeError("synthetic connection failure without HTTP status")

    class Stop:
        def wait(self, delay):
            return False

        def is_set(self):
            return False

    db = Database(tmp_path)
    sync = create_sync(db, SimpleNamespace(download_health_snapshot=fail), 0)
    day = date(2024, 6, 19)
    result = sync.run_summary(day, day + timedelta(days=9), Stop())
    assert result.download_errors == 5
    assert result.halted
    assert len(calls) == 15
    assert not sync.archives.payloads
