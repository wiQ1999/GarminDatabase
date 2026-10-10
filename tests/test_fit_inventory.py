from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest
import struct

import fitdecode

from garmin_fit_sdk import Encoder

spec = importlib.util.spec_from_file_location(
    'inventory', Path(__file__).resolve().parents[1] / 'scripts/analyze_fit_inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def test_metadata_inventory_does_not_retain_measurements(self):
        encoder = Encoder()
        encoder.write_mesg({'mesg_num': 0, 'type': 'activity', 'manufacturer': 'development',
                            'time_created': datetime(2026, 1, 1, tzinfo=timezone.utc)})
        encoder.write_mesg({'mesg_num': 20, 'timestamp': datetime(2026, 1, 1, tzinfo=timezone.utc),
                            'heart_rate': 123, 'cadence': 77})
        payload = bytes(encoder.close())
        result = inventory.decode_inventory(payload)
        self.assertEqual(result['profile_versions'], [int.from_bytes(payload[2:4], 'little')])
        names = {field['name'] for field in result['fields']}
        self.assertIn('heart_rate', names)
        self.assertIn('cadence', names)
        self.assertFalse(any('raw_value' in field or 'value' in field for field in result['fields']))
        comparison = inventory.sdk_check(payload)
        self.assertFalse(comparison['errors'])
        self.assertEqual(result['messages'], comparison['messages'])

    def test_invalid_fit_rejected(self):
        with self.assertRaises(Exception):
            inventory.decode_inventory(b'not FIT')

    def test_current_sdk_profile_enriches_newer_sleep_fields(self):
        report = {'summary': {'stored_field_occurrences': 1}, 'fields': [{
            'message_num': 412, 'field_num': 0, 'developer_index': None,
            'name': 'unknown_0', 'sdk_name': 'start_time', 'expanded': False,
            'parser_named': False, 'count': 1}]}
        inventory.enrich_public_profile(report)
        self.assertEqual(report['fields'][0]['sdk_message_name'], 'nap_event')
        self.assertEqual(report['summary']['public_profile_unknown_stored_variants'], 0)

    def test_unknown_message_and_array_with_invalid_element_are_catalogued(self):
        body = b'\x40\x00\x00' + struct.pack('<H', 60000) + b'\x01\x07\x02\x02\x00\x07\xff'
        header = struct.pack('<BBHI4s', 14, 16, 21000, len(body), b'.FIT')
        header += struct.pack('<H', fitdecode.utils.compute_crc(header))
        data = header + body
        data += struct.pack('<H', fitdecode.utils.compute_crc(data))
        result = inventory.decode_inventory(data)
        field = result['fields'][0]
        self.assertEqual(field['message_num'], 60000)
        self.assertEqual(field['field_num'], 7)
        self.assertFalse(field['parser_named'])
        self.assertEqual(field['array_lengths'], [2])
        self.assertTrue(field['contains_null_array'])
        with self.assertRaises(Exception):
            inventory.decode_inventory(data[:-1] + bytes([data[-1] ^ 1]))


if __name__ == '__main__':
    unittest.main()
