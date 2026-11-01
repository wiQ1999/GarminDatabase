"""Physical FIT preservation and explicitly versioned public-profile semantics."""

from garmin_fit_sdk import Profile

from garmin_database.domain.values import FIT_EPOCH, dumps

SUMMARY_MESSAGES = {211, 346, 370, 398}
SAMPLE_MESSAGES = {55, 227, 269, 275, 297, 371, 470, 471}
NUMERIC_TYPES = {
    "sint8",
    "uint8",
    "sint16",
    "uint16",
    "sint32",
    "uint32",
    "sint64",
    "uint64",
    "float32",
    "float64",
    "uint8z",
    "uint16z",
    "uint32z",
    "uint64z",
}


def scalar(value, default=None):
    if isinstance(value, list):
        return value[0] if len(value) == 1 else default
    return value if value is not None else default


def semantics(number, field, physical, file_hash):
    developer = getattr(field.field_def, "dev_data_index", None)
    message = Profile["messages"].get(number, {}) if developer is None else {}
    base = message.get("fields", {}).get(field.def_num, {})
    resolved = resolve_subfield(base, physical)
    name = resolved.get("name", field.name)
    known = bool(resolved) or field.field is not None
    unit = scalar(resolved.get("units"), field.units)
    scale = scalar(resolved.get("scale"), getattr(field.field, "scale", None))
    offset = scalar(resolved.get("offset"), getattr(field.field, "offset", None))
    kind = resolved.get("type", getattr(field.type, "name", None))
    time_role = field_time_role(kind, name)
    representation = field_representation(number) if known else "unknown"
    numeric = numeric_projection(known, kind, time_role, resolved, representation)
    # Developer index is only meaningful in a file. A conservative file-local key
    # prevents accidentally merging descriptions from unrelated applications.
    prefix = "native" if developer is None else f"developer:{file_hash}:{developer}"
    return dict(
        stable_key=f"{prefix}:{number}:{field.def_num}:{name}",
        message_num=number,
        field_num=field.def_num,
        variant_name=name,
        message_name=message.get("name", f"unknown_{number}"),
        namespace="native" if developer is None else "developer",
        developer_application_id_hex=None,
        developer_description_key=f"{file_hash}:{developer}:{field.def_num}"
        if developer is not None
        else None,
        semantics_status=semantics_status(known, developer),
        units=unit,
        scale=scale if isinstance(scale, (int, float)) and scale else None,
        offset=offset if isinstance(offset, (int, float)) else None,
        semantic_type=kind,
        numeric_projection_enabled=int(numeric),
        time_role=time_role,
        representation=representation,
        profile_metadata_json=dumps(
            {
                "profile": resolved,
                "enum": Profile["types"].get(kind, {}),
                "base_type": field.base_type.name,
            }
        ),
    )


def resolve_subfield(base, physical):
    for sub in base.get("sub_fields", []):
        if any(
            physical.get(mapping["num"]) == mapping["raw_value"]
            for mapping in sub.get("map", [])
        ):
            return {**base, **sub}
    return base


def field_time_role(kind, name):
    if kind == "date_time":
        return "utc_timestamp"
    if kind == "local_date_time":
        return "local_timestamp"
    if name in ("timestamp_16", "timestamp_min_8"):
        return "compressed_timestamp"
    return "duration" if "duration" in name else "none"


def field_representation(number):
    if number in SUMMARY_MESSAGES:
        return "source_summary"
    if number in SAMPLE_MESSAGES:
        return "sample"
    return "event" if number in {412, 276} else "metadata"


def numeric_projection(known, kind, time_role, resolved, representation):
    return (
        known
        and kind in NUMERIC_TYPES
        and time_role
        not in {"utc_timestamp", "local_timestamp", "compressed_timestamp"}
        and not resolved.get("has_components", False)
        and representation != "metadata"
    )


def semantics_status(known, developer):
    if not known:
        return "unknown"
    return "profile_known" if developer is None else "developer_described"


def utc_field(raw, metadata, names):
    for number, info in metadata.items():
        value = raw.get(number)
        if (
            info["time_role"] == "utc_timestamp"
            and isinstance(value, int)
            and value >= 0x10000000
            and info["variant_name"] in names
        ):
            return number, value
    return None


class TimeResolver:
    def __init__(self):
        self.last = None

    def resolve(self, frame, metadata):
        raw = {
            field.def_num: field.raw_value
            for field in frame.fields
            if field.field_def is not None
            and not getattr(field.field_def, "is_dev", False)
        }
        if frame.time_offset is not None:
            return self.compressed_header(frame.time_offset)
        explicit = utc_field(raw, metadata, {"timestamp"})
        if explicit is not None:
            number, self.last = explicit
            return (self.last + FIT_EPOCH) * 1000, "explicit_utc", number
        shortened = self.short_timestamp(frame.global_mesg_num, raw)
        if shortened is not None:
            return shortened
        associated = utc_field(
            raw, metadata, {"stress_level_time", "start_time", "end_time"}
        )
        if associated is not None:
            number, value = associated
            return (value + FIT_EPOCH) * 1000, "associated_field", number
        basis = (
            "unknown"
            if any(info["time_role"] != "none" for info in metadata.values())
            else "missing"
        )
        return None, basis, None

    def compressed_header(self, offset):
        if self.last is None:
            return None, "unknown", None
        value = (self.last & ~31) | offset
        if value < self.last:
            value += 32
        self.last = value
        return (value + FIT_EPOCH) * 1000, "compressed_header", None

    def short_timestamp(self, number, raw):
        if number != 55 or self.last is None:
            return None
        for number, bits, multiplier, basis in (
            (26, 16, 1, "timestamp_16"),
            (25, 8, 60, "timestamp_min_8"),
        ):
            if not isinstance(raw.get(number), int):
                continue
            reference = self.last // multiplier
            value = (reference & ~((1 << bits) - 1)) | raw[number]
            if value < reference:
                value += 1 << bits
            self.last = value * multiplier
            return (self.last + FIT_EPOCH) * 1000, basis, number
        return None
