"""Catalog membership and bounded reads with many unobserved variants."""

import pytest

from garmin_database.adapters.outbound.postgres.database import Database
from garmin_database.adapters.outbound.postgres.imports import Importer
from garmin_database.adapters.outbound.postgres.queries import Queries
from tests.support.fixtures import archive, fit_bytes

pytestmark = pytest.mark.integration


def test_catalog_uses_observed_active_fields_and_interpretation_sources(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    Importer(db).archive(
        archive(
            db.root,
            payload=fit_bytes(
                values=[
                    (1100000000 + i, 60 + i % 30, (43776 + i) % 65536, i)
                    for i in range(10000)
                ]
            ),
        )
    )
    before = {i for parameter in Queries(db).parameters() for i in parameter["ids"]}
    with db.connect() as conn:
        prototype = conn.execute(
            "SELECT id,profile_id FROM field_catalog WHERE variant_name='heart_rate'"
        ).fetchone()
        # Known variants without observations must never appear in the catalog.
        targets = conn.execute(
            """INSERT INTO field_catalog(profile_id,stable_key,message_num,
            field_num,variant_name,message_name,namespace,semantics_status,representation,profile_metadata_json)
            SELECT %s,'synthetic.'||i,55,27,'synthetic_'||i,'monitoring','native','profile_known','sample','{}'
            FROM generate_series(1,100) i RETURNING id""",
            (prototype[1],),
        ).fetchall()
        alias = targets[0][0]
        for kind in ("component", "subfield"):
            conn.execute(
                """INSERT INTO interpretation_rules(profile_id,source_catalog_id,target_catalog_id,kind,rule_json)
                VALUES(%s,%s,%s,%s,'{}')""",
                (prototype[1], prototype[0], alias, kind),
            )
        conn.execute("ANALYZE fit_fields")
        conn.execute("ANALYZE fit_messages")
        conn.execute("ANALYZE field_catalog")
    with db.connect(readonly=True) as conn:
        conn.execute("SET LOCAL statement_timeout='2s'")
        catalog = Queries(db).parameters(conn)
    actual = [i for parameter in catalog for i in parameter["ids"]]
    assert set(actual) == before | {alias} and len(actual) == len(set(actual))
    with db.connect() as conn:
        conn.execute("UPDATE file_decodes SET is_active=0")
    assert Queries(db).parameters() == []
