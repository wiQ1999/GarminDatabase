"""Composition root for desktop/CLI. Architecture: docs/03-architecture.md."""

from garmin_database.adapters.outbound.filesystem.archives import Archives
from garmin_database.adapters.outbound.filesystem.json_export import JSONExport
from garmin_database.adapters.outbound.filesystem.settings_json import (
    SettingsStore,
)
from garmin_database.adapters.outbound.garmin.client import GarminSource
from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.import_days import ImportDays
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.adapters.outbound.postgres.queries import Queries
from garmin_database.adapters.outbound.postgres.readings import DataAccess
from garmin_database.adapters.outbound.security.dpapi_session import SessionStore
from garmin_database.application.use_cases.export_data import Exporter as ExportData
from garmin_database.application.use_cases.login import Login
from garmin_database.application.use_cases.synchronize import Sync as Synchronize


def create_sync(db, source=None, delay=3.0):
    return Synchronize(ImportDays(db), Archives(db.root), Importer(db), source, delay)


def create_exporter(db, settings=None, settings_path=None):
    store = SettingsStore()
    return ExportData(
        DataAccess(db),
        JSONExport(db.root),
        settings or store.load(settings_path),
        store,
        settings_path,
    )


def create_source():
    return GarminSource(SessionStore())


class Services:
    def __init__(self, settings):
        self.settings_store = SettingsStore()
        self.source_factory = lambda: create_source()
        self.session_factory = lambda: SessionStore()
        self.prepare(settings)

    def prepare(self, settings):
        db = Database(settings.data_dir, settings.database_dsn)
        with db.writer_lock():
            db.initialize()
        self.db = db
        self.queries = Queries(db)

    def reconfigure(self, settings):
        return Services(settings)

    def status(self):
        return self.db.status()

    def session_available(self):
        return self.session_factory().path.is_file()

    def login(self, email, password, mfa, stop, progress):
        return Login(self.source_factory).run(email, password, mfa, stop, progress)

    def parameters(self):
        return self.queries.parameters()

    def chart(self, parameter, start, end):
        return self.queries.chart(parameter, start, end)

    def sync(
        self, start, end, stop, progress, local_only=False, force=False, delay=3.0
    ):
        return create_sync(
            self.db, None if local_only else self.source_factory(), delay
        ).run(
            start,
            end,
            stop,
            progress,
            local_only,
            force,
        )

    def export(self, settings, settings_path=None):
        return create_exporter(self.db, settings, settings_path)
