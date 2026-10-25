"""Versioned FIT interpretation rules, shared by the decoder."""

import json

from garmin_database.domain.values import dumps


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
