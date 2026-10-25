"""Bulk SQL must preserve physical values, transaction boundaries and source order."""

import json
import struct
import threading
from datetime import date
from zipfile import ZipFile

import psycopg
import pytest
from fitdecode.utils import compute_crc

from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.adapters.outbound.postgres.message_batch import MessageBatch
from garmin_database.adapters.outbound.postgres.queries import Queries
from garmin_database.bootstrap.dependencies import create_sync
from garmin_database.domain.aggregation import aggregate_days
from garmin_database.domain.cancellation import Cancelled
from tests.support.fixtures import archive, fit_bytes, zip_bytes

pytestmark = pytest.mark.integration


def many_records(count=20):
    return fit_bytes(
        values=[
            (1100000000 + i, 60 + i % 30, (43776 + i) % 65536, i) for i in range(count)
        ]
    )


def test_crc_after_several_written_batches_rolls_back_all_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(MessageBatch, "max_messages", 2)
    db = Database(tmp_path)
    db.initialize()
    payload = many_records()
    payload = payload[:-1] + bytes([payload[-1] ^ 1])
    flushed = []
    flush = MessageBatch.flush

    def track(batch):
        flush(batch)
        count = batch.conn.execute("SELECT count(*) FROM fit_messages").fetchone()[0]
        flushed.append(count)

    monkeypatch.setattr(MessageBatch, "flush", track)
    assert Importer(db).archive(archive(tmp_path, payload=payload)) == 1
    assert max(flushed) >= 2
    with db.connect(readonly=True) as c:
        assert c.execute("SELECT count(*) FROM fit_messages").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM fit_fields").fetchone()[0] == 0
        assert c.execute("SELECT status FROM file_decodes").fetchone()[0] == "failed"


def test_cancel_after_flush_restores_old_decode_revision_and_summary(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(MessageBatch, "max_messages", 2)
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path, payload=many_records())
    importer = Importer(db)
    assert importer.archive(path) == 0
    with db.connect(readonly=True) as c:
        before = c.execute("SELECT id,stored_field_count FROM file_decodes").fetchone()
        revision = c.execute("SELECT revision FROM dataset_state").fetchone()[0]
    stop = threading.Event()
    flush = MessageBatch.flush
    flushed = []

    def cancel_after_write(batch):
        flush(batch)
        flushed.append(True)
        # Other readers still observe the previous committed result.
        assert db.status()["fields"] == 80
        stop.set()

    monkeypatch.setattr(MessageBatch, "flush", cancel_after_write)
    with pytest.raises(Cancelled):
        importer.archive(path, stop=stop, force=True)
    assert flushed
    with db.connect(readonly=True) as c:
        assert (
            c.execute("SELECT id,stored_field_count FROM file_decodes").fetchone()
            == before
        )
        assert c.execute("SELECT revision FROM dataset_state").fetchone()[0] == revision


def test_returning_order_does_not_pair_fields_with_the_wrong_message(
    tmp_path, monkeypatch
):
    initialize = MessageBatch.__init__

    class ReversedReturning:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, query, params):
            result = self.conn.execute(query, params)
            return list(reversed(result.fetchall()))

        def cursor(self):
            return self.conn.cursor()

    def reverse_results(batch, conn, check):
        initialize(batch, conn, check)
        batch.conn = ReversedReturning(conn)

    monkeypatch.setattr(MessageBatch, "__init__", reverse_results)
    db = Database(tmp_path)
    db.initialize()
    assert Importer(db).archive(archive(tmp_path, payload=many_records())) == 0
    with db.connect(readonly=True) as c:
        rows = c.execute("""SELECT m.message_index,f.integer_value FROM fit_fields f
            JOIN fit_messages m ON m.id=f.message_id JOIN field_catalog c ON c.id=f.resolved_catalog_id
            WHERE c.variant_name='heart_rate' ORDER BY m.message_index""").fetchall()
    assert rows == [(i, 60 + i) for i in range(20)]


