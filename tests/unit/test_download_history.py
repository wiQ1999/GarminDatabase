import importlib.util
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location(
    "collector", Path(__file__).resolve().parents[2] / "scripts" / "download_history.py"
)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def bundle():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("sample_WELLNESS.fit", b"original bytes")
    return stream.getvalue()


class FakeAPI:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def download_health_snapshot(self, day):
        self.calls.append(day)
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response


class CollectorTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[2] / "data" / "test-work"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temporary = TemporaryDirectory(dir=test_root)
        self.addCleanup(self.temporary.cleanup)
        self.args = SimpleNamespace(
            data_dir=Path(self.temporary.name),
            start=date(2024, 1, 1),
            end=date(2024, 1, 2),
            attempts=2,
            delay=0,
            max_failures=5,
            retry_unresolved=False,
        )
        self.manifest = {"schema_version": 1, "days": {}}

    def collect(self, api):
        return collector.collect(
            self.args, self.manifest, lambda: api, sleep=lambda _: None
        )

    def test_download_and_resume_without_login_or_overwrite(self):
        payload = bundle()
        api = FakeAPI([payload, payload])
        self.assertEqual(self.collect(api), 0)
        self.assertEqual(len(api.calls), 2)

        def factory():
            self.fail("Resume should not log in")

        self.assertEqual(collector.collect(self.args, self.manifest, factory), 0)
        self.assertEqual(
            (self.args.data_dir / "raw/2024-01-01.zip").read_bytes(), payload
        )

    def test_404_remains_unverified_and_does_not_stop_history(self):
        api = FakeAPI([RuntimeError("API Error 404 - secret"), bundle()])
        self.assertEqual(self.collect(api), 2)
        row = self.manifest["days"]["2024-01-01"]
        self.assertEqual(row["status"], "not_found_unverified")
        self.assertEqual(len(api.calls), 2)
        self.assertNotIn("secret", (self.args.data_dir / "collection.json").read_text())
        self.assertEqual(self.collect(FakeAPI([])), 2)

    def test_rate_limit_stops_without_retrying_or_advancing(self):
        api = FakeAPI([RuntimeError("API Error 429 - secret")])
        self.assertEqual(self.collect(api), 2)
        self.assertEqual(api.calls, ["2024-01-01"])
        self.assertNotIn("2024-01-02", self.manifest["days"])

    def test_explicit_retry_of_unresolved_date(self):
        self.args.end = self.args.start
        self.collect(FakeAPI([RuntimeError("API Error 404")]))
        self.args.retry_unresolved = True
        self.assertEqual(self.collect(FakeAPI([bundle()])), 0)
        self.assertEqual(self.manifest["days"]["2024-01-01"]["attempts"], 2)

    def test_empty_zip_is_preserved_without_claiming_no_data(self):
        self.args.end = self.args.start
        stream = BytesIO()
        with ZipFile(stream, "w"):
            pass
        payload = stream.getvalue()
        self.assertEqual(self.collect(FakeAPI([payload])), 0)
        self.assertEqual(self.manifest["days"]["2024-01-01"]["status"], "empty_zip")
        self.assertEqual(
            (self.args.data_dir / "raw/2024-01-01.zip").read_bytes(), payload
        )

    def test_transient_failure_is_retried(self):
        self.args.end = self.args.start
        api = FakeAPI([RuntimeError("API Error 503 - secret"), bundle()])
        self.assertEqual(self.collect(api), 0)
        self.assertEqual(self.manifest["days"]["2024-01-01"]["attempts"], 2)

    def test_local_zip_recovered_after_manifest_write_failure(self):
        self.args.end = self.args.start
        with patch.object(collector, "atomic_json", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.collect(FakeAPI([bundle()]))
        self.manifest = {"schema_version": 1, "days": {}}
        self.assertEqual(self.collect(FakeAPI([])), 0)
        self.assertEqual(self.manifest["days"]["2024-01-01"]["origin"], "local_archive")

    def test_corrupt_local_file_is_preserved(self):
        raw = self.args.data_dir / "raw"
        raw.mkdir()
        path = raw / "2024-01-01.zip"
        path.write_bytes(b"corrupt")
        self.assertEqual(self.collect(FakeAPI([])), 2)
        self.assertEqual(path.read_bytes(), b"corrupt")
        self.assertEqual(self.manifest["days"]["2024-01-01"]["status"], "local_invalid")


if __name__ == "__main__":
    unittest.main()
