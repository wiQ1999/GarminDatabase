from datetime import date
from pathlib import Path

import pytest
from fixtures import archive, fit_bytes

from garmin_database.importer import Importer
from garmin_database.query import Queries
from garmin_database.storage import Database
from garmin_database.summaries import (
    MEAN_PARAMETERS,
    Summaries,
    aggregate_days,
    has_chart_summary,
    monthly_summaries,
    summary_method,
)
from garmin_database.util import Cancelled, writer_lock

pytestmark = pytest.mark.unit


def parameter(key="monitoring.heart_rate", enum=None, representation="sample"):
    return dict(key=key, enum=enum or {}, representation=representation)


def row(value, time="2024-11-08T08:00:00+00:00", validity="valid", day="2024-11-08"):
    return dict(value=value, time=time, validity=validity, requested_day=day)


@pytest.mark.parametrize("key", sorted(MEAN_PARAMETERS))
def test_supported_mean_policy(key):
    p = parameter(key)
    assert summary_method(p) == "sample_mean" and has_chart_summary(p)


def test_counters_categories_and_garmin_are_not_averaged():
    assert summary_method(parameter("monitoring.steps")) == "last_observed"
    assert (
        summary_method(parameter("sleep_level.sleep_level", {"1": "light"}))
        == "value_counts"
    )
    assert (
        summary_method(
            parameter(
                "hrv_status_summary.last_night_average", representation="source_summary"
            )
        )
        == "garmin"
    )
    assert not has_chart_summary(parameter("monitoring.steps"))


def test_daily_mean_preserves_invalid_and_excluded_counts_and_time_gaps():
    rows = [
        row(10),
        row(30, "2024-11-08T22:59:00+00:00"),
        row(None, validity="invalid"),
        row(-1),
        row(True),
        row([20, 30]),
        row(float("nan")),
        row(50, time=None),
    ]
    result = aggregate_days(rows, parameter("stress_level.stress_level_value"))[0]
    assert result["mean"] == 20 and result["minimum"] == 10 and result["maximum"] == 30
    assert result["valid_count"] == 2 and result["invalid_count"] == 1
    assert result["excluded_count"] == 4 and result["untimed_count"] == 1
    assert result["day_basis"] == "mixed" and result["last_time"] == rows[1]["time"]


def test_no_valid_samples_does_not_turn_into_zero():
    result = aggregate_days([row(None, validity="decode_error")], parameter())[0]
    assert result["mean"] is None and result["valid_count"] == 0
    assert result["minimum"] is None and result["first_time"] is None


def test_local_midnight_and_dst_use_warsaw_days():
    rows = [
        row(10, "2026-03-28T23:30:00+00:00"),
        row(20, "2026-03-29T21:59:00+00:00"),
        row(30, "2026-03-29T22:00:00+00:00"),
    ]
    result = aggregate_days(rows, parameter())
    assert [r["day"] for r in result] == ["2026-03-29", "2026-03-30"]
    assert [r["mean"] for r in result] == [15, 30]


def test_categories_are_observation_counts_not_durations():
    result = aggregate_days(
        [row(1), row(2), row(1)],
        parameter("sleep_level.sleep_level", {"1": "light", "2": "deep"}),
    )[0]
    assert result["value_counts"] == [[1, 2], [2, 1]]
    assert result["mean"] is None and result["valid_count"] == 3


def test_last_counter_value_uses_time_and_keeps_distinct_same_time_rows():
    result = aggregate_days(
        [
            row(150, "2024-11-08T09:00:00+00:00"),
            row(10),
            row(25, "2024-11-08T09:00:00+00:00"),
        ],
        parameter("monitoring.steps"),
    )[0]
    assert result["last_value"] == 25 and result["valid_count"] == 3
    assert result["mean"] is None


def test_monthly_mean_weights_samples_instead_of_days_and_marks_partial_month():
    days = aggregate_days(
        [row(10)] + [row(30, "2024-11-09T08:00:00+00:00")] * 3, parameter()
    )
    result = list(monthly_summaries(days, date(2024, 11, 8), date(2024, 11, 9)))[0]
    assert result["mean"] == 25 and result["valid_count"] == 4
    assert result["valid_days"] == 2
    assert result["minimum"] == 10 and result["maximum"] == 30
    assert result["period_from"] == "2024-11-08" and result["period_to"] == "2024-11-09"


def test_monthly_category_and_last_value_summaries():
    rows = [row(2), row(1, "2024-11-09T09:00:00+00:00"), row(None, time=None)]
    for p in (parameter("x", {"1": "a"}), parameter("monitoring.steps")):
        days = aggregate_days(rows, p)
        result = list(monthly_summaries(days, date(2024, 11, 1), date(2024, 11, 30)))[0]
        assert result["last_value"] == 1 and result["mean"] is None
        assert result["untimed_count"] == 1 and result["day_basis"] == "mixed"
        if p["enum"]:
            assert result["value_counts"] == [[1, 1], [2, 1]]


