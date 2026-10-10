from pathlib import Path
import sqlite3
import unittest

SQL = (Path(__file__).resolve().parents[1] / 'schema/001_initial.sql').read_text(encoding='utf-8')


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript(SQL)
        self.db.execute("INSERT INTO decoder_profiles VALUES(1,'fitdecode','0.11.0','test','{}')")
        self.db.execute("INSERT INTO fit_files VALUES(1,?,100,16,21000,'valid')", ('a' * 64,))
        self.db.execute("INSERT INTO decode_runs VALUES(1,1,'2026-10-10',NULL,'running')")
        self.db.execute("INSERT INTO file_decodes(id,fit_file_id,profile_id,run_id,status,is_active) VALUES(1,1,1,1,'complete',1)")
        self.db.execute("INSERT INTO message_definitions VALUES(1,1,0,55,0,'little',14)")
        self.db.execute("INSERT INTO field_definitions VALUES(1,1,0,27,'native',NULL,2,1)")
        self.db.execute("""INSERT INTO fit_messages(id,file_decode_id,message_definition_id,message_index,
            byte_offset,byte_length,time_unix_ms,time_basis,time_field_num)
            VALUES(1,1,1,0,25,2,1700000000000,'explicit_utc',253)""")
        self.db.execute("""INSERT INTO field_catalog(id,profile_id,stable_key,message_num,field_num,
            variant_name,message_name,namespace,semantics_status,units,scale,offset,numeric_projection_enabled,profile_metadata_json)
            VALUES(1,1,'55.27.heart_rate',55,27,'heart_rate','monitoring','native','profile_known','bpm',2,1,1,'{}')""")

    def field(self, kind, integer=None, real=None, text=None, array=None, validity='valid'):
        self.db.execute('INSERT INTO fit_fields VALUES(1,1,1,1,?,?,?,?,?,?)',
                        (kind, integer, real, text, array, validity))

    def test_raw_scalar_and_profile_conversion(self):
        self.field('integer', integer=126)
        self.assertEqual(self.db.execute('SELECT value FROM v_numeric_parameters').fetchone()[0], 62)
        self.assertEqual(self.db.execute('SELECT integer_value FROM fit_fields').fetchone()[0], 126)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_integer_text_preserves_unsigned_64bit(self):
        value = str(2**64 - 2)
        self.field('integer_text', text=value)
        self.assertEqual(self.db.execute('SELECT text_value FROM fit_fields').fetchone()[0], value)
        self.assertEqual(self.db.execute('SELECT count(*) FROM v_numeric_parameters').fetchone()[0], 0)

    def test_encoded_fields_not_projected_without_explicit_mapping(self):
        self.field('integer', integer=126)
        self.db.execute('UPDATE field_catalog SET numeric_projection_enabled=0')
        self.assertEqual(self.db.execute('SELECT count(*) FROM v_numeric_parameters').fetchone()[0], 0)

    def test_array_retains_invalid_positions(self):
        self.field('json', array='[1,null,3]', validity='partial_invalid')
        self.assertEqual(self.db.execute('SELECT value FROM fit_fields,json_each(json_value)').fetchall(),
                         [(1,), (None,), (3,)])

    def test_two_value_columns_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.field('integer', integer=1, text='duplicate')

    def test_mismatched_definition_rejected(self):
        self.db.execute("INSERT INTO message_definitions VALUES(2,1,1,55,1,'little',30)")
        self.db.execute("INSERT INTO field_definitions VALUES(2,2,0,27,'native',NULL,2,1)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO fit_fields VALUES(1,2,1,1,'integer',1,NULL,NULL,NULL,'valid')")

    def test_shared_file_has_two_provenance_links(self):
        for index, day in enumerate(('2026-10-08', '2026-10-09'), 1):
            self.db.execute("INSERT INTO import_days(day,download_status) VALUES(?,'downloaded')", (day,))
            self.db.execute('INSERT INTO archives VALUES(?,?,?,?,?,?,?)',
                            (index, day, f'raw/{day}.zip', 'b' * 64, 100, None, 'webapi'))
            self.db.execute('INSERT INTO archive_entries VALUES(?,?,?,?,?,?)',
                            (index, index, 0, 'sample.fit', 'WELLNESS', 1))
        self.assertEqual(self.db.execute('SELECT count(*) FROM v_field_provenance').fetchone()[0], 2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM fit_files').fetchone()[0], 1)

    def test_missing_time_cannot_claim_resolved_timestamp(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE fit_messages SET time_basis='missing' WHERE id=1")

    def test_compressed_header_retains_its_original_time_bits(self):
        self.db.execute("UPDATE fit_messages SET record_header=133,compressed_time_offset=5,time_basis='compressed_header' WHERE id=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('UPDATE fit_messages SET compressed_time_offset=6 WHERE id=1')


if __name__ == '__main__':
    unittest.main()
