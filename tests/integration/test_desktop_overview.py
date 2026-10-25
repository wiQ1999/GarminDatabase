import threading
import time

import pytest

from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.application.ports import ReadFailure
from garmin_database.bootstrap import dependencies
from garmin_database.bootstrap.dependencies import Services
from garmin_database.domain.cancellation import DeadlineStop
from tests.support.fixtures import archive, fit_bytes

pytestmark = pytest.mark.integration


def services(tmp_path):
    result = Services(Settings(data_dir=str(tmp_path / "data")))
    Importer(result.db).archive(archive(result.db.root))
    return result


def test_overview_catalog_and_status_share_snapshot_during_import(
    tmp_path, monkeypatch
):
    source = services(tmp_path)
    original = source.db.status
    published = False

    def status(conn):
        nonlocal published
        assert (
            conn.execute("SHOW transaction_isolation").fetchone()[0]
            == "repeatable read"
        )
        assert conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"
        result = original(conn)
        if not published:
            published = True
            Importer(source.db).archive(
                archive(
                    source.db.root,
                    "2024-11-09",
                    fit_bytes(55, [(253, 4, 134), (2, 4, 134)], [(1100000000, 70)]),
                )
            )
        return result

    monkeypatch.setattr(source.db, "status", status)
    before = source.overview(threading.Event())
    after = source.overview(threading.Event(), before["revision"])
    assert before["status"]["archives"] == 1 and after["status"]["archives"] == 2
    assert after["revision"] > before["revision"]
    assert len(after["parameters"]) > len(before["parameters"])


def test_overview_skips_unchanged_or_not_due_catalog(tmp_path, monkeypatch):
    source = services(tmp_path)
    initial = source.overview(threading.Event())

    def unexpected(*args):
        raise AssertionError("An unchanged catalog must not be queried")

    monkeypatch.setattr(source.queries, "parameters", unexpected)
    same = source.overview(threading.Event(), initial["revision"])
    not_due = source.overview(threading.Event(), None, False)
    assert same["parameters"] is None and not_due["parameters"] is None
    assert same["status"]["fields"] == 8 and not_due["status"]["fields"] == 8


@pytest.mark.parametrize("operation", ["overview_deadline", "chart_cancel"])
def test_read_budget_cancels_active_postgresql_query(tmp_path, monkeypatch, operation):
    source = services(tmp_path)
    stop = threading.Event()

    def slow_status(conn):
        conn.execute("SELECT pg_sleep(20)")

    def slow_chart(parameter, start, end, conn, stop):
        conn.execute("SELECT pg_sleep(20)")

    if operation == "overview_deadline":
        monkeypatch.setattr(
            dependencies,
            "DeadlineStop",
            lambda event, seconds: DeadlineStop(event, 0.1),
        )
        monkeypatch.setattr(source.db, "status", slow_status)

        def action():
            return source.overview(stop)

        timer = None
    else:
        monkeypatch.setattr(source.queries, "chart", slow_chart)

        def action():
            return source.chart({}, None, None, stop)

        timer = threading.Timer(0.1, stop.set)
        timer.start()
    try:
        started = time.monotonic()
        with pytest.raises(ReadFailure, match="Nie można odczytać bazy"):
            action()
        assert time.monotonic() - started < 2
    finally:
        if timer:
            timer.join()
    with source.db.connect(readonly=True) as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
