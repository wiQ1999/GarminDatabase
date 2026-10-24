"""Synthetic data only: shared policy, consistency, pagination and real stdio."""

import json
import os
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from garmin_database.adapters.inbound.mcp.client_config import client_config
from garmin_database.adapters.inbound.mcp.server import call, tool_definitions
from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.adapters.outbound.postgres.queries import Queries
from garmin_database.adapters.outbound.postgres.summaries import Summaries
from garmin_database.application.read_models import DAILY_COLUMNS
from garmin_database.application.use_cases.read_health import (
    MAX_BYTES,
    AccessError,
    compress_days,
)
from garmin_database.bootstrap.dependencies import create_exporter as Exporter
from garmin_database.bootstrap.mcp import create_service
from tests.support.fixtures import archive, fit_bytes

pytestmark = pytest.mark.unit
KEY = "monitoring.heart_rate"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def source(tmp_path):
    db = Database(tmp_path / "data")
    db.initialize()
    Importer(db).archive(archive(db.root))
    catalog = Queries(db).parameters()
    settings = Settings(
        data_dir=str(db.root),
        settings_version=2,
        export_parameters=[p["key"] for p in catalog],
        parameters=[p["key"] for p in catalog],
        mcp_parameters=[KEY],
        mcp_enabled=True,
    )
    path = tmp_path / "settings.json"
    settings.save(path)
    return db, settings, path, create_service(path)


def unpack(payload, index=0):
    table = payload["series"][index]
    return [dict(zip(table["columns"], row)) for row in table["data"]]


def test_migrate_legacy_and_preserve_explicit_empty():
    settings = Settings()
    assert settings.migrate([dict(key=KEY)])
    assert settings.export_parameters == [KEY]
    assert not settings.mcp_enabled and settings.mcp_parameters == []
    settings.export_parameters = []
    assert not settings.migrate([dict(key="new")])
    assert settings.export_parameters == []
    legacy = Settings(parameters=[KEY])
    legacy.migrate([dict(key="new")])
    assert legacy.export_parameters == [KEY]


@pytest.mark.parametrize(
    "updates",
    [
        dict(settings_version=3),
        dict(settings_version=True),
        dict(mcp_enabled=1),
        dict(mcp_parameters=[KEY, KEY]),
        dict(mcp_parameters="all"),
        dict(settings_version=2, export_parameters=None),
        dict(export_parameters=[1]),
    ],
)
def test_invalid_policy(updates):
    with pytest.raises(ValueError):
        Settings(**updates).validate()


@pytest.mark.integration
def test_catalog_only_enabled_metrics_and_revision_cache(source):
    db, settings, path, service = source
    result = service.catalog()
    assert [r["parameter"] for r in result["metrics"]] == [KEY]
    assert result["metrics"][0]["from"] == "2024-11-08"
    assert result["metrics"][0]["operations"] == ["get_daily", "get_period_stats"]
    assert service.catalog() == result
    settings.mcp_parameters = []
    settings.save(path)
    assert service.catalog()["metrics"] == []


@pytest.mark.integration
@pytest.mark.parametrize(
    "contents", ["{}", "{bad", '{"settings_version":99}', '{"mcp_enabled":true}']
)
def test_disabled_or_invalid_settings_fail_closed(source, contents):
    db, settings, path, service = source
    path.write_text(contents)
    with pytest.raises(AccessError):
        service.catalog()


@pytest.mark.integration
def test_daily_period_and_export_share_weighting_and_time(source, tmp_path):
    db, settings, path, service = source
    # Nov 9 has one sample versus two on Nov 8: (62+64+90)/3=72.
    Importer(db).archive(
        archive(
            db.root,
            "2024-11-09",
            fit_bytes(55, [(253, 4, 134), (27, 1, 2)], [(1100086400, 90)]),
        )
    )
    period = service.period("2024-11-01", "2024-11-30", [KEY])
    row = unpack(period)[0]
    assert row["mean"] == 72 and row["valid_count"] == 3
    assert row["valid_days"] == 2 and row["requested_days"] == 30
    assert row["minimum"] == 62 and row["maximum"] == 90
    daily = service.daily("2024-11-08", "2024-11-09", [KEY])
    assert [r["mean"] for r in unpack(daily)] == [63, 90]
    assert unpack(daily)[0]["first_time"].endswith("+01:00")
    p = next(p for p in Queries(db).parameters() if p["key"] == KEY)
    result = Exporter(db, settings, path).generate(
        tmp_path / "out",
        [p],
        date(2024, 11, 1),
        date(2024, 11, 30),
        summary_period="month",
    )
    exported = json.loads((result.directory / "history" / (KEY + ".json")).read_text())
    erow = dict(zip(exported["columns"], exported["data"][0]))
    assert erow["mean"] == row["mean"]
    assert exported["timestamp_timezone"] == "UTC"
    assert exported["calendar_timezone"] == "Europe/Warsaw"
    assert erow["first_time"].endswith("+00:00")


