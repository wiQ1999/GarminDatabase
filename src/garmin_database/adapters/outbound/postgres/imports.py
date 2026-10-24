import importlib.metadata
import json
import warnings
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import fitdecode

from garmin_database.adapters.outbound.fit.profile import TimeResolver, semantics
from garmin_database.domain.cancellation import Cancelled, check_stop
from garmin_database.domain.time import utc_now
from garmin_database.domain.values import dumps, typed_value


def json_load_profile(desc):
    return json.loads(desc["profile_metadata_json"]).get("profile", {})


def register_components(conn, profile, cid, desc, catalog_id):
    from garmin_fit_sdk import Profile

    from garmin_database.adapters.outbound.fit.profile import NUMERIC_TYPES, scalar

    public = json_load_profile(desc)
    shift = 0
    for index, number in enumerate(public.get("components", [])):
        target = Profile["messages"][desc["message_num"]]["fields"].get(number)
        if not target:
            continue
        updated = {
            **desc,
            "field_num": number,
            "variant_name": target["name"],
            "stable_key": f"native:{desc['message_num']}:{number}:{target['name']}",
            "units": scalar(target.get("units")),
            "scale": scalar(target.get("scale")),
            "offset": scalar(target.get("offset")),
            "semantic_type": target["type"],
            "numeric_projection_enabled": int(target["type"] in NUMERIC_TYPES),
            "profile_metadata_json": dumps(
                {"profile": target, "enum": Profile["types"].get(target["type"], {})}
            ),
        }
        target_id = catalog_id(updated)
        bits = public["bits"][index]
        rule = {
            "shift": shift,
            "bits": bits,
            "scale": public["scale"][index],
            "offset": public["offset"][index],
            "accumulate": target.get("is_accumulated", False),
            "parent_base_type": json.loads(desc["profile_metadata_json"])["base_type"],
        }
        conn.execute(
            "INSERT INTO interpretation_rules(profile_id,source_catalog_id,target_catalog_id,kind,rule_json) VALUES(%s,%s,%s,'component',%s) ON CONFLICT DO NOTHING",
            (profile, cid, target_id, dumps(rule)),
        )
        shift += bits


