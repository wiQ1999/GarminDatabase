"""Headless entry point shares the desktop pipeline; suitable for local checks."""

import argparse
import json
import threading
from datetime import date

from .auth import GarminSource
from .exporter import Exporter
from .query import Queries
from .settings import Settings
from .storage import Database
from .sync import Sync
from .util import Cancelled, writer_lock, yesterday


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="GarminDatabase — import, status i eksport"
    )
    parser.add_argument(
        "command", choices=["sync", "import-local", "reprocess", "status", "export"]
    )
    parser.add_argument("--data-dir")
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
    parser.add_argument("--full-samples", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings.load()
    db = Database(args.data_dir or settings.data_dir)
    stop = threading.Event()

    def progress(day, stage, index, total):
        print(f"{index}/{total} {day}: {stage}", flush=True)

    try:
        if args.command in {"sync", "import-local", "reprocess"}:
            errors = Sync(db, GarminSource() if args.command == "sync" else None).run(
                args.start,
                args.end,
                stop,
                progress,
                local_only=args.command != "sync",
                force=args.command == "reprocess",
            )
            print(json.dumps(db.status(), ensure_ascii=False), flush=True)
            return 2 if errors else 0
        with writer_lock(db.root):
            db.initialize()
        if args.command == "status":
            print(json.dumps(db.status(), ensure_ascii=False, indent=2))
            return 0
        params = Queries(db).parameters()
        if args.parameters:
            requested = set(args.parameters.split(","))
            params = [p for p in params if p["key"] in requested]
            if requested - {p["key"] for p in params}:
                raise ValueError("Nieznany parametr eksportu")
        result = Exporter(db).generate(
            args.output or settings.export_dir,
            params,
            args.start,
            args.end,
            args.recent_days,
            stop,
            args.full_samples,
            progress,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        stop.set()
        return 130
    except Cancelled:
        return 130
    except Exception as error:
        print(
            f"Operacja nie powiodła się ({type(error).__name__}); szczegóły prywatne pominięto"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
