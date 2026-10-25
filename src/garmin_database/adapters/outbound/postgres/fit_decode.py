"""Decode FIT frames in source order into one caller-owned transaction."""

import warnings
from pathlib import Path

import fitdecode
from garmin_fit_sdk import Profile

from garmin_database.adapters.outbound.fit.profile import TimeResolver, semantics
from garmin_database.adapters.outbound.postgres.fit_catalog import (
    json_load_profile,
    register_components,
    register_subfield,
)
from garmin_database.adapters.outbound.postgres.message_batch import MessageBatch
from garmin_database.domain.values import dumps, typed_value


def description_key(number, field, raw):
    base = Profile["messages"].get(number, {}).get("fields", {}).get(field.def_num, {})
    references = tuple(
        (mapping["num"], raw.get(mapping["num"]))
        for sub in base.get("sub_fields", [])
        for mapping in sub.get("map", [])
    )
    return (
        number,
        field.def_num,
        getattr(field.field_def, "dev_data_index", None),
        field.base_type.identifier,
        field.name,
        references,
    )


class FitDecoder:
    def __init__(self, conn, did, fid, file_hash, profile, check):
        self.conn, self.did, self.fid = conn, did, fid
        self.file_hash, self.profile, self.check = file_hash, profile, check
        self.definitions, self.catalog, self.descriptions = {}, {}, {}
        self.registered_rules = set()
        self.resolver = TimeResolver()
        self.messages = self.fields = self.unknown = self.definition_index = 0
        self.batch = MessageBatch(conn, check)

    def read(self, payload):
        with warnings.catch_warnings(record=True) as collected:
            with fitdecode.FitReader(
                payload,
                keep_raw_chunks=True,
                check_crc=fitdecode.CrcCheck.RAISE,
                error_handling=fitdecode.ErrorHandling.RAISE,
            ) as reader:
                for frame in reader:
                    self.check()
                    self.frame(frame, payload)
            self.batch.flush()
            # HTTP is concurrent, decoding is not. Do not attribute unrelated
            # library/network warnings to the active FIT or mark it partial.
            parser_root = Path(fitdecode.__file__).resolve().parent
            notices = [
                notice
                for notice in collected
                if Path(notice.filename).resolve().is_relative_to(parser_root)
            ]
            for notice in notices:
                self.conn.execute(
                    "INSERT INTO decode_issues(file_decode_id,issue_code,severity,context_json) "
                    "VALUES(%s,'parser_warning','warning',%s)",
                    (self.did, dumps({"category": notice.category.__name__})),
                )
        return bool(notices)

    def frame(self, frame, payload):
        if isinstance(frame, fitdecode.FitHeader):
            self.conn.execute(
                "UPDATE fit_files SET protocol_version=%s,header_profile_version=%s WHERE id=%s",
                (
                    payload[1],
                    int.from_bytes(frame.chunk.bytes[2:4], "little"),
                    self.fid,
                ),
            )
            self.resolver = TimeResolver()
        elif isinstance(frame, fitdecode.FitDefinitionMessage):
            self.definition(frame)
        elif isinstance(frame, fitdecode.FitDataMessage):
            self.message(frame)

    def definition(self, frame):
        self.definition_index += 1
        mid = self.conn.execute(
            "INSERT INTO message_definitions(file_decode_id,definition_index,global_message_num,"
            "local_message_num,byte_order,byte_offset) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                self.did,
                self.definition_index,
                frame.global_mesg_num,
                frame.local_mesg_num,
                "little" if frame.endian == "<" else "big",
                frame.chunk.offset,
            ),
        ).fetchone()[0]
        field_ids = {}
        for order, field in enumerate(frame.all_field_defs):
            developer = getattr(field, "dev_data_index", None)
            field_ids[id(field)] = self.conn.execute(
                "INSERT INTO field_definitions(message_definition_id,field_order,field_num,namespace,"
                "developer_data_index,base_type_id,size_bytes) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (
                    mid,
                    order,
                    field.def_num,
                    "native" if developer is None else "developer",
                    developer,
                    field.base_type.identifier,
                    field.size,
                ),
            ).fetchone()[0]
        self.definitions[id(frame)] = mid, field_ids

    def catalog_id(self, info):
        key = info["stable_key"]
        if key not in self.catalog:
            columns = [f'"{name}"' for name in info]
            self.conn.execute(
                f"INSERT INTO field_catalog(profile_id,{','.join(columns)}) "
                f"VALUES(%s{',%s' * len(columns)}) ON CONFLICT DO NOTHING",
                (self.profile, *info.values()),
            )
            self.catalog[key] = self.conn.execute(
                "SELECT id FROM field_catalog WHERE profile_id=%s AND stable_key=%s",
                (self.profile, key),
            ).fetchone()[0]
        return self.catalog[key]

    def describe(self, frame, physical):
        raw = {f.def_num: f.raw_value for f in physical if not f.field_def.is_dev}
        info = {}
        for field in physical:
            # Semantic coordinates survive local definition replacement. Python
            # object identities do not; subfields also depend on reference values.
            key = description_key(frame.global_mesg_num, field, raw)
            if key not in self.descriptions:
                self.descriptions[key] = semantics(
                    frame.global_mesg_num, field, raw, self.file_hash
                )
            info[id(field)] = self.descriptions[key]
        return info

    def register_rules(self, cid, desc):
        if cid in self.registered_rules:
            return
        self.registered_rules.add(cid)
        public = json_load_profile(desc)
        if public.get("has_components"):
            register_components(self.conn, self.profile, cid, desc, self.catalog_id)
        if public.get("map"):
            register_subfield(self.conn, self.profile, cid, desc, self.catalog_id)

    def message(self, frame):
        mid, field_ids = self.definitions[id(frame.def_mesg)]
        physical = [f for f in frame.fields if f.field_def is not None]
        info = self.describe(frame, physical)
        instant, basis, time_field = self.resolver.resolve(
            frame,
            {f.def_num: info[id(f)] for f in physical if not f.field_def.is_dev},
        )
        header = frame.chunk.bytes[0]
        message = (
            self.did,
            mid,
            self.messages,
            frame.chunk.offset,
            len(frame.chunk.bytes),
            header,
            header & 31 if header & 128 else None,
            instant,
            basis,
            time_field,
            dumps({"basis": basis, "field": time_field}),
        )
        fields = []
        for field in physical:
            desc = info[id(field)]
            cid = self.catalog_id(desc)
            fields.append(
                (
                    self.messages,
                    field_ids[id(field.field_def)],
                    mid,
                    cid,
                    *typed_value(field.raw_value),
                )
            )
            self.unknown += desc["semantics_status"] == "unknown"
            self.register_rules(cid, desc)
        self.batch.append(message, fields)
        self.fields += len(fields)
        self.messages += 1
