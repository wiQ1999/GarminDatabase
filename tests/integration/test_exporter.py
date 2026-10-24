import json
import threading
from datetime import date, datetime

import pytest

from garmin_database.adapters.outbound.filesystem.json_export import export_directory
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.adapters.outbound.postgres.queries import Queries, bounds
from garmin_database.bootstrap.dependencies import create_exporter as Exporter
from garmin_database.domain.cancellation import Cancelled
from tests.support.fixtures import archive, fit_bytes

pytestmark = pytest.mark.integration
START, END = date(2024, 1, 1), date(2025, 1, 1)


def setup(root, summary=False):
    db = Database(root)
    db.initialize()
    payload = (
        fit_bytes(211, [(253, 4, 134), (0, 1, 2)], [(1100000000, 50)])
        if summary
        else fit_bytes()
    )
    Importer(db).archive(archive(root, "2024-06-19", payload))
    return db


def read(result, kind, parameter):
    path = result.directory / kind / (parameter["key"] + ".json")
    assert result.files[kind + "/" + parameter["key"] + ".json"] == path.stat().st_size
    return json.loads(path.read_text(encoding="utf-8"))


def test_summary_history_and_per_parameter_details_keep_all_exports(tmp_path):
    db = setup(tmp_path / "data")
    params = Queries(db).parameters()
    heart = next(p for p in params if p["key"].endswith("heart_rate"))
    out = tmp_path / "exports"
    out.mkdir()
    (out / "recent.json").write_text("old export or user file")
    result = Exporter(db).generate(out, params, START, END, recent_days=400)
    history = read(result, "history", heart)
    details = read(result, "details", heart)
    assert history["summary_origin"] == "application"
    assert history["aggregation"]["method"] == "sample_mean"
    assert len(history["data"]) == 1
    row = dict(zip(history["columns"], history["data"][0]))
    assert row["mean"] == 63 and row["minimum"] == 62 and row["maximum"] == 64
    assert row["valid_count"] == 2
    assert [r[1] for r in details["data"]] == [62, 64]
    assert details["representation"] == "sample" and details["kind"] == "details"
    assert not (result.directory / "recent.json").exists()
    original = (result.directory / "history" / (heart["key"] + ".json")).read_bytes()
    second = Exporter(db).generate(out, [heart], START, END, 400)
    assert second.directory != result.directory
    assert (
        result.directory / "history" / (heart["key"] + ".json")
    ).read_bytes() == original
    assert (out / "recent.json").read_text() == "old export or user file"
    assert (
        json.loads((result.directory / "manifest.json").read_text())["status"]
        == "complete"
    )


def test_recent_window_limits_only_details(tmp_path):
    db = setup(tmp_path / "data")
    p = Queries(db).parameters()[0]
    result = Exporter(db).generate(tmp_path / "out", [p], START, END)
    assert read(result, "history", p)["data"]
    details = read(result, "details", p)
    assert details["from"] == "2024-10-04"
    assert len(details["data"]) == 2
    shorter = Exporter(db).generate(tmp_path / "out", [p], START, END, 5)
    assert read(shorter, "details", p)["data"] == []


def test_source_summary_is_preserved_even_when_month_is_selected(tmp_path):
    db = setup(tmp_path / "data", True)
    params = Queries(db).parameters()
    result = Exporter(db).generate(
        tmp_path / "out", params, START, END, 400, summary_period="month"
    )
    for p in params:
        history = read(result, "history", p)
        assert history["representation"] == "source_summary"
        assert history["summary_origin"] == "garmin"
        assert history["data"] == read(result, "details", p)["data"]
        assert "aggregation" not in history


def test_monthly_history_is_compact_and_details_unchanged(tmp_path):
    db = setup(tmp_path / "data")
    p = Queries(db).parameters()[0]
    result = Exporter(db).generate(
        tmp_path / "out", [p], START, END, 400, summary_period="month"
    )
    history = read(result, "history", p)
    row = dict(zip(history["columns"], history["data"][0]))
    assert row["month"] == "2024-11" and row["mean"] == 63
    assert row["valid_days"] == 1 and row["valid_count"] == 2
    assert row["period_from"] == "2024-11-01" and row["period_to"] == "2024-11-30"
    assert len(read(result, "details", p)["data"]) == 2


