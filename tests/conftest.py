import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_application_settings(tmp_path, monkeypatch):
    """Tests never read or update the Windows user's real preferences or session."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
