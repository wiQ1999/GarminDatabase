"""Compare every supplied HTML reference with chart data, MCP stdio and actual exports."""

import argparse
import csv
import html
import json
import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from garmin_database.adapters.outbound.filesystem.settings_json import Settings  # noqa: E402
from garmin_database.adapters.outbound.postgres.database import Database  # noqa: E402
from garmin_database.adapters.outbound.postgres.queries import Queries  # noqa: E402
from garmin_database.application.mcp_metrics import MCP_PARAMETERS  # noqa: E402
from garmin_database.domain.time import today  # noqa: E402
from scripts.garmin_channels import Wire, collect  # noqa: E402
from scripts.garmin_differences import selected_keys, source_differences  # noqa: E402
from scripts.garmin_point_locators import write_point_locators  # noqa: E402
from scripts.garmin_reference import reference  # noqa: E402


def public_source(result):
    return {key: value for key, value in result.items() if key != "data"}


def reference_duplicates(refs):
    seen = {}
    for ref in refs:
        key = ref["content_sha256"]
        if key in seen:
            ref["reference_issues"].append(
                "powielenie dostępnych kart i punktów z " + seen[key]
            )
        else:
            seen[key] = ref["file"]
    return refs


def summarize_audit(audits):
    failures, unexposed, unsupported = [], set(), set()
    for audit in audits:
        for key, channels in audit["parameters"].items():
            for channel in [
                "chart",
                "mcp",
                "mcp_period",
                "mcp_monthly",
                "export_details",
                "export_history",
                "export_month_history",
                "raw_daily_summary",
            ]:
                if channel not in channels:
                    continue
                result = channels[channel]
                if result.get("equal") is False:
                    failures.append(dict(parameter=key, channel=channel, **result))
                if result.get("status") == "not_exposed_by_public_contract":
                    unexposed.add(key)
                if result.get("status") == "unsupported_period":
                    unsupported.add(key)
    return dict(
        channel_discrepancies=failures,
        not_exposed_in_mcp=sorted(unexposed),
        chart_period_not_supported=sorted(unsupported),
    )