def test_copy_preserves_arrays_null_positions_utf8_and_uint64(tmp_path, monkeypatch):
    monkeypatch.setattr(MessageBatch, "max_messages", 1)
    text = "café\t\\\n"
    definition = b"\x40\x00\x00" + struct.pack("<H", 65500) + bytes([4])
    definition += bytes([0, 4, 2, 1, 16, 7, 2, 8, 143, 3, 4, 136])
    record = bytes([0, 1, 255, 3, 4]) + text.encode().ljust(16, b"\0")
    record += struct.pack("<Qf", 2**64 - 2, 1.25)
    body = definition + record
    header = struct.pack("<BBHI4s", 14, 0x20, 21800, len(body), b".FIT")
    header += struct.pack("<H", compute_crc(header))
    payload = header + body
    payload += struct.pack("<H", compute_crc(payload))
    db = Database(tmp_path)
    db.initialize()
    assert Importer(db).archive(archive(tmp_path, payload=payload)) == 0
    with db.connect(readonly=True) as c:
        rows = c.execute("""SELECT f.value_kind,f.json_value,f.text_value,f.real_value,f.validity
            FROM fit_fields f JOIN field_definitions d ON d.id=f.field_definition_id
            ORDER BY d.field_order""").fetchall()
    assert rows[0][0] == "json" and json.loads(rows[0][1]) == [1, None, 3, 4]
    assert rows[0][4] == "partial_invalid"
    assert rows[1][2] == text
    assert rows[2][0] == "integer_text" and rows[2][2] == str(2**64 - 2)
    assert rows[3][3] == 1.25


def test_sql_failure_does_not_mark_valid_original_as_corrupt(tmp_path, monkeypatch):
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path)
    importer = Importer(db)
    assert importer.archive(path) == 0

    def fail(*args):
        raise psycopg.IntegrityError("synthetic-private-SQL")

    monkeypatch.setattr(importer, "decode", fail)
    assert importer.archive(path, force=True) == 1
    with db.connect(readonly=True) as c:
        assert (
            c.execute("SELECT integrity_status FROM fit_files").fetchone()[0] == "valid"
        )
        assert c.execute("SELECT status FROM file_decodes").fetchone()[0] == "complete"
    assert db.status()["fields"] == 8


def test_all_origins_are_visible_before_first_fit_and_day_remains_partial(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path)
    with ZipFile(path, "a") as z:
        z.writestr("second_WELLNESS.fit", many_records(3))
    pending = []

    def progress(day, stage, *args):
        if stage == "Rozpoczynanie importu FIT":
            with db.connect(readonly=True) as c:
                assert (
                    c.execute("SELECT count(*) FROM archive_entries").fetchone()[0] == 2
                )
            pending.append(
                Queries(db).coverage(date(2024, 6, 19), date(2024, 6, 19))[
                    "decode_status"
                ]
            )

    assert Importer(db).archive(path, progress=progress) == 0
    assert pending == ["partial", "partial"]
    assert (
        Queries(db).coverage(date(2024, 6, 19), date(2024, 6, 19))["decode_status"]
        == "complete"
    )


def test_completed_identical_archive_does_not_decompress_again(tmp_path, monkeypatch):
    db = Database(tmp_path)
    db.initialize()
    path = archive(tmp_path)
    importer = Importer(db)
    importer.archive(path)

    def refuse(*args):
        pytest.fail("unchanged completed ZIP must not be decompressed")

    monkeypatch.setattr(ZipFile, "read", refuse)
    assert importer.archive(path) == 0


