"""Lossless values and canonical serialization, independent of FIT libraries."""

import json
import math

FIT_EPOCH = 631065600


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
