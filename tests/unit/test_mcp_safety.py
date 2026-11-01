"""Cancellation and unexpected errors must not cross request boundaries."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import anyio
import pytest

from garmin_database.adapters.inbound.mcp.server import call
from garmin_database.application.errors import AccessError
from garmin_database.application.settings import Settings
from garmin_database.application.use_cases.read_health import MCPData

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "error,visible",
    [
        (ValueError("private response"), False),
        (AccessError("Sprawdź ustawienia"), True),
    ],
)
def test_only_controlled_errors_are_published(error, visible):
    service = SimpleNamespace(catalog=Mock(side_effect=error))

    async def invoke():
        return await call(service, "garmin_catalog", {}, anyio.CapacityLimiter(1))

    result = anyio.run(invoke)
    assert result.isError
    assert "private response" not in result.content[0].text
    assert (str(error) in result.content[0].text) is visible


def test_cancelled_queued_request_does_not_overlap_an_active_snapshot():
    entered, release, queued, cancelled = Event(), Event(), Event(), Event()
    settings = Settings(settings_version=2, export_parameters=[], mcp_enabled=True)
    loads = []

    def load(path):
        loads.append(path)
        if len(loads) == 2:
            queued.set()
        return settings

    @contextmanager
    def snapshot(budget):
        entered.set()
        assert release.wait(5)
        yield SimpleNamespace(identity=[], revision=1, catalog=[], policy_revision=None)

    factory = Mock(return_value=SimpleNamespace(snapshot=snapshot))
    service = MCPData(
        settings_store=SimpleNamespace(load=load), readings_factory=factory
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.catalog)
        try:
            assert entered.wait(2)
            second = executor.submit(service.catalog, stop=cancelled)
            assert queued.wait(2)
            cancelled.set()
            with pytest.raises(AccessError, match="Anulowano"):
                second.result(timeout=2)
            assert factory.call_count == 1
        finally:
            release.set()
        assert first.result(timeout=2)["metrics"] == []
    assert service.catalog()["metrics"] == []
