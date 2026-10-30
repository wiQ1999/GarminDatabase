"""Frozen Windows help must also work when output is redirected to a pipe."""

import sys
from io import BytesIO, TextIOWrapper

import pytest

from garmin_database.bootstrap.collector import main

pytestmark = pytest.mark.unit


def test_help_reconfigures_legacy_windows_encoding_without_wrapping(monkeypatch):
    buffer = BytesIO()
    stream = TextIOWrapper(buffer, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
    assert sys.stdout is stream and stream.encoding == "utf-8"
    stream.flush()
    assert "ścieżka" in buffer.getvalue().decode("utf-8")
    stream.detach()
