from datetime import date, datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.application.errors import DownloadFailed
from garmin_database.bootstrap.dependencies import Services, create_sync
from tests.support.fixtures import fit_bytes, zip_bytes

pytestmark = pytest.mark.integration


def test_current_day_retries_each_cycle_without_refresh_all_and_deduplicates(tmp_path):
    services = Services(Settings(data_dir=str(tmp_path)))
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("Europe/Warsaw")).date()
    previous = day - timedelta(days=1)
    with services.db.writer_lock(), services.db.connect() as conn:
        conn.execute(
            "INSERT INTO import_days(day,download_status,attempts,checked_at,http_status) "
            "VALUES(%s,'not_found_unverified',1,%s,404)",
            (previous.isoformat(), now.isoformat()),
        )
    calls = []

    def download(requested):
        calls.append(requested)
        if len(calls) <= 2:
            raise DownloadFailed(404)
        return zip_bytes()

    source = SimpleNamespace(download_health_snapshot=download)
    for expected in ("missing", "missing", "imported", "imported"):
        sync = create_sync(services.db, source, delay=0)
        sync.clock = lambda: now
        summary = sync.run_summary(previous, day, Event())
        assert not sync.refresh_all
        assert summary.error_count == 0
        assert summary.successful_days == (expected == "imported")
        assert summary.unresolved_days == (2 if expected == "missing" else 1)
    assert calls == [day.isoformat()] * 4
    with services.db.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM fit_files").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM decode_runs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM fit_messages").fetchone()[0] == 2
        assert (
            conn.execute(
                "SELECT attempts FROM import_days WHERE day=%s", (previous.isoformat(),)
            ).fetchone()[0]
            == 1
        )
        current = conn.execute(
            "SELECT download_status,attempts,http_status,error_type FROM import_days WHERE day=%s",
            (day.isoformat(),),
        ).fetchone()
        assert tuple(current) == ("downloaded", 4, None, None)


def test_current_day_with_recent_404_is_prefetched_after_previous_day(tmp_path):
    services = Services(Settings(data_dir=str(tmp_path)))
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("Europe/Warsaw")).date()
    previous = day - timedelta(days=1)
    with services.db.writer_lock(), services.db.connect() as conn:
        conn.execute(
            "INSERT INTO import_days(day,download_status,attempts,checked_at,http_status) "
            "VALUES(%s,'not_found_unverified',1,%s,404)",
            (day.isoformat(), now.isoformat()),
        )
    calls = []

    def download(requested):
        calls.append(requested)
        return zip_bytes()

    sync = create_sync(
        services.db, SimpleNamespace(download_health_snapshot=download), delay=0
    )
    sync.clock = lambda: now
    summary = sync.run_summary(previous, day, Event())
    assert summary.successful_days == 2 and summary.issue_count == 0
    assert calls == [previous.isoformat(), day.isoformat()]
    assert not (tmp_path / "raw").exists()


@pytest.mark.parametrize("status", [404, 500])
def test_successful_download_replaces_previous_error_metadata(tmp_path, status):
    services = Services(Settings(data_dir=str(tmp_path)))
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    day = date(2024, 6, 19)
    with services.db.writer_lock(), services.db.connect() as conn:
        conn.execute(
            "INSERT INTO import_days(day,download_status,attempts,checked_at,http_status,error_type) VALUES(%s,%s,3,%s,%s,'RuntimeError')",
            (
                str(day),
                "not_found_unverified" if status == 404 else "failed",
                old,
                status,
            ),
        )
    services.source_factory = lambda: SimpleNamespace(
        download_health_snapshot=lambda day: zip_bytes()
    )
    result = services.sync(
        day, day, Event(), lambda *args: None, delay=0, detailed=True
    )
    assert result.successful_days == 1 and result.issue_count == 0
    with services.db.connect(readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM import_days WHERE day=%s", (str(day),)
        ).fetchone()
        assert row["download_status"] == "downloaded"
        assert row["http_status"] is None and row["error_type"] is None
        assert datetime.fromisoformat(row["checked_at"]) > datetime.fromisoformat(old)
        assert row["attempts"] == 4


def test_delayed_snapshot_is_recovered_without_duplicate_fits(tmp_path):
    services = Services(Settings(data_dir=str(tmp_path)))
    calls = []

    def download(day):
        calls.append(day)
        if len(calls) == 1:
            error = DownloadFailed(404, None)
            raise error
        return zip_bytes()

    sync = create_sync(
        services.db, SimpleNamespace(download_health_snapshot=download), delay=0
    )
    day = date(2024, 6, 19)
    assert sync.run_summary(day, day, Event()).unresolved_days == 1
    assert sync.run_summary(day, day, Event()).unresolved_days == 1
    assert len(calls) == 1
    sync.clock = lambda: datetime.now(timezone.utc) + timedelta(hours=25)
    result = sync.run_summary(day, day, Event())
    assert result.successful_days == 1 and result.issue_count == 0
    assert len(calls) == 2
    assert sync.archives.payloads == {}
    assert not (tmp_path / "raw").exists()
    assert sync.run_summary(day, day, Event()).successful_days == 1
    with services.db.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM fit_files").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM fit_messages").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM fit_fields").fetchone()[0] == 8
        assert (
            conn.execute("SELECT download_status FROM import_days").fetchone()[0]
            == "downloaded"
        )


def test_summary_matches_real_database_with_404_crc_failure_and_successful_last_day(
    tmp_path,
):
    services = Services(Settings(data_dir=str(tmp_path)))
    bad = fit_bytes()
    bad = bad[:-1] + bytes([bad[-1] ^ 1])

    def download(day):
        if day == "2024-06-19":
            error = DownloadFailed(404, None)
            raise error
        return zip_bytes(bad if day == "2024-06-20" else fit_bytes())

    services.source_factory = lambda: SimpleNamespace(download_health_snapshot=download)
    events = []
    result = services.sync(
        date(2024, 6, 19),
        date(2024, 6, 21),
        Event(),
        lambda *a: events.append(a),
        delay=0,
        detailed=True,
    )
    assert result.processed_days == result.requested_days == 3
    assert result.successful_days == result.unresolved_days == result.import_errors == 1
    assert (
        result.download_errors == result.archive_errors == 0 and result.issue_count == 2
    )
    assert (
        result.last_day == "2024-06-21"
        and result.last_day_result == "import zakończony bez błędów"
    )
    assert events[-1][1] == "Wynik dnia: import zakończony bez błędów"
    assert all("private" not in event[1] for event in events)
    with services.db.connect(readonly=True) as conn:
        assert (
            conn.execute(
                "SELECT download_status FROM import_days WHERE day='2024-06-19'"
            ).fetchone()[0]
            == "not_found_unverified"
        )
        assert dict(
            conn.execute("SELECT status,count(*) FROM file_decodes GROUP BY status")
        ) == {"failed": 1, "complete": 1}