def test_category_and_counter_histories_keep_their_meaning(tmp_path):
    db = setup(tmp_path / "data")
    importer = Importer(db)
    importer.archive(
        archive(
            db.root,
            "2024-06-20",
            fit_bytes(
                275,
                [(253, 4, 134), (0, 1, 2)],
                [(1100000000, 1), (1100000060, 2), (1100000120, 1)],
            ),
        )
    )
    importer.archive(
        archive(
            db.root,
            "2024-06-21",
            fit_bytes(
                55, [(253, 4, 134), (2, 4, 134)], [(1100000000, 100), (1100000060, 250)]
            ),
        )
    )
    params = Queries(db).parameters()
    result = Exporter(db).generate(tmp_path / "out", params, START, END, 400)
    for p in params:
        history = read(result, "history", p)
        data = dict(zip(history["columns"], history["data"][0]))
        if p["key"] == "sleep_level.sleep_level":
            assert "mean" not in history["columns"]
            assert data["value_counts"] == [[1, 2], [2, 1]]
            assert (
                history["value_labels"] and len(read(result, "details", p)["data"]) == 3
            )
        elif p["key"] == "monitoring.distance":
            assert "mean" not in history["columns"] and data["last_value"] == 2.5
            assert data["valid_count"] == 2


@pytest.mark.parametrize(
    "exception,status", [(Cancelled, "cancelled"), (ValueError, "failed")]
)
def test_partial_export_marks_status_and_removes_incomplete_file(
    tmp_path, monkeypatch, exception, status
):
    db = setup(tmp_path / "data")
    params = Queries(db).parameters()
    e = Exporter(db)

    def fail(stream, *args):
        stream.write('{"incomplete":')
        raise exception()

    monkeypatch.setattr(e.sink, "series", fail)
    with pytest.raises(exception):
        e.generate(tmp_path / "out", params, START, END, 400)
    directory = next((tmp_path / "out").iterdir())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == status and len(manifest["files"]) == 1
    assert not list(directory.rglob("*.tmp"))
    assert not list((directory / "details").glob("*.json"))
    assert list((directory / "history").glob("*.json"))


def test_cancellation_before_export_creates_no_folder(tmp_path):
    db = setup(tmp_path / "data")
    stop = threading.Event()
    stop.set()
    with pytest.raises(Cancelled):
        Exporter(db).generate(
            tmp_path / "out", Queries(db).parameters(), START, END, stop=stop
        )
    assert not (tmp_path / "out").exists()


def test_export_data_and_coverage_share_snapshot_during_new_import(tmp_path):
    db = setup(tmp_path / "data")
    p = Queries(db).parameters()[0]
    writes = []

    def progress(key, stage, index, total):
        if stage == "szczegóły":
            Importer(db).archive(
                archive(
                    db.root,
                    "2024-11-08",
                    fit_bytes(values=[(1100000120, 100, 43896, 125)]),
                )
            )
            writes.append(True)

    result = Exporter(db).generate(
        tmp_path / "out", [p], START, END, 400, progress=progress
    )
    history = read(result, "history", p)
    details = read(result, "details", p)
    assert writes and [r[1] for r in details["data"]] == [62, 64]
    assert (
        "2024-11-08" in history["missing_days"]
        and "2024-11-08" in details["missing_days"]
    )
    assert "2024-11-08" not in Queries(db).coverage(START, END)["missing_days"]


@pytest.mark.parametrize("period,params", [("year", True), ("day", False)])
def test_invalid_export_does_not_create_package(tmp_path, period, params):
    db = setup(tmp_path / "data")
    with pytest.raises(ValueError):
        Exporter(db).generate(
            tmp_path / "out",
            Queries(db).parameters() if params else [],
            START,
            END,
            summary_period=period,
        )
    assert not (tmp_path / "out").exists()


@pytest.mark.unit
def test_directory_collision_does_not_reuse_old_folder(tmp_path):
    now = datetime(2026, 10, 11, 12, 13, 14, 123456)
    one = export_directory(tmp_path, now)
    two = export_directory(tmp_path, now)
    assert one.name == "GarminDatabase_2026-10-11_12-13-14_123456"
    assert two.name == one.name + "_01"


@pytest.mark.unit
def test_dst_day_bounds():
    a, b = bounds(date(2026, 3, 29), date(2026, 3, 29))
    assert b - a == 23 * 3600 * 1000
    a, b = bounds(date(2026, 10, 25), date(2026, 10, 25))
    assert b - a == 25 * 3600 * 1000
