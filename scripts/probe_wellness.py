"""Download one wellness ZIP and compare decompressed content, without storing credentials."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta
from getpass import getpass
from hashlib import sha256
from io import BytesIO
import json
import logging
from pathlib import Path
import sys
from zipfile import ZipFile
from zoneinfo import ZoneInfo


def inventory(payload):
    entries = []
    with ZipFile(BytesIO(payload)) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError("ZIP CRC validation failed")
        for item in archive.infolist():
            if item.is_dir():
                continue
            content = archive.read(item)
            entries.append({
                "name": item.filename,
                "bytes": len(content),
                "sha256": sha256(content).hexdigest(),
            })
    if not entries:
        raise ValueError("Empty archive; no-data semantics need separate verification")
    return sorted(entries, key=lambda row: (row["name"], row["sha256"]))


def compare(reference, candidate):
    original = inventory(reference)
    downloaded = inventory(candidate)
    hashes = lambda entries: Counter((row["bytes"], row["sha256"]) for row in entries)
    return {
        "zip_bytes_equal": reference == candidate,
        "entries_equal_including_names": original == downloaded,
        "content_equal_ignoring_names": hashes(original) == hashes(downloaded),
        "reference": original,
        "candidate": downloaded,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", type=Path, help="Compare a local ZIP, without logging in")
    parser.add_argument("--output", type=Path, help="Download path; existing files are never overwritten")
    args = parser.parse_args()
    reference = args.reference.read_bytes()
    inventory(reference)
    if args.candidate:
        candidate = args.candidate.read_bytes()
    else:
        yesterday = datetime.now(ZoneInfo("Europe/Warsaw")).date() - timedelta(days=1)
        if args.date > yesterday:
            parser.error("Only completed calendar days can be downloaded")
        output = args.output or Path("data/raw") / f"{args.date.isoformat()}.zip"
        if output.exists():
            parser.error("Output exists; use --candidate to compare it")
        # Suppress library logs; never print raw exceptions that could contain secrets.
        logging.disable(logging.CRITICAL)
        from garminconnect import Garmin

        api = Garmin(
            email=input("Garmin email (local console): ").strip(),
            password=getpass("Garmin password: "),
            prompt_mfa=lambda: getpass("Garmin MFA code: ").strip(),
        )
        api.login()
        candidate = api.download_health_snapshot(args.date.isoformat())
        inventory(candidate)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output.open("xb") as destination:
                destination.write(candidate)
        except FileExistsError:
            raise
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        print(f"Downloaded original archive: {output.resolve()}")
    report = compare(reference, candidate)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["content_equal_ignoring_names"] else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f"Probe failed ({type(error).__name__}); no credentials were logged.", file=sys.stderr)
        sys.exit(1)