def test_non_parser_warning_does_not_mark_fit_partial(tmp_path, monkeypatch):
    import warnings

    from garmin_database.adapters.outbound.postgres.fit_decode import FitDecoder

    original = FitDecoder.frame

    def warning_from_another_library(decoder, *args):
        warnings.warn("synthetic-private-network-warning", UserWarning)
        return original(decoder, *args)

    monkeypatch.setattr(FitDecoder, "frame", warning_from_another_library)
    db = Database(tmp_path)
    db.initialize()
    assert Importer(db).archive(archive(tmp_path)) == 0
    with db.connect(readonly=True) as conn:
        assert (
            conn.execute("SELECT status FROM file_decodes").fetchone()[0] == "complete"
        )
        assert conn.execute("SELECT count(*) FROM decode_issues").fetchone()[0] == 0


def test_parser_warning_marks_only_its_fit_partial_without_persisting_text(
    tmp_path, monkeypatch
):
    import warnings

    import fitdecode

    from garmin_database.adapters.outbound.postgres.fit_decode import FitDecoder

    original = FitDecoder.frame

    def parser_warning(decoder, *args):
        warnings.warn_explicit(
            "synthetic-private-parser-details", UserWarning, fitdecode.__file__, 1
        )
        return original(decoder, *args)

    monkeypatch.setattr(FitDecoder, "frame", parser_warning)
    db = Database(tmp_path)
    db.initialize()
    assert Importer(db).archive(archive(tmp_path)) == 0
    with db.connect(readonly=True) as conn:
        assert (
            conn.execute("SELECT status FROM file_decodes").fetchone()[0] == "partial"
        )
        issues = conn.execute("SELECT context_json FROM decode_issues").fetchall()
    assert issues and all(
        json.loads(row[0]) == {"category": "UserWarning"} for row in issues
    )


def test_pipeline_keeps_cross_day_measurements_and_duplicate_fits(tmp_path):
    db = Database(tmp_path)
    # FIT epoch time 1100000000 is in November; requested June dates must never
    # replace its measurement time, and an identical later FIT counts once.
    first = fit_bytes(values=[(1100000000, 60, 43776, 1), (1100000060, 80, 43836, 2)])
    second = fit_bytes(values=[(1100000060, 100, 43836, 3)])

    class Source:
        def download_health_snapshot(self, day):
            return zip_bytes(second if day == "2024-06-20" else first)

    assert (
        create_sync(db, Source(), 0).run(
            date(2024, 6, 19), date(2024, 6, 21), threading.Event()
        )
        == 0
    )
    query = Queries(db)
    p = next(p for p in query.parameters() if p["key"] == "monitoring.heart_rate")
    rows = list(query.rows(p, date(2024, 11, 1), date(2024, 11, 30)))
    summary = aggregate_days(rows, p)
    assert len(rows) == 3 and summary[0]["mean"] == 80
    assert summary[0]["last_value"] == 100
    assert db.status()["files"] == 2 and db.status()["archives"] == 3


def test_cancelled_prefetch_pacing_refunds_only_the_unstarted_attempt(
    tmp_path, monkeypatch
):
    from garmin_database.application.use_cases.download_ahead import DownloadAhead

    db, stop = Database(tmp_path), threading.Event()
    start, import_zip = DownloadAhead.start, Importer.archive
    requests = []

    def delayed_second(ahead, day, delay):
        start(ahead, day, 60 if day == "2024-06-20" else 0)

    def finish_first(importer, *args, **kwargs):
        result = import_zip(importer, *args, **kwargs)
        stop.set()
        return result

    monkeypatch.setattr(DownloadAhead, "start", delayed_second)
    monkeypatch.setattr(Importer, "archive", finish_first)

    class Source:
        def download_health_snapshot(self, day):
            requests.append(day)
            return zip_bytes()

    with pytest.raises(Cancelled):
        create_sync(db, Source(), 0).run(date(2024, 6, 19), date(2024, 6, 20), stop)
    assert requests == ["2024-06-19"]
    with db.connect(readonly=True) as conn:
        assert conn.execute(
            "SELECT attempts FROM import_days ORDER BY day"
        ).fetchall() == [(1,), (0,)]
    assert db.status()["fields"] == 8
