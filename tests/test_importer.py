import threading
from datetime import date

import pytest
from fixtures import archive, fit_bytes, zip_bytes

from garmin_database.fit import typed_value
from garmin_database.importer import Importer
from garmin_database.storage import Database
from garmin_database.sync import Sync
from garmin_database.util import Cancelled


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,kind,validity",
    [
        (None, "null", "invalid"),
        (62, "integer", "valid"),
        (2**64 - 2, "integer_text", "valid"),
        (1.5, "real", "valid"),
        (float("nan"), "null", "invalid"),
        ("x", "text", "valid"),
        ([1, None], "json", "partial_invalid"),
        (bytes([1, 2]), "json", "valid"),
    ],
)
def test_values(value, kind, validity):
    row = typed_value(value)
    assert row[0] == kind and row[-1] == validity


@pytest.mark.integration
def test_import_and_reprocess(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    p = archive(tmp_path)
    importer = Importer(db)
    assert importer.archive(p) == 0
    before = db.status()
    assert (
        before["messages"] == 2
        and before["fields"] == 8
        and before["unknown_variants"] == 1
    )
    assert importer.archive(p) == 0
    assert db.status()["fields"] == 8
    assert importer.archive(p, force=True) == 0
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM file_decodes").fetchone()[0] == 1
        assert [
            x[0]
            for x in c.execute(
                "SELECT value FROM v_numeric_parameters WHERE variant_name='heart_rate' ORDER BY message_index"
            )
        ] == [62, 64]
        assert (
            c.execute(
                "SELECT count(*) FROM fit_fields f LEFT JOIN fit_messages m ON m.id=f.message_id WHERE m.id IS NULL"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.integration
def test_bad_crc_has_no_partial_rows(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    raw = fit_bytes()
    raw = raw[:-1] + bytes([raw[-1] ^ 1])
    stages = []
    assert (
        Importer(db).archive(
            archive(tmp_path, payload=raw),
            progress=lambda day, stage, index, total: stages.append(stage),
        )
        == 1
    )
    assert any(
        "Błąd importu FIT" in stage and "FitCRCError" in stage for stage in stages
    )
    assert db.status()["messages"] == 0


@pytest.mark.integration
def test_duplicate_fits_across_archives(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    i = Importer(db)
    i.archive(archive(tmp_path, "2024-06-19"))
    i.archive(archive(tmp_path, "2024-06-20"))
    assert db.status()["fields"] == 8 and db.status()["archives"] == 2


@pytest.mark.integration
def test_stop_before_import(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    stop = threading.Event()
    stop.set()
    with pytest.raises(Cancelled):
        Importer(db).archive(archive(tmp_path), stop)
    assert db.status()["messages"] == 0


@pytest.mark.integration
def test_sync_local_no_network(tmp_path):
    archive(tmp_path)
    db = Database(tmp_path)
    assert (
        Sync(db).run(
            date(2024, 6, 19), date(2024, 6, 20), threading.Event(), local_only=True
        )
        == 0
    )
    assert db.status()["archives"] == 1


@pytest.mark.integration
def test_download_then_resume(tmp_path):
    class Source:
        calls = 0

        def download_health_snapshot(self, day):
            self.calls += 1
            return zip_bytes()

    s = Source()
    db = Database(tmp_path)
    sync = Sync(db, s, 0)
    sync.run(date(2024, 6, 19), date(2024, 6, 19), threading.Event())
    sync.run(date(2024, 6, 19), date(2024, 6, 19), threading.Event())
    assert s.calls == 1 and db.status()["fields"] == 8


@pytest.mark.integration
def test_redefined_local_messages_keep_semantic_context(tmp_path):
    import struct

    from fitdecode.utils import compute_crc

    bodies = []
    for index in range(300):
        number = 211 if index % 2 else 55
        part = fit_bytes(
            number, [(253, 4, 134), (0, 1, 2)], [(1100000000 + index, index % 100)]
        )
        bodies.append(part[14:-2])
    body = b"".join(bodies)
    header = struct.pack("<BBHI4s", 14, 0x20, 21800, len(body), b".FIT")
    header += struct.pack("<H", compute_crc(header))
    payload = header + body
    payload += struct.pack("<H", compute_crc(payload))
    db = Database(tmp_path)
    db.initialize()
    assert Importer(db).archive(archive(tmp_path, payload=payload)) == 0
    with db.connect(readonly=True) as c:
        mismatches = c.execute("""SELECT count(*) FROM fit_fields f
            JOIN field_catalog c ON c.id=f.resolved_catalog_id
            JOIN fit_messages m ON m.id=f.message_id
            JOIN message_definitions d ON d.id=m.message_definition_id
            WHERE c.message_num<>d.global_message_num""").fetchone()[0]
    assert mismatches == 0 and db.status()["fields"] == 600
