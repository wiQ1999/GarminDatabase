"""Noninteractive scheduled runs and explicit interactive authentication."""

import argparse
import getpass
import json
import signal
import sys
from dataclasses import replace
from threading import Event

from garmin_database.application.time_presentation import collector_status_times
from garmin_database.application.use_cases.run_collector import RunCollector


def parser():
    result = argparse.ArgumentParser(description="GarminDatabase — kolektor cykliczny")
    result.add_argument("--config", help="Bezwzględna ścieżka konfiguracji kolektora")
    subs = result.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init")
    init.add_argument("--data-dir")
    install = subs.add_parser(
        "install", help="Przygotuj konfigurację i zarejestruj harmonogram"
    )
    install.add_argument("--account", help="Istniejące konto systemowe kolektora")
    install.add_argument("--interval", type=int, help="Cykl w minutach, minimum 15")
    install.add_argument(
        "--logon",
        choices=["interactive", "password"],
        help="Windows: bieżące konto bez hasła albo praca po wylogowaniu",
    )
    install.add_argument(
        "--enable", action="store_true", help="Włącz przyszłe uruchomienia"
    )
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


QUIET_OUTCOMES = frozenset({"not_due", "disabled", "already_claimed", "skipped_busy"})


class CollectorCommands:
    def __init__(
        self, args, stop, files_factory, manager_factory, session_factory, synchronize
    ):
        self.args, self.stop = args, stop
        self.files = files_factory(args.config)
        self.manager_factory = manager_factory
        self.session_factory = session_factory
        self.synchronize = synchronize

    def execute(self):
        return {
            "init": self.initialize,
            "install": self.install,
            "run": self.run,
            "status": self.status,
            "logs": self.logs,
            "prepare-key": self.prepare_key,
            "login": self.login,
            "schedule": self.schedule,
        }[self.args.command]()

    def manager(self):
        return self.manager_factory(self.args.config)

    def initialize(self):
        if self.files.config_path.exists():
            raise FileExistsError("Konfiguracja już istnieje")
        self.files.save_config(self.files.defaults(self.args.data_dir))
        print(str(self.files.config_path))
        return 0

    def install(self):
        try:
            config = self.files.load_config()
        except FileNotFoundError:
            config = self.files.defaults()
        config = self.files.for_account(config, self.args.account, self.args.logon)
        changes = {}
        if self.args.interval is not None:
            changes["interval_minutes"] = self.args.interval
        if self.args.enable:
            changes["enabled"] = True
        self.files.save_config(replace(config, **changes))
        self.manager().install(self.files.load_config())
        print(
            "Kolektor zainstalowany. Przygotuj sesję Garmin poleceniem login; sprawdź status i logs."
        )
        return 0

    def run(self):
        config = self.files.load_config()
        runtime = self.manager().runtime(config, self.synchronize)
        outcome = RunCollector(runtime).run(
            config, self.stop, scheduled=self.args.scheduled
        )
        if outcome not in QUIET_OUTCOMES:
            print(outcome)
        return 0 if outcome in QUIET_OUTCOMES | {"success"} else 2

    def status(self):
        value = self.manager().status(self.files.load_config())
        print(json.dumps(collector_status_times(value), ensure_ascii=False, indent=2))
        return 0

    def logs(self):
        print(self.files.logs(self.files.load_config()))
        return 0

    def prepare_key(self):
        self.manager().prepare_key(self.files.load_config())
        return 0

    def login(self):
        if not sys.stdin.isatty():
            raise RuntimeError("Logowanie wymaga terminala interaktywnego")
        self.manager().login(
            self.files.load_config(),
            self.session_factory,
            input("E-mail Garmin: ").strip(),
            getpass.getpass("Hasło Garmin: "),
            lambda: input("Kod MFA: "),
            self.stop,
        )
        print("Sesja kolektora gotowa")
        return 0

    def schedule(self):
        if self.args.action == "status":
            return self.status()
        config = self.files.load_config()
        if self.args.action in {"enable", "disable"}:
            config.enabled = self.args.action == "enable"
            self.files.save_config(config)
        self.manager().apply(config)
        print("Harmonogram zastosowany")
        return 0


def main(argv=None, *, files_factory, manager_factory, session_factory, synchronize):
    args = parser().parse_args(argv)
    stop = Event()
    old_handlers = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, lambda *_: stop.set())
        return CollectorCommands(
            args, stop, files_factory, manager_factory, session_factory, synchronize
        ).execute()
    except KeyboardInterrupt:
        stop.set()
        return 130
    except Exception as error:
        print(
            f"Operacja nie powiodła się ({type(error).__name__}); sprawdź konfigurację i uprawnienia",
            file=sys.stderr,
        )
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
