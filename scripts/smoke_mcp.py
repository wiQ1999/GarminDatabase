"""Exercise an actual stdio process using synthetic FIT data only."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

import anyio
import psycopg
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from fixtures import archive, fit_bytes  # noqa: E402

from garmin_database.fit import FIT_EPOCH  # noqa: E402
from garmin_database.importer import Importer  # noqa: E402
from garmin_database.settings import Settings  # noqa: E402
from garmin_database.storage import Database  # noqa: E402


def result_row(result):
    assert not result.isError
    table = result.structuredContent["series"][0]
    return dict(zip(table["columns"], table["data"][0]))


async def evaluate(session, key):
    args = dict(date_from="2024-01-01", date_to="2025-12-31", metrics=[key])
    catalog = await session.call_tool("garmin_catalog", {})
    assert catalog.structuredContent["metrics"][0]["parameter"] == key
    period = result_row(await session.call_tool("get_period_stats", args))
    daily = await session.call_tool("get_daily", args)
    day = result_row(daily)
    empty = result_row(
        await session.call_tool(
            "get_period_stats",
            dict(date_from="2023-12-01", date_to="2023-12-31", metrics=[key]),
        )
    )
    short = result_row(
        await session.call_tool(
            "get_period_stats",
            dict(date_from="2024-01-01", date_to="2024-01-03", metrics=[key]),
        )
    )
    answers = [
        str(int(period["mean"])),
        str(period["valid_count"]),
        str(period["valid_days"]),
        str(period["requested_days"]),
        "null" if empty["mean"] is None else "0",
        str(int(day["maximum"] - day["minimum"])),
        day["first_time"],
        str(day["mean"] == period["mean"]).lower(),
        str(daily.structuredContent["truncated"]).lower(),
        str(short["requested_days"] - short["valid_days"]),
    ]
    expected = [
        pair.findtext("answer")
        for pair in ElementTree.parse(ROOT / "tests/mcp_evaluation.xml").getroot()
    ]
    assert answers == expected, "Synthetic tool evaluation failed"
    return len(answers)


async def smoke(executable, result_dir):
    result_dir.mkdir(parents=True, exist_ok=True)
    db = Database(result_dir / "data")
    db.initialize()
    key = "monitoring.heart_rate"
    instant = int(datetime(2024, 1, 2, 8, tzinfo=timezone.utc).timestamp()) - FIT_EPOCH
    archive_path = db.root / "raw/2024-01-02.zip"
    if not archive_path.exists():
        archive(
            db.root,
            "2024-01-02",
            fit_bytes(
                55, [(253, 4, 134), (27, 1, 2)], [(instant, 60), (instant + 60, 80)]
            ),
        )
    Importer(db).archive(archive_path)
    path = result_dir / "settings.json"
    settings = Settings(
        data_dir=str(db.root),
        settings_version=2,
        export_parameters=[key],
        mcp_parameters=[key],
        mcp_enabled=True,
    )
    settings.save(path)
    args = [] if executable else [str(ROOT / "mcp_stdio.py")]
    params = StdioServerParameters(
        command=str(executable or sys.executable),
        env=dict(os.environ),
        args=[*args, "--settings-file", str(path.resolve())],
        cwd=str(result_dir),
    )
    errors_path = result_dir / "stderr.log"
    with anyio.fail_after(45), errors_path.open("w", encoding="utf-8") as errors:
        async with stdio_client(params, errlog=errors) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 3
                catalog = await session.call_tool("garmin_catalog", {})
                assert not catalog.isError
                evaluation_count = await evaluate(session, key)
                for name in ("get_daily", "get_period_stats"):
                    result = await session.call_tool(
                        name,
                        dict(
                            date_from="2024-01-01", date_to="2025-12-31", metrics=[key]
                        ),
                    )
                    assert not result.isError, result
                    assert len(result.model_dump_json().encode()) <= 16384
                    if name == "get_period_stats":
                        table = result.structuredContent["series"][0]
                        assert table["data"][0][table["columns"].index("mean")] == 70
                settings.mcp_enabled = False
                settings.save(path)
                assert (await session.call_tool("garmin_catalog", {})).isError
    assert not errors_path.read_text(encoding="utf-8").strip(), (
        "Server wrote unexpected stderr; see synthetic smoke log"
    )
    report = dict(
        status="passed",
        tools=3,
        evaluations=evaluation_count,
        synthetic=True,
        packaged=bool(executable),
    )
    (result_dir / "mcp-smoke.json").write_text(json.dumps(report), encoding="utf-8")
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=lambda p: Path(p).resolve())
    parser.add_argument(
        "--output",
        type=lambda p: Path(p).resolve(),
        default=ROOT / "test-results/mcp-smoke",
    )
    args = parser.parse_args()
    dsn = os.environ.get("GARMIN_TEST_DATABASE_DSN")
    if not dsn:
        raise SystemExit(
            "Ustaw GARMIN_TEST_DATABASE_DSN na osobną bazę testową PostgreSQL"
        )
    schema = "garmin_mcp_smoke_" + uuid4().hex
    previous = os.environ.get("GARMIN_DATABASE_DSN")
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            os.environ["GARMIN_DATABASE_DSN"] = make_conninfo(
                dsn, options=f"-c search_path={schema}"
            )
            anyio.run(smoke, args.executable, args.output)
        finally:
            if previous is None:
                os.environ.pop("GARMIN_DATABASE_DSN", None)
            else:
                os.environ["GARMIN_DATABASE_DSN"] = previous
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


if __name__ == "__main__":
    main()
