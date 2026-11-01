"""Garmin HTTP details are translated at the outgoing adapter boundary."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from garmin_database.adapters.outbound.garmin.client import GarminSource
from garmin_database.application.errors import DownloadFailed
from garmin_database.application.use_cases.synchronize import error_status

pytestmark = pytest.mark.unit


def test_source_exposes_only_structured_failure_and_retry_delay():
    error = RuntimeError("HTTP 503 private response and credentials")
    error.response = SimpleNamespace(status_code=503, headers={"Retry-After": "15"})
    source = GarminSource(Mock())
    source.api = SimpleNamespace(download_health_snapshot=Mock(side_effect=error))
    with pytest.raises(DownloadFailed) as caught:
        source.download_health_snapshot("2024-01-01")
    assert caught.value.http_status == 503
    assert caught.value.retry_after_seconds == 15
    assert "private" not in str(caught.value)
    assert not hasattr(caught.value, "response")


def test_core_does_not_interpret_provider_error_text():
    assert error_status(RuntimeError("HTTP 401")) is None
    assert error_status(DownloadFailed(401)) == 401


@pytest.mark.parametrize(
    "status,delay", [(True, True), ("401", "15"), (999, float("nan")), (None, -1)]
)
def test_failure_contract_discards_invalid_transport_metadata(status, delay):
    failure = DownloadFailed(status, delay)
    assert failure.http_status is None and failure.retry_after_seconds is None
