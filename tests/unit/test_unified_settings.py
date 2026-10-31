import json
from dataclasses import replace

import pytest

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.filesystem.settings_json import Settings


def test_shared_document_preserves_both_editors_and_has_single_connection(tmp_path):
    path = tmp_path / "settings.json"
    Settings(data_dir=str(tmp_path / "data"), database_dsn="host=first").save(path)
    stale = Settings.load(path)
    files = CollectorFiles(path)
    config = files.defaults(tmp_path / "data", None, settings_path=path)
    files.save_config(replace(config, run_as="synthetic", interval_minutes=30))
    stale.refresh_seconds = 45
    stale.save(path)
    value = json.loads(path.read_text())
    assert value["collector"]["interval_minutes"] == 30
    assert "database_dsn" not in value["collector"]
    assert "download_from" not in value["collector"]
    assert files.resolve_settings(files.load_config()).database_dsn == "host=first"
    files.save_config(replace(files.load_config(), enabled=True))
    assert Settings.load(path).refresh_seconds == 45


@pytest.mark.parametrize("value", [0, 4, 3601, True, 1.5])
def test_refresh_rejects_invalid_intervals(value):
    with pytest.raises(ValueError):
        Settings(refresh_seconds=value).validate()


def test_legacy_collector_is_visible_before_first_save_without_mutation(tmp_path):
    path = tmp_path / "settings.json"
    Settings(data_dir=str(tmp_path / "data")).save(path)
    legacy = CollectorFiles(tmp_path / "collector.json")
    legacy.save_config(replace(legacy.defaults(tmp_path / "data"), run_as="old-user"))
    before = path.read_bytes(), legacy.config_path.read_bytes()
    files = CollectorFiles(path)
    config = files.load_config()
    assert config.run_as == "old-user" and config.settings_path == str(path)
    assert before == (path.read_bytes(), legacy.config_path.read_bytes())
    files.save_config(config)
    assert Settings.load(path).collector["run_as"] == "old-user"
    assert legacy.config_path.read_bytes() == before[1]
