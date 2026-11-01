"""Collector orchestration depends on application ports, not native adapters."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from garmin_database.application.collector_models import CollectorState
from garmin_database.application.use_cases.manage_collector import CollectorManager

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("action", ["apply", "install"])
@pytest.mark.parametrize("privileged", [False, True])
def test_applied_state_is_published_by_its_owner_once(action, privileged):
    files, scheduler, registration = Mock(), Mock(), Mock()
    files.lock.return_value = nullcontext()
    files.load_state.return_value = CollectorState()
    getattr(registration, action).return_value = privileged
    config = Mock(revision="synthetic revision")
    manager = CollectorManager(
        files,
        scheduler,
        registration=registration,
        runtime_factory=Mock(),
        source_factory=Mock(),
    )
    getattr(manager, action)(config)
    if privileged:
        files.save_state.assert_not_called()
        registration.after_applied.assert_not_called()
    else:
        state = files.save_state.call_args.args[1]
        assert state.applied_revision == config.revision
        registration.after_applied.assert_called_once_with(config)
