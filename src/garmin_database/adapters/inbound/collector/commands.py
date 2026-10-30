"""Noninteractive scheduled runs and explicit interactive authentication."""

import argparse
import getpass
import json
import signal
import sys
from threading import Event

from garmin_database.application.use_cases.run_collector import RunCollector


def parser():
    result = argparse.ArgumentParser(description="GarminDatabase — kolektor cykliczny")
    result.add_argument("--config", help="Bezwzględna ścieżka konfiguracji kolektora")
    subs = result.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init")
    init.add_argument("--data-dir")
    run = subs.add_parser("run")
    run.add_argument("--scheduled", action="store_true")
    subs.add_parser("login")
    subs.add_parser("prepare-key")
    status = subs.add_parser("status")
    status.add_argument("--json", action="store_true")
    subs.add_parser("logs")
    schedule = subs.add_parser("schedule")
    schedule.add_argument(
        "action", choices=["install", "apply", "enable", "disable", "status"]
    )
    return result


def main(argv=None, *, files_factory, manager_factory, session_factory, synchronize):
    args = parser().parse_args(argv)
    stop = Event()
    old_handlers = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, lambda *_: stop.set())
        files = files_factory(args.config)
        if args.command == "init":
            if files.config_path.exists():
                raise FileExistsError("Konfiguracja już istnieje")
            files.save_config(files.defaults(args.data_dir))
            print(str(files.config_path))
            return 0
        config = files.load_config()
        if args.command == "run":
            # Runtime is an injected port; the entry adapter does not create it.
            runtime = manager_factory(args.config).runtime(config, synchronize)
            outcome = RunCollector(runtime).run(config, stop, scheduled=args.scheduled)
            if outcome not in {
                "not_due",
                "disabled",
                "already_claimed",
                "skipped_busy",
            }:
                print(outcome)
            return (
                0
                if outcome
                in {"not_due", "disabled", "already_claimed", "skipped_busy", "success"}
                else 2
            )
        manager = manager_factory(args.config)
        if args.command == "status":
            print(json.dumps(manager.status(config), ensure_ascii=False, indent=2))
        elif args.command == "logs":
            print(files.logs(config))
        elif args.command == "prepare-key":
            manager.prepare_key(config)
        elif args.command == "login":
            if not sys.stdin.isatty():
                raise RuntimeError("Logowanie wymaga terminala interaktywnego")
            manager.login(
                config,
                session_factory,
                input("E-mail Garmin: ").strip(),
                getpass.getpass("Hasło Garmin: "),
                lambda: input("Kod MFA: "),
                stop,
            )
            print("Sesja kolektora gotowa")
        elif args.command == "schedule":
            if args.action == "status":
                print(json.dumps(manager.status(config), ensure_ascii=False, indent=2))
            else:
                if args.action in {"enable", "disable"}:
                    config.enabled = args.action == "enable"
                    files.save_config(config)
                manager.apply(config)
                print("Harmonogram zastosowany")
        return 0
    except KeyboardInterrupt:
        stop.set()
        return 130
    except Exception as error:
        # Diagnostics are a category, never third-party exception text.
        print(
            f"Operacja nie powiodła się ({type(error).__name__}); sprawdź konfigurację i uprawnienia",
            file=sys.stderr,
        )
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
