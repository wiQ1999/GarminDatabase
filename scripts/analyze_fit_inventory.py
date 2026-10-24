"""Stream FITs from ZIPs; retain schema/count metadata, never measurement payloads.

Source rules: docs/02-source-validation.md. Local reports are not product docs.
"""

import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import time
import warnings
from zipfile import ZipFile

import fitdecode
from garmin_fit_sdk import Decoder, Profile, Stream

ROOT = Path(__file__).resolve().parents[1]


def enrich_public_profile(report):
    for row in report['fields']:
        message = Profile['messages'].get(row['message_num'], {})
        modern = message.get('fields', {}).get(row['field_num'], {})
        if row['developer_index'] is not None:
            modern = {}
        variant = next((field for field in modern.get('sub_fields', [])
                        if field['name'] == row['name']), modern)
        row.update({'sdk_message_name': message.get('name'),
                    'sdk_units': variant.get('units'), 'sdk_scale': variant.get('scale'),
                    'sdk_offset': variant.get('offset')})
    stored = [row for row in report['fields'] if not row['expanded']]
    named = sum(row['count'] for row in stored if row['parser_named'] or row['sdk_name'])
    report['summary']['public_profile_named_occurrence_percent'] = round(
        100 * named / report['summary']['stored_field_occurrences'], 2)
    report['summary']['public_profile_unknown_stored_variants'] = sum(
        not row['parser_named'] and not row['sdk_name'] for row in stored)
    return report


def decode_inventory(payload):
    messages = Counter()
    fields = {}
    times = []
    versions = []
    with warnings.catch_warnings(record=True) as notices:
        with fitdecode.FitReader(payload, keep_raw_chunks=True, check_crc=fitdecode.CrcCheck.RAISE,
                                 error_handling=fitdecode.ErrorHandling.RAISE) as reader:
            for frame in reader:
                if isinstance(frame, fitdecode.FitHeader):
                    versions.append(int.from_bytes(frame.chunk.bytes[2:4], 'little'))
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                number = frame.global_mesg_num
                messages[number] += 1
                for field in frame.fields:
                    developer = getattr(field.field_def, 'dev_data_index', None)
                    key = (number, field.def_num, developer, field.name, field.is_expanded)
                    modern = Profile['messages'].get(number, {}).get('fields', {}).get(field.def_num)
                    row = fields.setdefault(key, {
                        'message_num': number, 'message_name': frame.name,
                        'field_num': field.def_num, 'developer_index': developer,
                        'name': field.name, 'expanded': field.is_expanded,
                        'parser_named': field.field is not None,
                        'sdk_name': modern.get('name') if modern and developer is None else None,
                        'units': field.units, 'scale': getattr(field.field, 'scale', None),
                        'offset': getattr(field.field, 'offset', None),
                        'base_types': set(), 'byte_sizes': set(), 'array_lengths': set(),
                        'value_types': set(), 'count': 0, 'null_count': 0,
                        'contains_null_array': False, 'outside_signed_int64': False,
                    })
                    row['count'] += 1
                    raw = field.raw_value
                    row['null_count'] += raw is None
                    row['base_types'].add(field.base_type.name)
                    if field.field_def:
                        row['byte_sizes'].add(field.field_def.size)
                    row['value_types'].add(type(raw).__name__)
                    if isinstance(raw, (tuple, list)):
                        row['array_lengths'].add(len(raw))
                        row['contains_null_array'] |= any(value is None for value in raw)
                        values = raw
                    else:
                        values = (raw,)
                    row['outside_signed_int64'] |= any(isinstance(value, int)
                        and not -(2**63) <= value < 2**63 for value in values)
                    if isinstance(field.value, datetime) and field.name in (
                            'timestamp', 'time_created', 'stress_level_time', 'start_time', 'end_time'):
                        times.append(field.value.isoformat())
    for row in fields.values():
        for key in ('base_types', 'byte_sizes', 'array_lengths', 'value_types'):
            row[key] = sorted(row[key])
    return {'messages': dict(messages), 'fields': list(fields.values()),
            'min_time': min(times) if times else None, 'max_time': max(times) if times else None,
            'profile_versions': versions, 'warnings': len(notices)}


