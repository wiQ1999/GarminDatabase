"""Export selection and consistent reading. Contract: docs/05-export.md."""

from garmin_database.application.ports import ExportSink, Readings, SettingsStore
from garmin_database.domain.time import dates


class Exporter:
    def __init__(
        self,
        readings: Readings,
        sink: ExportSink,
        settings,
        settings_store: SettingsStore,
        settings_path=None,
    ):
        self.readings = readings
        self.sink = sink
        self.settings = settings
        self.settings_store = settings_store
        self.settings_path = settings_path

    def generate(
        self,
        output,
        parameters,
        start,
        end,
        recent_days=90,
        stop=None,
        summary_period="day",
        progress=lambda *a: None,
    ):
        list(dates(start, end))
        if recent_days < 1 or summary_period not in {"day", "month"}:
            raise ValueError("Nieprawidłowy okres szczegółów lub podsumowań")
        if not parameters or len({p["key"] for p in parameters}) != len(parameters):
            raise ValueError("Wybierz niepowtarzające się parametry")
        with self.readings.snapshot(stop) as snapshot:
            if self.settings.migrate(snapshot.catalog):
                self.settings_store.save(self.settings, self.settings_path)
            parameters = snapshot.select(
                self.settings, "export", [p["key"] for p in parameters]
            )
            return self.sink.generate(
                output,
                parameters,
                start,
                end,
                recent_days,
                stop,
                summary_period,
                progress,
                snapshot,
            )
