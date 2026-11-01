from dataclasses import replace
from threading import Event
from unittest.mock import Mock

import pytest

from garmin_database.adapters.outbound.filesystem.collector_files import CollectorFiles
from garmin_database.adapters.outbound.security.dpapi_session import SessionStore
from garmin_database.application.collector_models import CollectorState
from garmin_database.application.errors import CollectorLoginUnavailable
from garmin_database.bootstrap.collector import create_manager
from garmin_database.bootstrap.dependencies import Services


def setup(tmp_path):
    files = CollectorFiles(tmp_path / "collector.json")
    config = replace(files.defaults(tmp_path / "data"), run_as="synthetic-current")
    files.save_config(config)
    manager = create_manager(files, Mock(), manage_access=False)
    services = object.__new__(Services)
    services.current_account = lambda: "synthetic-current"
    services.collector_manager = lambda path: manager
    return services, manager, config


def test_other_account_and_missing_setup_never_receive_credentials(
    tmp_path, monkeypatch
):
    services, manager, config = setup(tmp_path)
    login = Mock(side_effect=AssertionError("No credentials may reach Garmin"))
    monkeypatch.setattr(manager, "login", login)
    manager.files.save_config(replace(config, run_as="another-account"))
    with pytest.raises(CollectorLoginUnavailable, match="konta zadania"):
        services.login_collector(None, "synthetic", "synthetic", None, Event(), None)
    manager.files.config_path.unlink()
    with pytest.raises(CollectorLoginUnavailable, match="Najpierw zapisz"):
        services.login_collector(None, "synthetic", "synthetic", None, Event(), None)
    login.assert_not_called()


def test_collector_login_keeps_gui_session_and_forwards_mfa_and_progress(
    tmp_path, monkeypatch
):
    from garmin_database.adapters.outbound.garmin import client
    from garmin_database.bootstrap import collector

    services, manager, config = setup(tmp_path)

    # Synthetic protector tests routing; real Windows DPAPI has its own test.
    def protect(value, decrypt=False):
        return value[::-1]

    gui = SessionStore(tmp_path / "gui/session.bin", protector=protect)
    gui.save("synthetic-gui")
    before = gui.path.read_bytes()
    store = SessionStore(config.session_path, protector=protect)
    monkeypatch.setattr(collector, "session_store", lambda config: store)
    manager.files.save_state(config, CollectorState(auth_required=True))

    class Source:
        def __init__(self, session):
            self.session = session

        def login(self, email, password, mfa, *, stop, progress):
            assert mfa() == "synthetic-mfa"
            progress("session_save")
            self.session.save("synthetic-collector")
            progress("ready")

    monkeypatch.setattr(client, "GarminSource", Source)
    stages = []
    assert (
        services.login_collector(
            None,
            "synthetic",
            "synthetic",
            lambda: "synthetic-mfa",
            Event(),
            stages.append,
        )
        == "login"
    )
    assert gui.path.read_bytes() == before and gui.load() == "synthetic-gui"
    assert store.load() == "synthetic-collector"
    assert stages == ["session_save", "ready"]
    assert not manager.files.load_state(config).auth_required