def register_subfield(conn, profile, cid, desc, catalog_id):
    from garmin_fit_sdk import Profile

    from garmin_database.adapters.outbound.fit.profile import scalar

    base = (
        Profile["messages"]
        .get(desc["message_num"], {})
        .get("fields", {})
        .get(desc["field_num"], {})
    )
    resolved = json_load_profile(desc)
    if not resolved.get("map") or not base:
        return
    original = {
        **desc,
        "variant_name": base["name"],
        "stable_key": f"native:{desc['message_num']}:{desc['field_num']}:{base['name']}",
        "units": scalar(base.get("units")),
        "scale": scalar(base.get("scale")),
        "offset": scalar(base.get("offset")),
        "semantic_type": base["type"],
        "profile_metadata_json": dumps(
            {
                "profile": base,
                "enum": Profile["types"].get(base["type"], {}),
                "base_type": json.loads(desc["profile_metadata_json"])["base_type"],
            }
        ),
    }
    source = catalog_id(original)
    conn.execute(
        "INSERT INTO interpretation_rules(profile_id,source_catalog_id,target_catalog_id,kind,rule_json) VALUES(%s,%s,%s,'subfield',%s) ON CONFLICT DO NOTHING",
        (
            profile,
            source,
            cid,
            dumps(
                {
                    "map": resolved["map"],
                    "scale": resolved.get("scale"),
                    "offset": resolved.get("offset"),
                }
            ),
        ),
    )


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
        path = Path(path)
        from datetime import date

        day = date.fromisoformat(path.stem).isoformat()
        # Refuse originals outside the configured data directory.
        relative = path.resolve().relative_to(self.db.root.resolve()).as_posix()
        digest = sha256(path.read_bytes()).hexdigest()
        with self.db.connect() as conn, ZipFile(path) as archive:
            previous = conn.execute(
                "SELECT id,sha256 FROM archives WHERE day=%s", (day,)
            ).fetchone()
            if previous and previous[1] != digest:
                raise ValueError("Zmienione archiwum źródłowe")
            bad = archive.testzip()
            if bad is not None:
                raise ValueError("Nieprawidłowy CRC archiwum")
            entries = [
                (i, x) for i, x in enumerate(archive.infolist()) if not x.is_dir()
            ]
            conn.execute(
                "INSERT INTO import_days(day,download_status,checked_at) VALUES(%s,%s,%s) ON CONFLICT(day) DO UPDATE SET download_status=excluded.download_status",
                (day, "downloaded" if entries else "empty_zip", utc_now()),
            )
            conn.execute(
                "INSERT INTO archives(day,relative_path,sha256,size_bytes,acquired_at,acquisition_origin) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (day, relative, digest, path.stat().st_size, utc_now(), origin),
            )
            aid = conn.execute(
                "SELECT id FROM archives WHERE day=%s", (day,)
            ).fetchone()[0]
            profile = self.profile(conn)
            if previous and not force:
                registered = conn.execute(
                    "SELECT count(*) FROM archive_entries WHERE archive_id=%s", (aid,)
                ).fetchone()[0]
                incomplete = conn.execute(
                    """SELECT 1 FROM archive_entries e WHERE e.archive_id=%s AND NOT EXISTS(
                    SELECT 1 FROM file_decodes d WHERE d.fit_file_id=e.fit_file_id
                    AND d.profile_id=%s AND d.is_active=1 AND d.status='complete') LIMIT 1""",
                    (aid, profile),
                ).fetchone()
                if registered == len(entries) and not incomplete:
                    return 0  # no fictitious decode run for an unchanged completed ZIP
            run = conn.execute(
                "INSERT INTO decode_runs(profile_id,started_at,status) VALUES(%s,%s,'running') RETURNING id",
                (profile, utc_now()),
            ).fetchone()[0]
            conn.commit()
            failed = 0
            try:
                for index, item in entries:
                    check_stop(stop)
                    payload = archive.read(item)
                    h = sha256(payload).hexdigest()
                    conn.execute(
                        "INSERT INTO fit_files(sha256,size_bytes,integrity_status) VALUES(%s,%s,'pending') ON CONFLICT DO NOTHING",
                        (h, len(payload)),
                    )
                    fid = conn.execute(
                        "SELECT id FROM fit_files WHERE sha256=%s", (h,)
                    ).fetchone()[0]
                    category = Path(item.filename).stem.partition("_")[2] or "unknown"
                    conn.execute(
                        "INSERT INTO archive_entries(archive_id,entry_index,entry_name,category,fit_file_id) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (aid, index, item.filename, category, fid),
                    )
                    conn.commit()
                    done = conn.execute(
                        "SELECT status FROM file_decodes WHERE fit_file_id=%s AND profile_id=%s",
                        (fid, profile),
                    ).fetchone()
                    force_file = (
                        force is True or isinstance(force, set) and fid in force
                    )
                    if not force_file and done and done[0] == "complete":
                        continue
                    progress(day, "import", index + 1, len(entries))
                    try:
                        self.decode(conn, payload, fid, h, profile, run, stop)
                    except Cancelled:
                        raise
                    except Exception as error:
                        conn.rollback()
                        failed += 1
                        # Retain the previous active result on failed reprocessing.
                        old = conn.execute(
                            "SELECT id FROM file_decodes WHERE fit_file_id=%s AND profile_id=%s",
                            (fid, profile),
                        ).fetchone()
                        if not old:
                            did = conn.execute(
                                "INSERT INTO file_decodes(fit_file_id,profile_id,run_id,status,error_type) VALUES(%s,%s,%s,'failed',%s) RETURNING id",
                                (fid, profile, run, type(error).__name__),
                            ).fetchone()[0]
                            conn.execute(
                                "INSERT INTO decode_issues(file_decode_id,issue_code,severity,context_json) VALUES(%s,'fit_decode_failed','error',%s)",
                                (did, dumps({"type": type(error).__name__})),
                            )
                        conn.execute(
                            "UPDATE fit_files SET integrity_status='invalid' WHERE id=%s",
                            (fid,),
                        )
                        conn.commit()
                        progress(
                            day,
                            f"Błąd importu FIT — {type(error).__name__}. Archiwum ZIP zachowano; nieukończony zapis FIT wycofano.",
                            index + 1,
                            len(entries),
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

    def decode(self, conn, payload, fid, file_hash, profile, run, stop):
        # The SELECT in archive() has already opened this FIT transaction.
        # Deletion and replacement remain inside one transaction; rollback restores it.
        conn.execute(
            "DELETE FROM file_decodes WHERE fit_file_id=%s AND profile_id=%s",
            (fid, profile),
        )
        did = conn.execute(
            "INSERT INTO file_decodes(fit_file_id,profile_id,run_id,status) VALUES(%s,%s,%s,'pending') RETURNING id",
            (fid, profile, run),
        ).fetchone()[0]
        definitions = {}
        catalog = {}
        descriptions = {}
        registered_rules = set()
        resolver = TimeResolver()
        messages = fields = unknown = definition_index = 0

        def catalog_id(info):
            key = info["stable_key"]
            if key not in catalog:
                columns = [f'"{name}"' for name in info]
                conn.execute(
                    f"INSERT INTO field_catalog(profile_id,{','.join(columns)}) VALUES(%s{',%s' * len(columns)}) ON CONFLICT DO NOTHING",
                    (profile, *info.values()),
                )
                catalog[key] = conn.execute(
                    "SELECT id FROM field_catalog WHERE profile_id=%s AND stable_key=%s",
                    (profile, key),
                ).fetchone()[0]
            return catalog[key]

        with warnings.catch_warnings(record=True) as notices:
            with fitdecode.FitReader(
                payload,
                keep_raw_chunks=True,
                check_crc=fitdecode.CrcCheck.RAISE,
                error_handling=fitdecode.ErrorHandling.RAISE,
            ) as reader:
                for frame in reader:
                    check_stop(stop)
                    if isinstance(frame, fitdecode.FitHeader):
                        conn.execute(
                            "UPDATE fit_files SET protocol_version=%s,header_profile_version=%s WHERE id=%s",
                            (
                                payload[1],
                                int.from_bytes(frame.chunk.bytes[2:4], "little"),
                                fid,
                            ),
                        )
                        resolver = TimeResolver()
                    elif isinstance(frame, fitdecode.FitDefinitionMessage):
                        definition_index += 1
                        mid = conn.execute(
                            "INSERT INTO message_definitions(file_decode_id,definition_index,global_message_num,local_message_num,byte_order,byte_offset) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
                            (
                                did,
                                definition_index,
                                frame.global_mesg_num,
                                frame.local_mesg_num,
                                "little" if frame.endian == "<" else "big",
                                frame.chunk.offset,
                            ),
                        ).fetchone()[0]
                        field_ids = {}
                        for order, f in enumerate(frame.all_field_defs):
                            idx = getattr(f, "dev_data_index", None)
                            field_ids[id(f)] = conn.execute(
                                "INSERT INTO field_definitions(message_definition_id,field_order,field_num,namespace,developer_data_index,base_type_id,size_bytes) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                                (
                                    mid,
                                    order,
                                    f.def_num,
                                    "native" if idx is None else "developer",
                                    idx,
                                    f.base_type.identifier,
                                    f.size,
                                ),
                            ).fetchone()[0]
                        definitions[id(frame)] = (mid, field_ids)
                    elif isinstance(frame, fitdecode.FitDataMessage):
                        mid, field_ids = definitions[id(frame.def_mesg)]
                        physical = [f for f in frame.fields if f.field_def is not None]
                        raw = {
                            f.def_num: f.raw_value
                            for f in physical
                            if not f.field_def.is_dev
                        }
                        info = {}
                        for f in physical:
                            # Profile subfields can depend on any reference field;
                            # use those reference values as part of the cache key.
                            from garmin_fit_sdk import Profile

                            base = (
                                Profile["messages"]
                                .get(frame.global_mesg_num, {})
                                .get("fields", {})
                                .get(f.def_num, {})
                            )
                            references = tuple(
                                (m["num"], raw.get(m["num"]))
                                for sub in base.get("sub_fields", [])
                                for m in sub.get("map", [])
                            )
                            # Python object ids may be reused after FIT local
                            # definitions are replaced. Cache semantic coordinates,
                            # never an object's memory address.
                            key = (
                                frame.global_mesg_num,
                                f.def_num,
                                getattr(f.field_def, "dev_data_index", None),
                                f.base_type.identifier,
                                f.name,
                                references,
                            )
                            if key not in descriptions:
                                descriptions[key] = semantics(
                                    frame.global_mesg_num, f, raw, file_hash
                                )
                            info[id(f)] = descriptions[key]
                        time, basis, time_field = resolver.resolve(
                            frame,
                            {
                                f.def_num: info[id(f)]
                                for f in physical
                                if not f.field_def.is_dev
                            },
                        )
                        header = frame.chunk.bytes[0]
                        message = conn.execute(
                            "INSERT INTO fit_messages(file_decode_id,message_definition_id,message_index,byte_offset,byte_length,record_header,compressed_time_offset,time_unix_ms,time_basis,time_field_num,time_resolution_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                            (
                                did,
                                mid,
                                messages,
                                frame.chunk.offset,
                                len(frame.chunk.bytes),
                                header,
                                header & 31 if header & 128 else None,
                                time,
                                basis,
                                time_field,
                                dumps({"basis": basis, "field": time_field}),
                            ),
                        ).fetchone()[0]
                        batch = []
                        for f in physical:
                            desc = info[id(f)]
                            cid = catalog_id(desc)
                            batch.append(
                                (
                                    message,
                                    field_ids[id(f.field_def)],
                                    mid,
                                    cid,
                                    *typed_value(f.raw_value),
                                )
                            )
                            unknown += desc["semantics_status"] == "unknown"
                            if cid not in registered_rules:
                                registered_rules.add(cid)
                                public = json_load_profile(desc)
                                if public.get("has_components"):
                                    register_components(
                                        conn, profile, cid, desc, catalog_id
                                    )
                                if public.get("map"):
                                    register_subfield(
                                        conn, profile, cid, desc, catalog_id
                                    )
                        conn.cursor().executemany(
                            "INSERT INTO fit_fields VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            batch,
                        )
                        fields += len(batch)
                        messages += 1
            for notice in notices:
                conn.execute(
                    "INSERT INTO decode_issues(file_decode_id,issue_code,severity,context_json) VALUES(%s,'parser_warning','warning',%s)",
                    (did, dumps({"category": notice.category.__name__})),
                )
        check_stop(stop)
        conn.execute("UPDATE file_decodes SET is_active=0 WHERE fit_file_id=%s", (fid,))
        conn.execute(
            "UPDATE file_decodes SET status=%s,decoded_at=%s,is_active=1,message_count=%s,stored_field_count=%s,unknown_field_count=%s WHERE id=%s",
            (
                "partial" if notices else "complete",
                utc_now(),
                messages,
                fields,
                unknown,
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
