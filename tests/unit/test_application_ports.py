"""Use cases operate on ports without SQL, filesystem or Garmin access."""

from contextlib import contextmanager
from datetime import date
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.application.settings import Settings
from garmin_database.application.use_cases.export_data import Exporter
from garmin_database.application.use_cases.login import Login
from garmin_database.application.use_cases.synchronize import Sync
from garmin_database.domain.cancellation import Cancelled

pytestmark = pytest.mark.unit


@contextmanager
def context(value=None):
    yield value


def test_local_import_is_orchestrated_without_network_or_sql():
    repository, archives, importer, source = Mock(), Mock(), Mock(), Mock()
    repository.writer_lock.side_effect = context
    archives.restore_manifest.return_value = {}
    archives.exists.return_value = True
    importer.archive.return_value = 0
    service = Sync(repository, archives, importer, source, delay=0)
    assert (
        service.run(date(2024, 1, 1), date(2024, 1, 1), Event(), local_only=True) == 0
    )
    importer.archive.assert_called_once()
    source.download_health_snapshot.assert_not_called()
    repository.initialize.assert_called_once()


def test_fit_errors_do_not_stop_successful_downloads_after_five_days():
    from tests.support.fixtures import zip_bytes

    repository, archives, importer, source = Mock(), Mock(), Mock(), Mock()
    repository.writer_lock.side_effect = context
    repository.day.return_value = None
    archives.restore_manifest.return_value = {}
    downloaded = set()
    archives.exists.side_effect = lambda day: day in downloaded
    archives.save.side_effect = lambda day, payload: downloaded.add(day)
    source.download_health_snapshot.return_value = zip_bytes()
    importer.archive.return_value = 1
    service = Sync(repository, archives, importer, source, delay=0)
    assert service.run(date(2024, 1, 1), date(2024, 1, 6), Event()) == 6
    assert source.download_health_snapshot.call_count == 6


def test_login_uses_new_client_and_honors_cancellation():
    factory = Mock()
    service, stop = Login(factory), Event()
    for _ in range(2):
        assert service.run("synthetic", "synthetic", None, stop, None) == "login"
    assert factory.call_count == 2
    stop.set()
    with pytest.raises(Cancelled):
        service.run("synthetic", "synthetic", None, stop, None)
    assert factory.call_count == 2


def test_export_passes_only_canonical_selection_and_one_snapshot_to_sink():
    canonical = {"key": "monitoring.heart_rate", "unit": "bpm"}
    snap = SimpleNamespace(catalog=[canonical], select=Mock(return_value=[canonical]))
    readings = SimpleNamespace(snapshot=lambda stop: context(snap))
    sink, store = Mock(), Mock()
    settings = Settings(settings_version=2, export_parameters=[canonical["key"]])
    result = Exporter(readings, sink, settings, store).generate(
        "unused",
        [{"key": canonical["key"], "ids": [999]}],
        date(2024, 1, 1),
        date(2024, 1, 1),
    )
    assert result is sink.generate.return_value
    assert sink.generate.call_args.args[1] == [canonical]
    assert sink.generate.call_args.args[-1] is snap
    store.save.assert_not_called()


def test_settings_adapter_persists_the_plain_application_model(tmp_path):
    from garmin_database.adapters.outbound.filesystem.settings_json import SettingsStore

    store, path = SettingsStore(), tmp_path / "settings.json"
    settings = Settings(data_dir="synthetic-data", export_dir="synthetic-exports")
    store.save(settings, path)
    loaded = store.load(path)
    assert loaded.data_dir == settings.data_dir
    assert loaded.export_dir == settings.export_dir


def test_login_diagnostic_rejects_unknown_categories_and_unstructured_status():
    from garmin_database.application.errors import LoginFailed

    error = LoginFailed("unknown", "synthetic-private-input", "synthetic-status")
    assert error.code == "CONNECT/CLIENT_ERROR"
    assert error.http_status is None
    assert "synthetic" not in str(error)
