"""Collect original daily Garmin wellness ZIPs and a resumable metadata report."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from getpass import getpass
from hashlib import sha256
from io import BytesIO
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import time
from zipfile import ZipFile
from zoneinfo import ZoneInfo

PROJECT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inspect_zip(payload):
    entries = []
    with ZipFile(BytesIO(payload)) as archive:
        for item in archive.infolist():
            if not item.is_dir():
                content = archive.read(item)  # also verifies CRC
                entries.append({
                    'name': item.filename,
                    'bytes': len(content),
                    'sha256': sha256(content).hexdigest(),
                })
    return {
        'status': 'downloaded' if entries else 'empty_zip',
        'bytes': len(payload),
        'sha256': sha256(payload).hexdigest(),
        'uncompressed_bytes': sum(entry['bytes'] for entry in entries),
        'file_count': len(entries),
        'files': entries,
    }


def error_metadata(error):
    """Never persist exception text, response bodies or authentication material."""
    status = None
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        status = getattr(getattr(current, 'response', None), 'status_code', None)
        if status is None:
            match = re.search(r'(?:API Error|HTTP|status[=: ]+)\s*(\d{3})', str(current), re.I)
            if match:
                status = int(match.group(1))
        if status is not None:
            break
        current = current.__cause__ or current.__context__
    name = type(error).__name__
    if 'TooManyRequests' in name:
        status = 429
    elif 'NotFound' in name:
        status = 404
    elif 'Authentication' in name and status is None:
        status = 401
    return {
        'status': 'not_found_unverified' if status == 404 else 'failed',
        'http_status': status,
        'error_type': name,
    }


def save_zip(path, payload):
    if path.exists():
        raise FileExistsError('Existing archives are never overwritten')
    temporary = path.with_suffix('.zip.part')
    try:
        with temporary.open('wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # The collection lock prevents two cooperating writers from replacing archives.
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_summary(manifest):
    records = manifest['days']
    completed = sorted(key for key, row in records.items() if row['status'] == 'downloaded')
    categories = Counter()
    for row in records.values():
        for entry in row.get('files', []):
            categories[Path(entry['name']).stem.partition('_')[2] or 'unknown'] += 1
    return {
        'updated_at': now(),
        'days_by_status': dict(Counter(row['status'] for row in records.values())),
        'first_nonempty_archive_date': completed[0] if completed else None,
        'last_nonempty_archive_date': completed[-1] if completed else None,
        'archive_bytes': sum(row.get('bytes', 0) for row in records.values()),
        'uncompressed_bytes': sum(row.get('uncompressed_bytes', 0) for row in records.values()),
        'files_by_name_category': dict(sorted(categories.items())),
        'unresolved_dates': sorted(key for key, row in records.items()
                                   if row['status'] not in ('downloaded', 'empty_zip')),
        'empty_zip_dates': sorted(key for key, row in records.items() if row['status'] == 'empty_zip'),
    }


def login(session):
    from garminconnect import Garmin, GarminConnectAuthenticationError
    if session.exists():
        api = Garmin(retry_attempts=1)
        try:
            api.login(str(session))
            return api
        except (GarminConnectAuthenticationError, FileNotFoundError):
            print('Stored session unavailable; please log in locally.')
    api = Garmin(
        email=input('Garmin email: ').strip(),
        password=getpass('Garmin password: '),
        prompt_mfa=lambda: getpass('Garmin MFA code: ').strip(),
        retry_attempts=1,
    )
    session.mkdir(parents=True, exist_ok=True)
    api.login(str(session))
    return api


def collect(args, manifest, api_factory, sleep=time.sleep):
    raw = args.data_dir / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    report_path = args.data_dir / 'collection.json'
    api = None
    failures = 0
    exit_code = 0
    total = (args.end - args.start).days + 1
    for index in range(total):
        day = (args.start + timedelta(days=index)).isoformat()
        path = raw / f'{day}.zip'
        old = manifest['days'].get(day, {})
        attempts = old.get('attempts', 0)
        if path.exists():
            # Revalidate originals even on resume; never replace corrupt local data.
            try:
                row = inspect_zip(path.read_bytes())
                row['origin'] = old.get('origin', 'local_archive')
            except Exception as error:
                row = {'status': 'local_invalid', 'error_type': type(error).__name__}
            action = 'local'
        elif old.get('status') == 'not_found_unverified' and not args.retry_unresolved:
            row = dict(old)
            action = 'previous 404; unresolved'
        else:
            if api is None:
                api = api_factory()
            for attempt in range(args.attempts):
                sleep(args.delay if attempt == 0 else max(args.delay, 2 ** attempt))
                attempts += 1
                try:
                    payload = api.download_health_snapshot(day)
                    row = inspect_zip(payload)
                    row['origin'] = 'webapi'
                    break
                except Exception as error:
                    row = error_metadata(error)
                    status = row['http_status']
                    if status in (401, 403, 404, 429) or (status is not None and status < 500):
                        break
            if row['status'] in ('downloaded', 'empty_zip'):
                # Disk/write errors are outside retries and never cause more API requests.
                save_zip(path, payload)
            action = row['status']
        row.update({'checked_at': now(), 'attempts': attempts})
        manifest['days'][day] = row
        manifest['summary'] = build_summary(manifest)
        atomic_json(report_path, manifest)
        print(f'[{index + 1}/{total}] {day}: {action}; {row.get("bytes", 0)} bytes', flush=True)
        if row['status'] not in ('downloaded', 'empty_zip'):
            exit_code = 2
        if row.get('http_status') in (401, 403, 429) or row['status'] == 'local_invalid':
            print('Stopped: authentication/rate limit or invalid local archive. Progress saved.')
            return 2
        failures = failures + 1 if row['status'] == 'failed' else 0
        if failures >= args.max_failures:
            print('Stopped after consecutive failures. Progress saved.')
            return 2
    return exit_code


def main():
    yesterday = datetime.now(ZoneInfo('Europe/Warsaw')).date() - timedelta(days=1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='start', type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument('--to', dest='end', type=date.fromisoformat, default=yesterday)
    parser.add_argument('--data-dir', type=Path, default=PROJECT / 'data')
    parser.add_argument('--session-dir', type=Path, default=PROJECT / 'private' / 'garmin-session')
    parser.add_argument('--delay', type=float, default=3, help='Seconds between download attempts')
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--max-failures', type=int, default=5)
    parser.add_argument('--retry-unresolved', action='store_true', help='Retry dates previously returning 404')
    args = parser.parse_args()
    if args.start > args.end or args.end > yesterday:
        parser.error('Range must be ordered and end no later than yesterday in Europe/Warsaw')
    if not math.isfinite(args.delay) or args.delay < 0 or args.attempts < 1 or args.max_failures < 1:
        parser.error('Invalid delay, attempts or failure limit')
    args.data_dir.mkdir(parents=True, exist_ok=True)
    lock = args.data_dir / 'collection.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        parser.error('collection.lock exists; remove it only after confirming no collector is running')
    os.close(descriptor)
    logging.disable(logging.CRITICAL)
    try:
        path = args.data_dir / 'collection.json'
        manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
            'schema_version': 1,
            'endpoint': '/download-service/files/wellness/{date}',
            'timezone': 'Europe/Warsaw',
            'days': {},
        }
        if manifest.get('schema_version') != 1:
            raise ValueError('Unsupported manifest version')
        manifest['last_requested_range'] = {'from': args.start.isoformat(), 'to': args.end.isoformat()}
        result = collect(args, manifest, lambda: login(args.session_dir))
        print(json.dumps(manifest.get('summary', {}), ensure_ascii=False, indent=2))
        print(f'Report: {path.resolve()}')
        return result
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nInterrupted; completed days remain saved. Run the same command to resume.', file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f'Collector failed ({type(error).__name__}); no raw error or credentials logged.', file=sys.stderr)
        sys.exit(1)
