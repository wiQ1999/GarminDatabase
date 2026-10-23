"""Physical FIT preservation and explicitly versioned public-profile semantics."""

import json
import math

from garmin_fit_sdk import Profile

FIT_EPOCH = 631065600  # 1989-12-31 UTC
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


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def json_value(value):
    if isinstance(value, (tuple, list, bytes)):
        return [json_value(x) for x in value]
    if isinstance(value, int) and not -(2**63) <= value < 2**63:
        return {"integer_text": str(value)}
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def typed_value(value):
    """Exactly one PostgreSQL value column is populated, before any FIT scaling."""
    validity = "valid"
    if value is None:
        return ("null", None, None, None, None, "invalid")
    if isinstance(value, (list, tuple, bytes)):
        data = json_value(value)
        if any(x is None for x in data):
            validity = "partial_invalid"
        return ("json", None, None, None, dumps(data), validity)
    if isinstance(value, int):
        if -(2**63) <= value < 2**63:
            return ("integer", value, None, None, None, validity)
        return ("integer_text", None, None, str(value), None, validity)
    if isinstance(value, float):
        return (
            ("real", None, value, None, None, validity)
            if math.isfinite(value)
            else ("null", None, None, None, None, "invalid")
        )
    if isinstance(value, str):
        return ("text", None, None, value, None, validity)
    raise TypeError("Nieobsługiwany typ wartości FIT")


def scalar(value, default=None):
    if isinstance(value, list):
        return value[0] if len(value) == 1 else default
    return value if value is not None else default


def semantics(number, field, physical, file_hash):
    developer = getattr(field.field_def, "dev_data_index", None)
    message = Profile["messages"].get(number, {}) if developer is None else {}
    base = message.get("fields", {}).get(field.def_num, {})
    resolved = base
    for sub in base.get("sub_fields", []):
        if any(physical.get(m["num"]) == m["raw_value"] for m in sub.get("map", [])):
            resolved = {**base, **sub}
            break
    name = resolved.get("name", field.name)
    known = bool(resolved) or field.field is not None
    unit = scalar(resolved.get("units"), field.units)
    scale = scalar(resolved.get("scale"), getattr(field.field, "scale", None))
    offset = scalar(resolved.get("offset"), getattr(field.field, "offset", None))
    kind = resolved.get("type", getattr(field.type, "name", None))
    time_role = (
        "utc_timestamp"
        if kind == "date_time"
        else "local_timestamp"
        if kind == "local_date_time"
        else "compressed_timestamp"
        if name in ("timestamp_16", "timestamp_min_8")
        else "duration"
        if "duration" in name
        else "none"
    )
    representation = (
        "source_summary"
        if number in SUMMARY_MESSAGES
        else "sample"
        if number in SAMPLE_MESSAGES
        else "event"
        if number in {412, 276}
        else "metadata"
    )
    if not known:
        representation = "unknown"
    numeric = (
        known
        and kind in NUMERIC_TYPES
        and time_role
        not in {"utc_timestamp", "local_timestamp", "compressed_timestamp"}
        and not resolved.get("has_components", False)
        and representation != "metadata"
    )
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
        semantics_status="profile_known"
        if known and developer is None
        else "developer_described"
        if known
        else "unknown",
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


class TimeResolver:
    def __init__(self):
        self.last = None

    def resolve(self, frame, metadata):
        raw = {
            f.def_num: f.raw_value
            for f in frame.fields
            if f.field_def is not None and not getattr(f.field_def, "is_dev", False)
        }
        if frame.time_offset is not None:
            if self.last is None:
                return None, "unknown", None
            value = (self.last & ~31) | frame.time_offset
            if value < self.last:
                value += 32
            self.last = value
            return (value + FIT_EPOCH) * 1000, "compressed_header", None
        for number, info in metadata.items():
            value = raw.get(number)
            if (
                info["time_role"] == "utc_timestamp"
                and isinstance(value, int)
                and value >= 0x10000000
            ):
                if info["variant_name"] == "timestamp":
                    self.last = value
                    return (value + FIT_EPOCH) * 1000, "explicit_utc", number
        if frame.global_mesg_num == 55 and self.last is not None:
            for number, bits, multiplier, basis in (
                (26, 16, 1, "timestamp_16"),
                (25, 8, 60, "timestamp_min_8"),
            ):
                if isinstance(raw.get(number), int):
                    reference = self.last // multiplier
                    value = (reference & ~((1 << bits) - 1)) | raw[number]
                    if value < reference:
                        value += 1 << bits
                    self.last = value * multiplier
                    return (self.last + FIT_EPOCH) * 1000, basis, number
        for number, info in metadata.items():
            value = raw.get(number)
            if (
                info["time_role"] == "utc_timestamp"
                and isinstance(value, int)
                and value >= 0x10000000
                and info["variant_name"]
                in {"stress_level_time", "start_time", "end_time"}
            ):
                return (value + FIT_EPOCH) * 1000, "associated_field", number
        return (
            None,
            "unknown"
            if any(x["time_role"] != "none" for x in metadata.values())
            else "missing",
            None,
        )
