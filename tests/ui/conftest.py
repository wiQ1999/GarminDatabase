"""UI tests never inspect or change the user's native task scheduler."""

import pytest

from garmin_database.bootstrap.collector import create_manager
from garmin_database.bootstrap.dependencies import Services


class OfflineScheduler:
    def status(self, config):
        return {"installed": False, "enabled": False, "revision_matches": False}

    def apply(self, config):
        raise AssertionError(
            "Native registration must be explicitly mocked in UI tests"
        )


@pytest.fixture(autouse=True)
def isolated_scheduler(monkeypatch):
    def manager(services, path=None):
        return create_manager(path, scheduler=OfflineScheduler(), manage_access=False)

    monkeypatch.setattr(Services, "collector_manager", manager)
