"""Desktop composition and safe startup. See docs/03-architecture.md."""

import argparse
import ssl
import sys
import time
from datetime import date
from pathlib import Path
from threading import Event

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from garmin_database.adapters.inbound.desktop.icons import application_icon
from garmin_database.adapters.inbound.desktop.window import Window as DesktopWindow
from garmin_database.adapters.outbound.diagnostics.startup import startup_failure
from garmin_database.adapters.outbound.filesystem.files import atomic_json
from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.bootstrap.dependencies import Services


def Window(settings=None, settings_path=None):
    settings = settings or Settings.load(settings_path)
    return DesktopWindow(settings, settings_path, services=Services(settings))


def smoke_import(window, args):
    if not args.smoke_import_from:
        return
    # The external runner supplies synthetic originals and an isolated schema.
    # Exercise frozen bulk import and idempotent resume before the screenshot.
    for _ in range(2):
        errors = window.services.sync(
            date.fromisoformat(args.smoke_import_from),
            date.fromisoformat(args.smoke_import_to),
            Event(),
            lambda *a: None,
            local_only=True,
        )
        if errors:
            raise RuntimeError("Błąd syntetycznego importu smoke")
    window.refresh()


def smoke_snapshot(window, picture, app):
    deadline = time.monotonic() + 20

    def fail():
        atomic_json(
            Path(picture).with_suffix(".error.json"), {"type": "UIReadinessFailure"}
        )
        app.setQuitOnLastWindowClosed(False)
        window.closing = True
        window.close()

        def leave_when_closed():
            if window.isVisible():
                QTimer.singleShot(100, leave_when_closed)
            else:
                app.exit(1)

        leave_when_closed()

    def snapshot():
        idle = (
            not window.overview.busy
            and window.query_worker is None
            and not window.query_pending
        )
        if (
            idle
            and window.status_info
            and window.catalog_loaded
            and not window.status_error.text()
        ):
            atomic_json(
                Path(picture).with_suffix(".ui.json"),
                {"overview_ready": True, "background_idle": True},
            )
            window.grab().save(picture)
            window.close()
        elif (idle and window.overview.initialized) or time.monotonic() >= deadline:
            fail()
        else:
            QTimer.singleShot(100, snapshot)

    QTimer.singleShot(100, snapshot)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--settings-file")
    parser.add_argument("--smoke-screenshot")
    parser.add_argument("--smoke-import-from")
    parser.add_argument("--smoke-import-to")
    args = parser.parse_args(argv)
    if bool(args.smoke_import_from) != bool(args.smoke_import_to):
        parser.error("Podaj obie granice syntetycznego importu smoke")
    if args.smoke_import_from and not args.smoke_screenshot:
        parser.error("Import smoke wymaga --smoke-screenshot")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("GarminDatabase")
    app.setWindowIcon(application_icon())
    settings = None
    try:
        if args.smoke_screenshot:
            # A visible window alone does not verify the frozen HTTPS runtime.
            ssl.create_default_context()
        settings = Settings.load(args.settings_file)
        if args.data_dir:
            settings.data_dir = args.data_dir
        window = Window(settings, args.settings_file)
        smoke_import(window, args)
        window.show()
        if args.smoke_screenshot:
            smoke_snapshot(window, args.smoke_screenshot, app)
        return app.exec()
    except Exception as error:
        if args.smoke_screenshot:
            atomic_json(
                Path(args.smoke_screenshot).with_suffix(".error.json"),
                {"type": type(error).__name__, "module": getattr(error, "name", None)},
            )
            return 1
        QMessageBox.critical(
            None,
            "GarminDatabase",
            startup_failure(error, settings, args.settings_file),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