def sdk_check(payload):
    seen = Counter()
    def listener(number, message):
        seen[number] += 1
    _, errors = Decoder(Stream.from_byte_array(bytearray(payload))).read(
        apply_scale_and_offset=False, convert_datetimes_to_dates=False,
        convert_types_to_strings=False, expand_sub_fields=False,
        expand_components=False, merge_heart_rates=False, mesg_listener=listener)
    return {'messages': dict(seen), 'errors': [type(error).__name__ for error in errors]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--limit', type=int, help='Only first N archives, for a smoke test')
    args = parser.parse_args()
    start = time.monotonic()
    checkpoint = args.data_dir / 'fit_inventory_checkpoint.json'
    parser_versions = {name: importlib.metadata.version(name)
                       for name in ('fitdecode', 'garmin-fit-sdk')}
    cached = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    cache = cached.get('cache', {}) if cached.get('parser_versions') == parser_versions else {}
    for result in cache.values():
        if 'messages' in result:
            result['messages'] = {int(key): count for key, count in result['messages'].items()}
    catalog = {}
    totals = Counter()
    message_counts = Counter()
    categories = Counter()
    errors = []
    sdk_checks = []
    signatures = set()
    min_time = max_time = None
    profile_versions = Counter()
    archive_dates = []
    archive_files = sorted((args.data_dir / 'raw').glob('*.zip'))
    if args.limit:
        archive_files = archive_files[:args.limit]
    for index, path in enumerate(archive_files, 1):
        archive_dates.append(path.stem)
        totals['archive_bytes'] += path.stat().st_size
        with ZipFile(path) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                payload = archive.read(entry)
                digest = sha256(payload).hexdigest()
                category = Path(entry.filename).stem.partition('_')[2]
                totals['file_occurrences'] += 1
                totals['uncompressed_bytes'] += len(payload)
                categories[category] += 1
                if digest not in cache:
                    try:
                        cache[digest] = decode_inventory(payload)
                    except Exception as error:
                        cache[digest] = {'error': type(error).__name__}
                result = cache[digest]
                if 'error' in result:
                    errors.append({'archive': path.name, 'entry': entry.filename, 'error': result['error']})
                    continue
                totals['decoded_file_occurrences'] += 1
                totals['warning_occurrences'] += result['warnings']
                profile_versions.update('.'.join(map(str, version)) if isinstance(version, (tuple, list))
                                        else str(version) for version in result['profile_versions'])
                message_counts.update(result['messages'])
                if result['min_time']:
                    min_time = min(min_time, result['min_time']) if min_time else result['min_time']
                    max_time = max(max_time, result['max_time']) if max_time else result['max_time']
                signature = tuple(sorted((f['message_num'], f['field_num'], f['name'], f['expanded'])
                                         for f in result['fields']))
                if signature not in signatures:
                    signatures.add(signature)
                    checked = sdk_check(payload)
                    sdk_checks.append({'archive': path.name, 'category': category,
                                       'counts_match': checked['messages'] == result['messages'],
                                       'errors': checked['errors']})
                for field in result['fields']:
                    key = (field['message_num'], field['field_num'], field['developer_index'],
                           field['name'], field['expanded'])
                    if key not in catalog:
                        catalog[key] = dict(field)
                        catalog[key].update({'count': 0, 'null_count': 0,
                                             'categories': set(), 'first_archive': path.stem,
                                             'last_archive': path.stem})
                        for name in ('base_types', 'byte_sizes', 'array_lengths', 'value_types'):
                            catalog[key][name] = set()
                    row = catalog[key]
                    row['count'] += field['count']
                    row['null_count'] += field['null_count']
                    row['categories'].add(category)
                    row['last_archive'] = path.stem
                    for name in ('base_types', 'byte_sizes', 'array_lengths', 'value_types'):
                        row[name].update(field[name])
                    for name in ('contains_null_array', 'outside_signed_int64'):
                        row[name] |= field[name]
        if index % 50 == 0:
            temporary = checkpoint.with_suffix('.tmp')
            temporary.write_text(json.dumps({'parser_versions': parser_versions, 'cache': cache}), encoding='utf-8')
            temporary.replace(checkpoint)
            print(f'{index}/{len(archive_files)} archives; {len(catalog)} field variants', flush=True)
    for row in catalog.values():
        for key in ('categories', 'base_types', 'byte_sizes', 'array_lengths', 'value_types'):
            row[key] = sorted(row[key])
    rows = sorted(catalog.values(), key=lambda f: (f['message_num'], f['field_num'], f['name']))
    stored = [field for field in rows if not field['expanded']]
    observed = sum(field['count'] for field in stored)
    named = sum(field['count'] for field in stored if field['parser_named'])
    manifest = json.loads((args.data_dir / 'collection.json').read_text(encoding='utf-8'))
    unresolved = sorted(day for day, row in manifest['days'].items()
                        if row['status'] == 'not_found_unverified')
    consecutive_start = archive_dates[-1] if archive_dates else None
    from datetime import date, timedelta
    if consecutive_start:
        available = set(archive_dates)
        current = date.fromisoformat(consecutive_start)
        while (current - timedelta(days=1)).isoformat() in available:
            current -= timedelta(days=1)
        consecutive_start = current.isoformat()
    totals['unique_files_decoded'] = sum('error' not in result for result in cache.values())
    summary = {
        'archives': len(archive_files), **dict(totals), 'unique_file_hashes': len(cache),
        'categories': dict(categories), 'message_types': len(message_counts),
        'messages': sum(message_counts.values()), 'field_variants': len(rows),
        'stored_field_variants': len(stored), 'expanded_field_variants': len(rows) - len(stored),
        'stored_field_occurrences': observed, 'named_field_occurrences': named,
        'named_occurrence_percent': round(100 * named / observed, 2) if observed else 0,
        'unknown_stored_field_variants': sum(not field['parser_named'] for field in stored),
        'sdk_only_named_variants': sum(not field['parser_named'] and bool(field['sdk_name']) for field in stored),
        'first_archive': archive_dates[0] if archive_dates else None,
        'last_archive': archive_dates[-1] if archive_dates else None,
        'continuous_archive_history_from': consecutive_start,
        'min_known_utc_time': min_time, 'max_known_utc_time': max_time,
        'unresolved_days': len(unresolved), 'fit_decode_errors': len(errors),
        'sdk_signature_checks': len(sdk_checks),
        'sdk_checks_with_errors': sum(bool(check['errors']) for check in sdk_checks),
        'sdk_message_count_mismatches': sum(not check['counts_match'] for check in sdk_checks),
        'elapsed_seconds': round(time.monotonic() - start, 1),
    }
    report = {'summary': summary,
              'parser_versions': parser_versions,
              'profile_versions': dict(profile_versions),
              'message_counts': dict(sorted(message_counts.items())),
              'fields': rows, 'errors': errors, 'sdk_checks': sdk_checks,
              'unresolved_dates': unresolved}
    output = args.data_dir / 'fit_inventory.json'
    enrich_public_profile(report)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    checkpoint.unlink(missing_ok=True)
    print(json.dumps(summary, indent=2))
    print(f'Report: {output}')


if __name__ == '__main__':
    main()
