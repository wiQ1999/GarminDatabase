"""Headless entry point shares the desktop pipeline; suitable for local checks."""

import argparse
import json
import threading
from datetime import date

from garmin_database.application.read_models import select_parameters
from garmin_database.application.sync_messages import sync_summary_text
from garmin_database.domain.cancellation import Cancelled
from garmin_database.domain.time import yesterday


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="GarminDatabase — import, status i eksport"
    )
    parser.add_argument(
        "command", choices=["sync", "import-local", "reprocess", "status", "export"]
    )
    parser.add_argument("--data-dir")
    parser.add_argument("--settings-file")
    parser.add_argument(
        "--from", dest="start", type=date.fromisoformat, default=date(2024, 1, 1)
    )
    parser.add_argument(
        "--to", dest="end", type=date.fromisoformat, default=yesterday()
    )
    parser.add_argument("--output")
    parser.add_argument(
        "--parameters", help="Nazwy message.field, oddzielone przecinkiem"
    )
    parser.add_argument("--recent-days", type=int, default=90)
    parser.add_argument("--summary-period", choices=["day", "month"], default="day")
    return parser.parse_args(argv)


def progress(day, stage, index, total):
    print(f"{index}/{total} {day}: {stage}", flush=True)


def export_files(args, settings, db, stop):
    catalog = db.parameters()
    if settings.migrate(catalog):
        db.settings_store.save(settings, args.settings_file)
    requested = (
        args.parameters.split(",") if args.parameters else settings.export_parameters
    )
    params = select_parameters(catalog, settings.export_parameters, requested)
    result = db.export(settings, args.settings_file).generate(
        args.output or settings.export_dir,
        params,
        args.start,
        args.end,
        args.recent_days,
        stop,
        args.summary_period,
        progress,
    )
    print(
        json.dumps(
            {"directory": str(result.directory), "files": result.files},
            ensure_ascii=False,
        )
    )
    return 0


def run_command(args, services, settings, stop):
    if args.command in {"sync", "import-local", "reprocess"}:
        result = services.sync(
            args.start,
            args.end,
            stop,
            progress,
            local_only=args.command != "sync",
            force=args.command == "reprocess",
            detailed=True,
        )
        print(sync_summary_text(result), flush=True)
        print(json.dumps(services.status(), ensure_ascii=False), flush=True)
        return 2 if result.issue_count else 0
    if args.command == "status":
        print(json.dumps(services.status(), ensure_ascii=False, indent=2))
        return 0
    return export_files(args, settings, services, stop)


def main(argv=None, *, settings_store, services_factory):
    args = parse_args(argv)
    stop = threading.Event()
    try:
        settings = settings_store.load(args.settings_file)
        if args.data_dir:
            settings.data_dir = args.data_dir
        return run_command(args, services_factory(settings), settings, stop)
    except (KeyboardInterrupt, Cancelled):
        stop.set()
        return 130
    except Exception as error:
        print(
            f"Operacja nie powiodła się ({type(error).__name__}); szczegóły prywatne pominięto"
        )
        return 1
