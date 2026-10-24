"""Desktop composition and safe startup. See docs/03-architecture.md."""

import argparse
import ssl
import sys
from pathlib import Path

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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--settings-file")
    parser.add_argument("--smoke-screenshot")
    args = parser.parse_args(argv)
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
        window.show()
        if args.smoke_screenshot:

            def snapshot():
                window.grab().save(args.smoke_screenshot)
                window.close()

            QTimer.singleShot(1000, snapshot)
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