def test_untimed_observations_are_not_dated_measurements():
    result = aggregate_days([row(50, time=None)], parameter())[0]
    assert result["day"] == "2024-11-08" and result["day_basis"] == "requested_day"
    assert (
        result["mean"] is None
        and result["valid_count"] == 0
        and result["untimed_count"] == 1
    )
    month = list(monthly_summaries([result], date(2024, 11, 1), date(2024, 11, 30)))[0]
    assert month["mean"] is None and month["valid_days"] == 0


def test_cancelled_aggregation_stops_before_reading_all_rows():
    class Stop:
        def is_set(self):
            return True

    with pytest.raises(Cancelled):
        aggregate_days([row(20)], parameter(), Stop())


@pytest.mark.integration
def test_daily_cache_reuse_reprocessing_invalidation_and_chart(tmp_path, monkeypatch):
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path)
    importer = Importer(db)
    importer.archive(path)
    q = Queries(db)
    p = q.parameters()[0]
    start, end = date(2024, 11, 1), date(2024, 11, 30)
    with db.connect(readonly=True) as c:
        c.execute("BEGIN")
        result = Summaries(db).daily(p, start, end, c)
    assert result[0]["mean"] == 63
    with db.connect(readonly=True) as c:
        assert (
            c.execute("SELECT mean FROM v_current_daily_summaries").fetchone()[0] == 63
        )
    original = Queries.rows
    monkeypatch.setattr(
        Queries, "rows", lambda *a: pytest.fail("cache should avoid source scan")
    )
    with db.connect(readonly=True) as c:
        c.execute("BEGIN")
        assert Summaries(db).daily(p, date(2024, 11, 8), date(2024, 11, 8), c) == result
    importer.archive(path, force=True)
    with db.connect(readonly=True) as c:
        assert (
            c.execute("SELECT count(*) FROM v_current_daily_summaries").fetchone()[0]
            == 0
        )
    monkeypatch.setattr(Queries, "rows", original)
    points, message = q.chart(p, start, end)
    assert points[0][1] == 63 and "obliczone" in message
    assert db.status()["fields"] == 8


@pytest.mark.integration
def test_summary_snapshot_survives_new_import_without_publishing_stale_cache(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    importer = Importer(db)
    importer.archive(archive(tmp_path))
    p = Queries(db).parameters()[0]
    with db.connect(readonly=True) as snapshot:
        snapshot.execute("BEGIN")
        snapshot.execute("SELECT revision FROM dataset_state").fetchone()
        importer.archive(
            archive(
                tmp_path,
                "2024-06-20",
                fit_bytes(values=[(1100000120, 100, 43896, 125)]),
            )
        )
        old = Summaries(db).daily(p, date(2024, 11, 8), date(2024, 11, 8), snapshot)
        assert old[0]["mean"] == 63 and old[0]["valid_count"] == 2
    with db.connect(readonly=True) as c:
        assert c.execute("SELECT count(*) FROM summary_cache").fetchone()[0] == 0


@pytest.mark.integration
def test_busy_writer_does_not_block_readonly_summary(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    Importer(db).archive(archive(tmp_path))
    p = Queries(db).parameters()[0]
    with writer_lock(db.root), db.connect(readonly=True) as c:
        c.execute("BEGIN")
        assert (
            Summaries(db).daily(p, date(2024, 11, 8), date(2024, 11, 8), c)[0]["mean"]
            == 63
        )
        assert c.execute("SELECT count(*) FROM summary_cache").fetchone()[0] == 0


@pytest.mark.integration
def test_cache_publication_cancel_rolls_back_existing_cache(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    Importer(db).archive(archive(tmp_path))
    p = Queries(db).parameters()[0]
    start = end = date(2024, 11, 8)
    with db.connect(readonly=True) as c:
        c.execute("BEGIN")
        original = Summaries(db).daily(p, start, end, c)
        revision = c.execute("SELECT revision FROM dataset_state").fetchone()[0]

    class Stop:
        calls = 0

        def is_set(self):
            self.calls += 1
            return self.calls == 2

    with pytest.raises(Cancelled):
        Summaries(db).publish(p, start, end, revision, original, Stop())
    with db.connect(readonly=True) as c:
        assert c.execute(
            "SELECT mean,valid_count FROM v_current_daily_summaries"
        ).fetchone()[:] == (63, 2)


@pytest.mark.integration
def test_migration_from_version_two_preserves_source_records(tmp_path):
    db = Database(tmp_path)
    root = Path(__file__).resolve().parents[1]
    with db.connect() as c:
        c.executescript((root / "schema/001_initial.sql").read_text())
        c.executescript((root / "schema/002_query_indexes.sql").read_text())
        c.execute(
            "INSERT INTO import_days(day,download_status) VALUES('2024-01-01','empty_zip')"
        )
    db.initialize()
    with db.connect(readonly=True) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 3
        assert c.execute("SELECT count(*) FROM import_days").fetchone()[0] == 1
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    assert (root / "schema/003_summaries.sql").read_bytes() == (
        root / "garmin_database/resources/003_summaries.sql"
    ).read_bytes()