@pytest.mark.integration
def test_mcp_never_opens_writer_even_on_cold_cache(source, monkeypatch):
    db, settings, path, service = source
    original = Database.connect

    def readonly(self, readonly=False):
        assert readonly, "MCP attempted to write"
        return original(self, readonly=True)

    monkeypatch.setattr(Database, "connect", readonly)
    service.catalog()
    service.daily("2024-11-08", "2024-11-08", [KEY])
    service.period("2024-01-01", "2025-12-31", [KEY])
    with db.connect(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM summary_cache").fetchone()[0] == 0


@pytest.mark.integration
def test_daily_pagination_traverses_empty_days_without_loss(source):
    service = source[3]
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    cursor, seen, values = None, [], []
    while True:
        result = service.daily(str(start), str(end), [KEY], cursor)
        a, b = date.fromisoformat(result["from"]), date.fromisoformat(result["to"])
        seen.extend(a + timedelta(days=n) for n in range((b - a).days + 1))
        values.extend(unpack(result))
        assert service.fits(result)
        if not result["truncated"]:
            assert result["next_cursor"] is None
            break
        assert result["next_cursor"] != cursor
        cursor = result["next_cursor"]
    assert seen == [start + timedelta(days=n) for n in range((end - start).days + 1)]
    assert len(values) == 1 and values[0]["mean"] == 63


@pytest.mark.integration
def test_byte_budget_shrinks_day_pages(source):
    db = source[0]
    Importer(db).archive(
        archive(
            db.root,
            "2024-11-10",
            fit_bytes(
                55,
                [(253, 4, 134), (27, 1, 2)],
                [(1100000000 + i * 86400, 70) for i in range(50)],
            ),
        )
    )
    path = source[2]
    service = create_service(path, max_bytes=2500)
    result = service.daily("2024-11-01", "2024-12-31", [KEY])
    assert service.fits(result)
    assert result["truncated"]
    with pytest.raises(AccessError, match="limit"):
        create_service(path, max_bytes=600).daily("2024-11-08", "2024-11-08", [KEY])


@pytest.mark.integration
@pytest.mark.parametrize("metrics", [[], [KEY, KEY], ["unknown"], "all", [KEY] * 6])
def test_explicit_metrics_and_no_bypass(source, metrics):
    with pytest.raises(ValueError):
        source[3].daily("2024-11-08", "2024-11-08", metrics)


@pytest.mark.integration
@pytest.mark.parametrize(
    "begin,end",
    [
        ("bad", "2024-01-01"),
        ("2024-02-31", "2024-03-01"),
        ("2024-02-02", "2024-01-01"),
        ("9999-01-01", "9999-01-02"),
    ],
)
def test_invalid_ranges(source, begin, end):
    with pytest.raises(AccessError):
        source[3].period(begin, end, [KEY])


@pytest.mark.integration
def test_empty_period_is_null_not_zero(source):
    result = source[3].period("2024-01-01", "2024-02-29", [KEY])
    row = unpack(result)[0]
    assert row["mean"] is None and row["first_time"] is None
    assert row["valid_days"] == 0 and row["requested_days"] == 60
    assert result["gaps_format"] == "day_counts"


@pytest.mark.integration
@pytest.mark.parametrize(
    "change", ["metrics", "db", "connection", "enabled", "revision", "query", "forged"]
)
def test_cursors_are_bound_to_query_revision_and_policy(source, change):
    db, settings, path, service = source
    cursor = service.daily("2024-01-01", "2024-12-31", [KEY])["next_cursor"]
    end = "2024-12-31"
    if change == "metrics":
        settings.mcp_parameters = []
    elif change == "db":
        settings.data_dir = str(db.root / "other")
    elif change == "connection":
        settings.database_dsn = "dbname=garmin_missing_mcp_test"
    elif change == "enabled":
        settings.mcp_enabled = False
    elif change == "revision":
        Importer(db).archive(
            archive(
                db.root, "2024-11-09", fit_bytes(values=[(1100086400, 80, 43776, 123)])
            )
        )
    elif change == "query":
        end = "2024-12-30"
    else:
        cursor = "corrupt" + cursor
    settings.save(path)
    with pytest.raises(ValueError):
        service.daily("2024-01-01", end, [KEY], cursor)


@pytest.mark.integration
def test_policy_revocation_during_request_prevents_publication(source, monkeypatch):
    db, settings, path, service = source
    original = Summaries.daily

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        settings.mcp_enabled = False
        settings.save(path)
        return result

    monkeypatch.setattr(Summaries, "daily", revoke)
    with pytest.raises(AccessError):
        service.daily("2024-11-08", "2024-11-08", [KEY])


@pytest.mark.integration
def test_period_retains_snapshot_during_import(source, monkeypatch):
    db, settings, path, service = source
    original = Summaries.daily
    wrote = []

    def concurrent(*args, **kwargs):
        result = original(*args, **kwargs)
        if not wrote:
            Importer(db).archive(
                archive(
                    db.root,
                    "2024-11-09",
                    fit_bytes(values=[(1100086400, 90, 43776, 123)]),
                )
            )
            wrote.append(True)
        return result

    monkeypatch.setattr(Summaries, "daily", concurrent)
    row = unpack(service.period("2024-01-01", "2024-12-31", [KEY]))[0]
    assert row["mean"] == 63 and row["valid_count"] == 2


@pytest.mark.integration
def test_timeout_cancellation_and_missing_database(source):
    db, settings, path, service = source
    stop = threading.Event()
    stop.set()
    with pytest.raises(AccessError):
        service.period("2024-11-08", "2024-11-08", [KEY], stop)
    with pytest.raises(AccessError):
        create_service(path, seconds=-1).catalog()
    settings.database_dsn = "dbname=garmin_missing_mcp_test"
    settings.data_dir = str(db.root / "absent")
    settings.save(path)
    with pytest.raises(AccessError):
        service.catalog()
    assert not Path(settings.data_dir).exists()


@pytest.mark.integration
def test_wrong_schema_does_not_migrate(source):
    db, settings, path, service = source
    with db.connect() as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version=3")
    with pytest.raises(ValueError, match="bazę"):
        service.catalog()
    with db.connect(readonly=True) as conn:
        assert (
            conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
            == 2
        )


@pytest.mark.integration
def test_export_policy_is_enforced_for_direct_call(source, tmp_path):
    db, settings, path, service = source
    settings.export_parameters = []
    params = Queries(db).parameters()
    with pytest.raises(ValueError, match="wyłączony"):
        Exporter(db, settings, path).generate(
            tmp_path / "out", params, date(2024, 11, 8), date(2024, 11, 8)
        )
    assert not (tmp_path / "out").exists()


@pytest.mark.integration
def test_cli_respects_export_allowlist(source, tmp_path, capsys):
    from garmin_database.bootstrap.cli import main

    db, settings, path, service = source
    settings.export_parameters = [KEY]
    settings.save(path)
    args = [
        "export",
        "--settings-file",
        str(path),
        "--output",
        str(tmp_path / "out"),
        "--from",
        "2024-11-08",
        "--to",
        "2024-11-08",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert len(payload["files"]) == 2
    assert main(args + ["--parameters", "monitoring.distance"]) == 1


@pytest.mark.integration
def test_two_year_cold_period_and_dst(source):
    from datetime import datetime, timezone

    from garmin_database.domain.values import FIT_EPOCH

    db, settings, path, service = source
    start = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    stamp = int(start.timestamp()) - FIT_EPOCH
    values = [(stamp + i * 86400 + j * 60, 70) for i in range(731) for j in range(4)]
    Importer(db).archive(
        archive(
            db.root, "2025-12-31", fit_bytes(55, [(253, 4, 134), (27, 1, 2)], values)
        )
    )
    row = unpack(service.period("2024-01-01", "2025-12-31", [KEY]))[0]
    assert row["valid_days"] == row["requested_days"] == 731
    assert row["valid_count"] == 731 * 4 + 2
    assert row["mean"] == 70
    for day in ("2024-03-31", "2024-10-27"):
        row = unpack(service.daily(day, day, [KEY]))[0]
        assert row["valid_count"] == 4


def test_rounding_only_on_presentation_and_unknown_times():
    from garmin_database.application.use_cases.read_health import series
    from garmin_database.domain.aggregation import aggregate_days

    param = dict(key=KEY, unit="bpm", representation="sample")
    rows = [
        dict(
            time="2024-11-08T12:00:00+00:00",
            value=60.25,
            validity="valid",
            requested_day="2024-11-08",
        ),
        dict(time=None, value=90, validity="valid", requested_day="2024-11-08"),
    ]
    daily = aggregate_days(rows, param)
    table = series(param, daily, DAILY_COLUMNS, "day")
    assert table["data"][0][1] == 60 and daily[0]["mean"] == 60.25
    assert daily[0]["untimed_count"] == 1 and daily[0]["day_basis"] == "mixed"


@pytest.mark.integration
def test_helpers_and_configuration(source):
    assert compress_days(["2024-01-01", "2024-01-02", "2024-01-04"], "missing") == [
        {"reason": "missing", "from": "2024-01-01", "to": "2024-01-02"},
        {"reason": "missing", "from": "2024-01-04", "to": "2024-01-04"},
    ]
    config = client_config(source[2])["mcpServers"]["garmin_database"]
    assert Path(config["args"][0]).is_file()
    assert config["args"][-1] == str(source[2])
    assert all(t.annotations.readOnlyHint for t in tool_definitions())


@pytest.mark.integration
def test_adapter_errors_do_not_echo_private_inputs(source, monkeypatch):
    async def check():
        limiter = anyio.CapacityLimiter(1)
        assert (await call(source[3], "missing", {}, limiter)).isError
        assert (
            await call(source[3], "get_daily", {"extra": "secret"}, limiter)
        ).isError
        monkeypatch.setattr(
            source[3],
            "catalog",
            lambda **k: (_ for _ in ()).throw(RuntimeError("private")),
        )
        result = await call(source[3], "garmin_catalog", {}, limiter)
        assert result.isError and "private" not in result.model_dump_json()

    anyio.run(check)


@pytest.mark.integration
def test_adapter_success_limits_and_readonly_annotations(source, monkeypatch):
    from garmin_database.adapters.inbound.mcp.server import create_server

    async def check():
        server = create_server(source[3])
        assert server.name == "garmin_database_mcp"
        limiter = anyio.CapacityLimiter(1)
        result = await call(source[3], "garmin_catalog", {}, limiter)
        assert not result.isError and result.structuredContent["metrics"]
        source[1].mcp_enabled = False
        source[1].save(source[2])
        assert (await call(source[3], "garmin_catalog", {}, limiter)).isError
        monkeypatch.setattr(source[3], "catalog", lambda **k: {"large": "a" * 20000})
        assert (await call(source[3], "garmin_catalog", {}, limiter)).isError

    anyio.run(check)


@pytest.mark.integration
def test_packaged_client_configuration(source, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "D:/app/GarminDatabase/GarminDatabase.exe")
    config = client_config(source[2])["mcpServers"]["garmin_database"]
    assert (
        config["command"].replace("\\", "/")
        == "D:/app/GarminDatabaseMCP/GarminDatabaseMCP.exe"
    )
    assert config["args"][0] == "--settings-file"


@pytest.mark.integration
def test_real_stdio_client_all_tools(tmp_path, source):
    async def check():
        params = StdioServerParameters(
            command=sys.executable,
            env=dict(os.environ),
            args=[
                str(ROOT / "scripts/entrypoints/mcp_stdio.py"),
                "--settings-file",
                str(source[2]),
            ],
            cwd=str(tmp_path),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == {
                    "garmin_catalog",
                    "get_daily",
                    "get_period_stats",
                }
                result = await session.call_tool("garmin_catalog", {})
                assert (
                    not result.isError
                    and result.structuredContent["metrics"][0]["parameter"] == KEY
                )
                args = dict(date_from="2024-11-08", date_to="2024-11-08", metrics=[KEY])
                for name in ("get_daily", "get_period_stats"):
                    result = await session.call_tool(name, args)
                    assert (
                        not result.isError
                        and unpack(result.structuredContent)[0]["mean"] == 63
                    )
                    assert (
                        len(result.model_dump_json(by_alias=True).encode()) < MAX_BYTES
                    )
                    assert len(result.content[0].text) < 100
                source[1].mcp_enabled = False
                source[1].save(source[2])
                assert (await session.call_tool("garmin_catalog", {})).isError

    anyio.run(check)


@pytest.mark.integration
def test_postgresql_cancellation_interrupts_running_query(source):
    import time

    import psycopg

    from garmin_database.adapters.outbound.postgres.readings import DataAccess

    stop = threading.Event()
    began = time.monotonic()
    from garmin_database.application.ports import ReadFailure

    with pytest.raises(ReadFailure) as cancelled:
        with DataAccess(source[0]).snapshot(stop) as snapshot:
            timer = threading.Timer(0.1, stop.set)
            timer.start()
            try:
                snapshot.conn.execute("SELECT pg_sleep(5)")
            finally:
                timer.cancel()
    assert isinstance(cancelled.value.__context__, psycopg.errors.QueryCanceled)
    assert time.monotonic() - began < 2


@pytest.mark.integration
def test_mcp_postgresql_deadline_interrupts_blocked_catalog(source, monkeypatch):
    import time

    original = Queries.parameters

    def blocked(self, conn=None):
        conn.execute("SELECT pg_sleep(5)")
        return original(self, conn)

    monkeypatch.setattr(Queries, "parameters", blocked)
    began = time.monotonic()
    with pytest.raises(AccessError, match="Przekroczono"):
        create_service(source[2], seconds=0.1).catalog()
    assert time.monotonic() - began < 2
