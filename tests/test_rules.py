import threading
from datetime import date
from types import SimpleNamespace as Obj

import pytest
from fixtures import archive, fit_bytes

from garmin_database.auth import GarminSource, LoginFailed, SessionStore
from garmin_database.cli import main
from garmin_database.fit import (
    FIT_EPOCH,
    TimeResolver,
    json_value,
    typed_value,
)
from garmin_database.importer import Importer
from garmin_database.query import Queries, decode_value, group
from garmin_database.storage import Database
from garmin_database.sync import Sync, error_status

pytestmark = pytest.mark.unit


def frame(number, values, offset=None):
    return Obj(
        global_mesg_num=number,
        time_offset=offset,
        fields=[
            Obj(def_num=k, raw_value=v, field_def=Obj(is_dev=False))
            for k, v in values.items()
        ],
    )


@pytest.mark.parametrize(
    "bits,num,basis", [(16, 26, "timestamp_16"), (8, 25, "timestamp_min_8")]
)
@pytest.mark.parametrize("delta", [0, 1, 30, 60, 120, 300])
def test_short_timestamps(bits, num, basis, delta):
    r = TimeResolver()
    r.last = 1100000000
    future = r.last + delta
    multiplier = 60 if bits == 8 else 1
    result = r.resolve(frame(55, {num: (future // multiplier) & ((1 << bits) - 1)}), {})
    assert result[0] == (future // multiplier * multiplier + FIT_EPOCH) * 1000
    assert result[1] == basis


@pytest.mark.parametrize("offset", [0, 1, 15, 30, 31])
def test_compressed_timestamp(offset):
    r = TimeResolver()
    r.last = 1100000031
    stamp, basis, _ = r.resolve(frame(55, {}, offset), {})
    expected = (r.last + FIT_EPOCH) * 1000
    assert stamp == expected and basis == "compressed_header"


def test_unknown_compressed_time():
    assert TimeResolver().resolve(frame(55, {}, 1), {}) == (None, "unknown", None)


@pytest.mark.parametrize(
    "name", ["timestamp", "stress_level_time", "start_time", "end_time"]
)
def test_full_and_associated_time(name):
    t, b, f = TimeResolver().resolve(
        frame(227, {1: 1100000000}),
        {1: {"variant_name": name, "time_role": "utc_timestamp"}},
    )
    assert t == (1100000000 + FIT_EPOCH) * 1000
    assert b == ("explicit_utc" if name == "timestamp" else "associated_field")


@pytest.mark.parametrize("value", [-(2**63), 2**63 - 1, 2**63, 2**64 - 2])
def test_integer_precision(value):
    row = typed_value(value)
    assert row[1] == value if row[0] == "integer" else int(row[3]) == value


def test_invalid_array_and_large_integer():
    assert json_value([1, float("inf"), 2**64 - 1]) == [
        1,
        None,
        {"integer_text": str(2**64 - 1)},
    ]
    with pytest.raises(TypeError):
        typed_value(object())


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_status_detection(status):
    assert error_status(Obj(response=Obj(status_code=status))) == status
    assert error_status(RuntimeError(f"HTTP {status}")) == status


@pytest.mark.parametrize(
    "message,category",
    [
        ("sleep_level", "Sen"),
        ("hrv_value", "Serce i HRV"),
        ("stress_level", "Stres"),
        ("respiration_rate", "Oddychanie i saturacja"),
        ("monitoring", "Ruch"),
        ("skin_temp_overnight", "Pozostałe"),
    ],
)
def test_groups(message, category):
    assert group(message) == category


@pytest.mark.parametrize(
    "kind,source,expected",
    [
        ("integer", 128, 1),
        ("real", 64.0, 0.5),
        ("text", "abc", "abc"),
        ("null", None, None),
        ("integer_text", str(2**64 - 1), {"integer_text": str(2**64 - 1)}),
    ],
)
def test_export_value_kinds(kind, source, expected):
    row = dict(
        value_kind=kind,
        integer_value=source,
        real_value=source,
        text_value=source,
        json_value=None,
    )
    assert (
        decode_value(row, {"scale": 128, "offset": 0, "time_role": "none"}) == expected
    )


def test_login_does_not_persist_password(tmp_path):
    class Api:
        def __init__(self, **kwargs):
            self.password = kwargs["password"]
            self.client = Obj(dumps=lambda: '{"token":"mock"}')

        def login(self, token):
            assert token == "{}"

        def download_health_snapshot(self, day):
            return b"zip"

    store = SessionStore(tmp_path / "session", lambda b, decrypt=False: b[::-1])
    source = GarminSource(store, Api)
    source.login("email", "secret")
    assert source.api.password is None and "secret" not in store.load()
    assert source.download_health_snapshot("2024-01-01") == b"zip"


def test_login_failure_clears_password(tmp_path):
    instances = []

    class Api:
        def __init__(self, **kwargs):
            self.password = kwargs["password"]
            instances.append(self)

        def login(self, token):
            raise ValueError("private response")

    source = GarminSource(SessionStore(tmp_path / "session"), Api)
    with pytest.raises(LoginFailed):
        source.login("email", "secret")
    assert instances[0].password is None


@pytest.mark.integration
def test_components_and_subfield_scale(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    # walking cycles field is steps (scale 1), not cycles (scale 2).
    raw = fit_bytes(
        55,
        [(253, 4, 134), (3, 4, 134), (5, 1, 2), (24, 1, 2)],
        [(1100000000, 100, 6, 70)],
    )
    assert Importer(db).archive(archive(tmp_path, payload=raw)) == 0
    q = Queries(db)
    params = q.parameters()
    steps = next(p for p in params if p["key"].endswith(".steps"))
    intensity = next(p for p in params if p["key"].endswith(".intensity"))
    rows = list(q.rows(steps, date(2024, 1, 1), date(2025, 1, 1)))
    assert rows[0]["value"] == 100
    rows = list(q.rows(intensity, date(2024, 1, 1), date(2025, 1, 1)))
    assert rows[0]["value"] == 2  # packed source component, SDK scale 1


@pytest.mark.integration
@pytest.mark.parametrize("status", [401, 403, 404, 429])
def test_sync_http_failures(tmp_path, status):
    class Source:
        calls = 0

        def download_health_snapshot(self, day):
            self.calls += 1
            raise RuntimeError(f"HTTP {status}")

    source = Source()
    db = Database(tmp_path)
    errors = Sync(db, source, 0).run(
        date(2024, 1, 1), date(2024, 1, 2), threading.Event()
    )
    assert errors > 0
    assert source.calls == (2 if status == 404 else 1)
    if status == 404:
        Sync(db, source, 0).run(date(2024, 1, 1), date(2024, 1, 2), threading.Event())
        assert source.calls == 2


@pytest.mark.integration
def test_cli_status_and_export(tmp_path, capsys):
    db = Database(tmp_path / "data")
    db.initialize()
    Importer(db).archive(archive(db.root))
    assert main(["status", "--data-dir", str(db.root)]) == 0
    assert (
        main(
            [
                "export",
                "--data-dir",
                str(db.root),
                "--output",
                str(tmp_path / "out"),
                "--from",
                "2024-01-01",
                "--to",
                "2025-01-01",
                "--recent-days",
                "500",
            ]
        )
        == 0
    )
    assert (
        main(["export", "--data-dir", str(db.root), "--parameters", "doesnotexist"])
        == 1
    )


@pytest.mark.parametrize("name", ["../../secret", "a/b", "a\\b", ".hidden", "x" * 200])
def test_export_names_stay_in_folder(name):
    from pathlib import Path

    from garmin_database.exporter import parameter_filename

    result = parameter_filename(name)
    assert (
        Path(result).name == result and len(result) < 160 and not result.startswith(".")
    )