def render(report, output):
    esc = html.escape
    parts = [
        '<!doctype html><html lang="pl"><meta charset="utf-8"><title>Porównanie Garmin</title>',
        "<style>body{font:15px system-ui;max-width:1450px;margin:32px auto;padding:0 20px;color:#202632;background:#f5f7fa}table{border-collapse:collapse;width:100%;background:white;margin:15px 0 32px}th,td{border:1px solid #d7dce5;padding:9px;text-align:left;vertical-align:top}th{background:#e6ecf5}h2{margin-top:40px}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;font-size:12px}a{color:#1760a8}</style>",
        "<h1>Garmin HTML → wykresy, MCP, eksport</h1>",
        "<p>Raport zawiera liczniki i lokalizatory, bez wartości pomiarów. Rzeczywiste wartości pozostają w oryginalnym HTML i wygenerowanych plikach eksportu.</p>",
        "<p>Wykresy: rzeczywiste zapytanie aplikacji i przygotowanie serii, bez porównania pikseli. MCP: gotowy proces stdio, wszystkie strony. Eksport: produkcyjny eksporter i ponowny odczyt JSON. Publikacja odtwarzalnego cache wyłączona. Globalne ustawienia pozostają bez zmian.</p>",
        "<p>Podstawowy czas HTML interpretowany jako Europe/Warsaw; przesunięcia ±1/±2 h są wyłącznie diagnostyką. Rozwinięcie faz snu do przedziałów jest diagnostyką między sąsiednimi obserwacjami (maksymalnie 12 h), bez zmiany źródeł.</p>",
        "<p>Różne metryki: średnia próbek doby, średnia podczas snu/czuwania i statystyki przedziałów Garmin nie mają automatycznej równoważności. Dopasowanie po zaokrągleniu lub transformacji nie jest ścisłą zgodnością.</p>",
        "<p>Do walidacji użyto osobnej, prywatnej konfiguracji MCP i eksportu. Nie poszerzono zapisanej polityki dostępu aplikacji. Liczby punktów obejmują powtórzenia serii i powielone zapisy HTML; nie oznaczają liczby odrębnych pomiarów.</p>",
        "<p><b>Legenda:</b> exact — zgodność liczbowa; display_rounding_match — zgodność dopiero po zaokrągleniu; different — różne wartości; no_stored_equivalent — brak udokumentowanego odpowiednika w katalogu lub konwersji; reference_not_numeric — brak liczbowej referencji; no_exact_reference_values — sam rysunek bez dokładnych wartości. semantic_constraint i method określają ograniczenia porównania, nawet gdy liczby są zgodne.</p>",
        "<h2>Kontrola kanałów aplikacji</h2><pre>"
        + esc(json.dumps(report["application_summary"], ensure_ascii=False, indent=2))
        + "</pre>"
        + coverage_html(report),
        "<h2>Źródła</h2><table><tr><th>Plik</th><th>Widok i rzeczywisty zakres</th><th>Uwagi referencyjne</th><th>Eksport</th></tr>",
    ]
    for index, source in enumerate(report["sources"]):
        link = export_links(source, output)
        parts.append(
            f'<tr><td><a href="#s{index}">{esc(source["file"])}</a></td><td>{esc(source["topic"])}<br>{esc(source["visible_range"])}</td><td>{esc("; ".join(source["reference_issues"])) or "—"}</td><td>{link}</td></tr>'
        )
    parts.append("</table>")
    for index, source in enumerate(report["sources"]):
        parts.extend(
            [
                f'<h2 id="s{index}">{esc(source["file"])}</h2>',
                "<pre>"
                + esc(
                    json.dumps(
                        dict(
                            range=source["visible_range"],
                            reference_issues=source["reference_issues"],
                            unparsed=source["unparsed_point_formats"],
                        ),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                + "</pre>",
                "<table><tr><th>Odniesienie Garmin / parametr</th><th>Wykres</th><th>MCP</th><th>Eksport</th></tr>",
            ]
        )
        for feature in source["features"]:
            cells = "".join(
                "<td><pre>"
                + esc(
                    json.dumps(
                        feature["channels"][channel], ensure_ascii=False, indent=2
                    )
                )
                + "</pre></td>"
                for channel in ["chart", "mcp", "export"]
            )
            parts.append(
                "<tr><td>"
                + esc(feature["label"])
                + "<br><code>"
                + esc(feature.get("parameter") or "brak odpowiednika")
                + "</code></td>"
                + cells
                + "</tr>"
            )
        if not source["features"]:
            parts.append(
                "<tr><td>Brak dokładnych wartości referencyjnych</td><td>Nie można porównać</td><td>Nie można porównać</td><td>Nie można porównać</td></tr>"
            )
        parts.append(
            "</table><details><summary>Kontrola spójności danych wariantów</summary><pre>"
            + esc(
                json.dumps(
                    source.get("channel_audit", source.get("channel_status")),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            + "</pre></details>"
        )
    parts.append("</html>")
    output.write_text("\n".join(parts), encoding="utf-8")


def export_links(source, output):
    links = []
    for key, label in [
        ("export_directory", "dzienny"),
        ("export_month_directory", "miesięczny"),
    ]:
        folder = source.get(key)
        if folder:
            relative = os.path.relpath(folder, output.parent).replace("\\", "/")
            links.append(
                '<a href="'
                + html.escape(relative)
                + '/manifest.json">'
                + label
                + "</a>"
            )
    return " · ".join(links) or "—"


def coverage_html(report):
    rows = []
    for key, coverage in report.get("parameter_coverage", {}).items():
        rows.append(
            "<tr><td><code>"
            + html.escape(key)
            + "</code></td><td>"
            + ("Tak" if coverage["observed_data_tested"] else "Brak próbki")
            + "</td><td>"
            + str(len(coverage["scopes"]))
            + "</td></tr>"
        )
    return (
        "<details><summary>Pokrycie wszystkich parametrów katalogu</summary><table><tr><th>Parametr</th><th>Sprawdzono rzeczywiste obserwacje</th><th>Zakresy kontroli</th></tr>"
        + "".join(rows)
        + "</table></details>"
    )


def supplemental_scopes(db, catalog, audit):
    scopes = {}
    with db.connect(readonly=True) as conn:
        for key, check in audit["parameters"].items():
            if check["sql_rows"]:
                continue
            ids = (
                set(catalog[key]["ids"])
                | Queries.component_rules(catalog[key], conn).keys()
            )
            day = conn.execute(
                "SELECT max(a.day) FROM fit_fields f JOIN fit_messages m ON m.id=f.message_id JOIN file_decodes d ON d.id=m.file_decode_id JOIN archive_entries e ON e.fit_file_id=d.fit_file_id JOIN archives a ON a.id=e.archive_id WHERE d.is_active=1 AND f.resolved_catalog_id=ANY(%s)",
                (list(ids),),
            ).fetchone()[0]
            if day:
                scopes.setdefault(date.fromisoformat(day), []).append(key)
    return scopes


async def compare_references(
    refs, db, configured, private, args, catalog, wire, audits
):
    sources, cache = [], {}
    for index, ref in enumerate(refs, 1):
        print(
            json.dumps(dict(phase="reference", checked=index, total=len(refs))),
            flush=True,
        )
        bundle = None
        if ref["start"] and ref["topic"] != "unrelated_or_incomplete":
            keys = selected_keys(ref, catalog)
            token = (ref["start"], ref["end"], tuple(keys))
            if keys and token not in cache:
                cache[token] = await collect(
                    db,
                    configured,
                    private,
                    args.output / "exports",
                    catalog,
                    keys,
                    ref["start"],
                    ref["end"],
                    wire,
                )
                audits.append(public_source(cache[token]))
            bundle = cache.get(token)
        sources.append(source_differences(ref, bundle, catalog))
        (args.output / "sources.checkpoint.json").write_text(
            json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return sources


async def run_channels(args, db, catalog, configured, private, refs):
    with db.connect(readonly=True) as conn:
        last_day = conn.execute("SELECT max(day) FROM archives").fetchone()[0]
    audit_day = args.audit_day or (
        date.fromisoformat(last_day) if last_day else today()
    )
    params = StdioServerParameters(
        command=str(args.mcp_executable.resolve()),
        args=["--settings-file", str(private.resolve())],
        env=dict(os.environ),
        cwd=str(ROOT),
    )
    audits = []
    with open(os.devnull, "w") as errors:
        async with stdio_client(params, errlog=errors) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools) == 6
                wire = Wire(session)
                print(
                    json.dumps(dict(phase="all_stored_parameters", total=len(catalog))),
                    flush=True,
                )
                audit = await collect(
                    db,
                    configured,
                    private,
                    args.output / "exports",
                    catalog,
                    list(catalog),
                    audit_day,
                    audit_day,
                    wire,
                )
                cursor = None
                while True:
                    payload = await wire.call(
                        "garmin_catalog",
                        {"cursor": cursor} if cursor else {},
                        audit["revision"],
                    )
                    cursor = payload["next_cursor"]
                    if cursor is None:
                        break
                audits.append(public_source(audit))
                for day, keys in supplemental_scopes(db, catalog, audit).items():
                    supplement = await collect(
                        db,
                        configured,
                        private,
                        args.output / "exports",
                        catalog,
                        keys,
                        day,
                        day,
                        wire,
                    )
                    audits.append(public_source(supplement))
                del audit
                sources = await compare_references(
                    refs, db, configured, private, args, catalog, wire, audits
                )
    return sources, audits, dict(wire.calls)


def coverage_audit(catalog, audits):
    result = {}
    for key in catalog:
        scopes = [
            dict(start=a["start"], end=a["end"], rows=a["parameters"][key]["sql_rows"])
            for a in audits
            if key in a["parameters"]
        ]
        result[key] = dict(
            observed_data_tested=any(s["rows"] for s in scopes), scopes=scopes
        )
    return result


def difference_rows(sources):
    for source in sources:
        for feature in source["features"]:
            for channel, result in feature["channels"].items():
                matched = result.get("status") == "exact" or (
                    "reference_points" in result
                    and result["exact"] == result["reference_points"]
                )
                if not matched:
                    yield dict(
                        source=source["file"],
                        visible_range=source["visible_range"],
                        feature=feature["label"],
                        parameter=feature.get("parameter"),
                        variant=channel,
                        result=json.dumps(result, ensure_ascii=False),
                    )


def write_report(report, output):
    (output / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    render(report, output / "comparison.html")
    with (output / "differences.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        fields = [
            "source",
            "visible_range",
            "feature",
            "parameter",
            "variant",
            "result",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(difference_rows(report["sources"]))
    write_point_locators(report, output)


async def analyze(args):
    args.output.mkdir(parents=True, exist_ok=True)
    original = args.settings_file.read_bytes()
    settings = Settings.load(args.settings_file)
    db = Database(settings.data_dir, settings.database_dsn)
    catalog = {p["key"]: p for p in Queries(db).parameters()}
    private = args.output / "settings.private.json"
    configured = replace(
        settings,
        settings_version=2,
        mcp_enabled=True,
        mcp_parameters=sorted(catalog.keys() & MCP_PARAMETERS),
        export_parameters=sorted(catalog),
    )
    configured.save(private)
    refs = reference_duplicates(
        [reference(p) for p in sorted(args.input.glob("*.html"))]
    )
    try:
        sources, audits, calls = await run_channels(
            args, db, catalog, configured, private, refs
        )
    finally:
        private.unlink(missing_ok=True)
    report = dict(
        schema_version=1,
        reference_root=str(args.input.resolve()),
        stored_parameters=len(catalog),
        sources=sources,
        all_parameter_audit=audits[0],
        parameter_coverage=coverage_audit(catalog, audits),
        application_summary=summarize_audit(audits),
        mcp_calls=calls,
        original_settings_unchanged=original == args.settings_file.read_bytes(),
        measurements_in_report=False,
        dataset_revisions=sorted({a["revision"] for a in audits}),
    )
    assert report["original_settings_unchanged"]
    write_report(report, args.output)
    print(
        json.dumps(
            dict(
                phase="complete",
                sources=len(sources),
                parameters=len(catalog),
                discrepancies=len(
                    report["application_summary"]["channel_discrepancies"]
                ),
            )
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("verification"))
    parser.add_argument("--settings-file", type=Path, required=True)
    parser.add_argument("--mcp-executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--audit-day",
        type=date.fromisoformat,
        help="Dzień kontroli katalogu; domyślnie ostatnie archiwum",
    )
    args = parser.parse_args()
    try:
        anyio.run(analyze, args)
    except Exception as error:
        print("Comparison failed: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
