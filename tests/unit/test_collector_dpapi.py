"""Native DPAPI roundtrip runs on Windows without depending on PostgreSQL."""

import os

import pytest

from garmin_database.adapters.outbound.security.dpapi_session import SessionStore

pytestmark = pytest.mark.unit


@pytest.mark.skipif(os.name != "nt", reason="Real DPAPI requires Windows")
def test_collector_native_dpapi_under_current_windows_identity(tmp_path):
    store = SessionStore(tmp_path / "auth/session.bin")
    with store.lock():
        store.save("synthetic-session-for-native-dpapi")
        assert store.load() == "synthetic-session-for-native-dpapi"
    assert b"synthetic-session-for-native-dpapi" not in store.path.read_bytes()
