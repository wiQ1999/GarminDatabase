"""Transactional archive registration and FIT import; docs/04-synchronization.md."""

import importlib.metadata
from hashlib import file_digest, sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import fitdecode

from garmin_database.adapters.outbound.postgres.fit_decode import FitDecoder
from garmin_database.application.archive_payload import ArchivePayload
from garmin_database.domain.cancellation import Cancelled, check_stop
from garmin_database.domain.time import utc_now
from garmin_database.domain.values import dumps


class Importer:
    def __init__(self, db):
        self.db = db

    def profile(self, conn):
        options = dumps(
            {
                "sdk": importlib.metadata.version("garmin-fit-sdk"),
                "raw": True,
                "rules_version": 1,
                "time": "FIT context; no archive timestamp inference",
            }
        )
        values = (
            "fitdecode",
            importlib.metadata.version("fitdecode"),
            importlib.metadata.version("garmin-fit-sdk"),
            options,
        )
        conn.execute(
            "INSERT INTO decoder_profiles(parser_name,parser_version,profile_version,options_json) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            values,
        )
        return conn.execute(
            "SELECT id FROM decoder_profiles WHERE parser_name=%s AND parser_version=%s AND profile_version=%s AND options_json=%s",
            values,
        ).fetchone()[0]

    def archive(
        self,
        path,
        stop=None,
        progress=lambda *a: None,
        force=False,
        origin="local_archive",
    ):
        with self.db.writer_lock():
            return self._archive(path, stop, progress, force, origin)

    def _archive(
        self,
        path,
        stop=None,
        progress=lambda *a: None,
        force=False,
        origin="local_archive",
    ):
        check_stop(stop)
        downloaded, day, relative, digest, size, source = self.archive_source(path)
        # Source bytes are owned by this invocation; no persistent network ZIP.
        with self.db.connect() as conn, ZipFile(source) as archive:
            previous = conn.execute(
                "SELECT id,sha256 FROM archives WHERE day=%s", (day,)
            ).fetchone()
            if previous and previous[1] != digest and not downloaded:
                raise ValueError("Zmienione archiwum źródłowe")
            profile = self.profile(conn)
            entries = [
                (i, item)
                for i, item in enumerate(archive.infolist())
                if not item.is_dir()
            ]
            if not downloaded and self.can_skip_archive(
                conn, previous, digest, profile, len(entries), force
            ):
                return 0
            aid = self.register_archive(
                conn, size, day, relative, digest, entries, origin
            )
            # Publish every origin before the first decoded FIT, so a reader
            # cannot mistake a partly registered day for a complete one.
            prepared = self.prepare_entries(conn, archive, aid, stop, downloaded)
            if self.download_complete(conn, aid, profile, downloaded, force):
                return 0
            run = conn.execute(
                "INSERT INTO decode_runs(profile_id,started_at,status) VALUES(%s,%s,'running') RETURNING id",
                (profile, utc_now()),
            ).fetchone()[0]
            conn.commit()
            return self.import_entries(
                conn, archive, prepared, day, aid, profile, run, stop, progress, force
            )

    def can_skip_archive(self, conn, previous, digest, profile, count, force):
        return bool(
            previous
            and previous[1] == digest
            and not force
            and self.complete(conn, previous[0], profile, count)
        )

    @staticmethod
    def download_complete(conn, aid, profile, downloaded, force):
        if not downloaded or force:
            return False
        return not conn.execute(
            """SELECT 1 FROM archive_entries e WHERE e.archive_id=%s AND NOT EXISTS(
            SELECT 1 FROM file_decodes d WHERE d.fit_file_id=e.fit_file_id AND d.profile_id=%s AND d.is_active=1 AND d.status='complete') LIMIT 1""",
            (aid, profile),
        ).fetchone()

    def archive_source(self, path):
        from datetime import date

        downloaded = isinstance(path, ArchivePayload)
        if downloaded:
            day = date.fromisoformat(path.day).isoformat()
            content = path.content
            relative = f"remote/{day}.zip"
            digest = sha256(content).hexdigest()
            size = len(content)
            source = BytesIO(content)
        else:
            path = Path(path)
            day = date.fromisoformat(path.stem).isoformat()
            relative = path.resolve().relative_to(self.db.root.resolve()).as_posix()
            with path.open("rb") as stream:
                digest = file_digest(stream, "sha256").hexdigest()
            size = path.stat().st_size
            source = path
        return downloaded, day, relative, digest, size, source

    @staticmethod
    def complete(conn, aid, profile, count):
        registered = conn.execute(
            "SELECT count(*) FROM archive_entries WHERE archive_id=%s", (aid,)
        ).fetchone()[0]
        incomplete = conn.execute(
            """SELECT 1 FROM archive_entries e WHERE e.archive_id=%s AND NOT EXISTS(
            SELECT 1 FROM file_decodes d WHERE d.fit_file_id=e.fit_file_id
            AND d.profile_id=%s AND d.is_active=1 AND d.status='complete') LIMIT 1""",
            (aid, profile),
        ).fetchone()
        return registered == count and not incomplete

    @staticmethod
    def register_archive(conn, size, day, relative, digest, entries, origin):
        conn.execute(
            "INSERT INTO import_days(day,download_status,checked_at) VALUES(%s,%s,%s) "
            "ON CONFLICT(day) DO UPDATE SET download_status=excluded.download_status",
            (day, "downloaded" if entries else "empty_zip", utc_now()),
        )
        conn.execute(
            "INSERT INTO archives(day,relative_path,sha256,size_bytes,acquired_at,acquisition_origin) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (day, relative, digest, size, utc_now(), origin),
        )
        return conn.execute("SELECT id FROM archives WHERE day=%s", (day,)).fetchone()[
            0
        ]

    def import_entries(
        self, conn, archive, entries, day, aid, profile, run, stop, progress, force
    ):
        failed = 0
        try:
            for index, item, fid, digest in entries:
                check_stop(stop)
                payload = archive.read(item)
                failed += self.import_file(
                    conn,
                    payload,
                    fid,
                    digest,
                    profile,
                    run,
                    stop,
                    progress,
                    day,
                    index + 1,
                    len(entries),
                    force,
                )
            conn.execute(
                "UPDATE decode_runs SET finished_at=%s,status=%s WHERE id=%s",
                (utc_now(), "partial" if failed else "complete", run),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            conn.execute(
                "UPDATE decode_runs SET finished_at=%s,status='interrupted' WHERE id=%s",
                (utc_now(), run),
            )
            conn.commit()
            raise
        return failed

    def prepare_entries(self, conn, archive, aid, stop, downloaded=False):
        prepared = []
        existing = dict(
            conn.execute(
                "SELECT entry_index,fit_file_id FROM archive_entries WHERE archive_id=%s",
                (aid,),
            )
        )
        known = (
            dict(
                conn.execute(
                    "SELECT f.sha256,e.fit_file_id FROM archive_entries e JOIN fit_files f ON f.id=e.fit_file_id WHERE e.archive_id=%s",
                    (aid,),
                )
            )
            if downloaded
            else {}
        )
        next_index = max(existing, default=-1) + 1
        for index, item in enumerate(archive.infolist()):
            check_stop(stop)
            # Read through EOF to verify ZIP CRC, also for unused directory entries.
            payload = archive.read(item)
            if item.is_dir():
                continue
            digest = sha256(payload).hexdigest()
            fid = known.get(digest) if downloaded else existing.get(index)
            entry_index = next_index if downloaded else index
            if fid is None:
                fid = self.register_entry(
                    conn, aid, entry_index, item.filename, digest, len(payload)
                )
                next_index += 1
                known[digest] = fid
            prepared.append((index, item, fid, digest))
        return prepared

    @staticmethod
    def register_entry(conn, aid, index, name, digest, size):
        conn.execute(
            "INSERT INTO fit_files(sha256,size_bytes,integrity_status) VALUES(%s,%s,'pending') ON CONFLICT DO NOTHING",
            (digest, size),
        )
        fid = conn.execute(
            "SELECT id FROM fit_files WHERE sha256=%s", (digest,)
        ).fetchone()[0]
        category = Path(name).stem.partition("_")[2] or "unknown"
        conn.execute(
            "INSERT INTO archive_entries(archive_id,entry_index,entry_name,category,fit_file_id) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (aid, index, name, category, fid),
        )
        return fid

    def import_file(
        self,
        conn,
        payload,
        fid,
        digest,
        profile,
        run,
        stop,
        progress,
        day,
        index,
        total,
        force,
    ):
        done = conn.execute(
            "SELECT status FROM file_decodes WHERE fit_file_id=%s AND profile_id=%s",
            (fid, profile),
        ).fetchone()
        force_file = force is True or isinstance(force, set) and fid in force
        if not force_file and done and done[0] == "complete":
            return 0
        progress(day, "Rozpoczynanie importu FIT", index, total)
        try:
            self.decode(conn, payload, fid, digest, profile, run, stop)
        except Cancelled:
            raise
        except Exception as error:
            conn.rollback()
            self.record_failure(conn, fid, profile, run, error)
            progress(
                day,
                f"Błąd importu FIT — {type(error).__name__}. Nieukończony zapis FIT wycofano. Pobieranie można ponowić.",
                index,
                total,
            )
            return 1
        return 0

    @staticmethod
    def record_failure(conn, fid, profile, run, error):
        old = conn.execute(
            "SELECT id FROM file_decodes WHERE fit_file_id=%s AND profile_id=%s",
            (fid, profile),
        ).fetchone()
        if not old:
            did = conn.execute(
                "INSERT INTO file_decodes(fit_file_id,profile_id,run_id,status,error_type) "
                "VALUES(%s,%s,%s,'failed',%s) RETURNING id",
                (fid, profile, run, type(error).__name__),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO decode_issues(file_decode_id,issue_code,severity,context_json) "
                "VALUES(%s,'fit_decode_failed','error',%s)",
                (did, dumps({"type": type(error).__name__})),
            )
        # SQL/coordination errors are not evidence that original FIT bytes are bad.
        if isinstance(error, fitdecode.FitError):
            conn.execute(
                "UPDATE fit_files SET integrity_status='invalid' WHERE id=%s", (fid,)
            )
        conn.commit()

    def decode(self, conn, payload, fid, file_hash, profile, run, stop):
        conn.execute(
            "DELETE FROM file_decodes WHERE fit_file_id=%s AND profile_id=%s",
            (fid, profile),
        )
        did = conn.execute(
            "INSERT INTO file_decodes(fit_file_id,profile_id,run_id,status) VALUES(%s,%s,%s,'pending') RETURNING id",
            (fid, profile, run),
        ).fetchone()[0]
        decoder = FitDecoder(
            conn, did, fid, file_hash, profile, lambda: check_stop(stop)
        )
        partial = decoder.read(payload)
        check_stop(stop)
        conn.execute("UPDATE file_decodes SET is_active=0 WHERE fit_file_id=%s", (fid,))
        conn.execute(
            "UPDATE file_decodes SET status=%s,decoded_at=%s,is_active=1,message_count=%s,"
            "stored_field_count=%s,unknown_field_count=%s WHERE id=%s",
            (
                "partial" if partial else "complete",
                utc_now(),
                decoder.messages,
                decoder.fields,
                decoder.unknown,
                did,
            ),
        )
        conn.execute(
            "UPDATE fit_files SET integrity_status='valid' WHERE id=%s", (fid,)
        )
        conn.execute(
            "DELETE FROM file_decodes WHERE fit_file_id=%s AND id<>%s", (fid, did)
        )
        conn.commit()
