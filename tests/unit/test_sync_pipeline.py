"""Synchronize a bounded download ahead without moving SQL into that worker."""

import threading
import time
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from garmin_database.adapters.outbound.filesystem.archives import Archives
from garmin_database.application.use_cases.download_ahead import DownloadAhead
from garmin_database.application.use_cases.synchronize import Sync, validate_zip
from garmin_database.domain.cancellation import Cancelled
from tests.support.fixtures import zip_bytes

pytestmark = pytest.mark.unit
START, END = date(2024, 6, 19), date(2024, 6, 21)


class Repository:
    def __init__(self):
        self.owner = threading.get_ident()
        self.rows = {}
        self.initialized = 0
        self.attempts = []

    def check_owner(self):
        assert threading.get_ident() == self.owner

    @contextmanager
    def writer_lock(self):
        self.check_owner()
        yield

    def initialize(self):
        self.check_owner()
        self.initialized += 1

    def restore_days(self, days):
        self.check_owner()

    def day(self, day):
        self.check_owner()
        return self.rows.get(day)

    def attempt(self, day):
        self.check_owner()
        self.attempts.append(day)

    def failed(self, day, status, error_type):
        self.check_owner()
        self.rows[day] = dict(
            download_status="not_found_unverified" if status == 404 else "failed"
        )

    def cancel_attempt(self, day):
        self.check_owner()
        self.attempts.remove(day)

    def local_invalid(self, day, error_type):
        self.check_owner()


def test_next_zip_downloads_during_import_with_one_sql_owner_and_one_day_buffer(
    tmp_path,
):
    repository, store = Repository(), Archives(tmp_path)
    second_saved = threading.Event()
    requests, imports, network_threads = [], [], set()
    save = store.save

    def save_zip(day, payload):
        save(day, payload)
        if day == "2024-06-20":
            second_saved.set()

    store.save = save_zip

    def download(day):
        assert day in repository.attempts  # persisted before HTTP begins
        network_threads.add(threading.get_ident())
        requests.append(day)
        return zip_bytes()

    def import_zip(path, *args, **kwargs):
        repository.check_owner()
        imports.append(path.stem)
        if path.stem == "2024-06-19":
            assert second_saved.wait(5), "download must overlap the first import"
            assert requests == ["2024-06-19", "2024-06-20"]
        return 0

    sync = Sync(
        repository,
        store,
        SimpleNamespace(archive=import_zip),
        SimpleNamespace(download_health_snapshot=download),
        delay=0,
    )
    assert sync.run(START, END, threading.Event()) == 0
    assert imports == requests == ["2024-06-19", "2024-06-20", "2024-06-21"]
    assert len(network_threads) == 1 and repository.owner not in network_threads
    assert repository.initialized == 1


@pytest.mark.parametrize("status", [401, 403, 429])
def test_fatal_prefetched_response_stops_before_a_third_request(tmp_path, status):
    repository, store = Repository(), Archives(tmp_path)
    failed = threading.Event()
    requests, imports = [], []

    def download(day):
        requests.append(day)
        if day == "2024-06-20":
            failed.set()
            error = RuntimeError("synthetic-private-body")
            error.response = SimpleNamespace(status_code=status)
            raise error
        return zip_bytes()

    def import_zip(path, *args, **kwargs):
        imports.append(path.stem)
        assert failed.wait(5)
        return 0

    stages = []
    sync = Sync(
        repository,
        store,
        SimpleNamespace(archive=import_zip),
        SimpleNamespace(download_health_snapshot=download),
        delay=0,
    )
    assert sync.run(START, END, threading.Event(), lambda *a: stages.append(a[1])) == 1
    assert requests == ["2024-06-19", "2024-06-20"] and imports == ["2024-06-19"]
    assert all("private" not in stage for stage in stages)


@pytest.mark.parametrize("outcome", ["success", "404"])
def test_cancel_joins_prefetch_preserves_zip_or_records_unresolved_day(
    tmp_path, outcome
):
    repository, store = Repository(), Archives(tmp_path)
    stop, second_started, finish_http = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    requests = []

    def download(day):
        requests.append(day)
        if day == "2024-06-20":
            second_started.set()
            assert finish_http.wait(5)
            if outcome == "404":
                error = RuntimeError("synthetic-private-body")
                error.response = SimpleNamespace(status_code=404)
                raise error
        return zip_bytes()

    def import_zip(*args, **kwargs):
        assert second_started.wait(5)
        stop.set()
        finish_http.set()
        return 0

    source = SimpleNamespace(download_health_snapshot=download)
    sync = Sync(repository, store, SimpleNamespace(archive=import_zip), source, delay=0)
    with pytest.raises(Cancelled):
        sync.run(START, END, stop)
    assert not any(t.name.startswith("garmin-download") for t in threading.enumerate())
    assert requests == ["2024-06-19", "2024-06-20"]
    sync.importer = SimpleNamespace(archive=lambda *a, **kw: 0)
    assert sync.run(START, date(2024, 6, 20), threading.Event()) == (outcome == "404")
    assert len(requests) == 2
    assert store.exists("2024-06-20") == (outcome == "success")


def test_cancel_wakes_long_initial_delay_without_issuing_http(tmp_path):
    stop = threading.Event()
    calls = []
    begin = time.monotonic()
    with DownloadAhead(
        SimpleNamespace(download_health_snapshot=calls.append),
        Archives(tmp_path),
        stop,
        validate_zip,
    ) as ahead:
        ahead.start("2024-06-19", 60)
        stop.set()
        with pytest.raises(Cancelled):
            ahead.result("2024-06-19")
    assert time.monotonic() - begin < 2 and calls == []


def test_cancel_during_prefetch_delay_does_not_count_a_network_attempt(
    tmp_path, monkeypatch
):
    repository, store, stop = Repository(), Archives(tmp_path), threading.Event()
    start = DownloadAhead.start
    requests = []

    def delayed_second(ahead, day, delay):
        start(ahead, day, 60 if day == "2024-06-20" else 0)

    monkeypatch.setattr(DownloadAhead, "start", delayed_second)
    source = SimpleNamespace(
        download_health_snapshot=lambda day: requests.append(day) or zip_bytes()
    )
    sync = Sync(
        repository,
        store,
        SimpleNamespace(archive=lambda *a, **kw: stop.set() or 0),
        source,
        delay=0,
    )
    with pytest.raises(Cancelled):
        sync.run(START, END, stop)
    assert requests == repository.attempts == ["2024-06-19"]


def test_disk_failure_is_not_retried_as_http(tmp_path):
    repository, store = Repository(), Archives(tmp_path)
    requests = []

    def fail_save(*args):
        raise OSError("synthetic disk failure")

    store.save = fail_save
    source = SimpleNamespace(
        download_health_snapshot=lambda day: requests.append(day) or zip_bytes()
    )
    sync = Sync(
        repository,
        store,
        SimpleNamespace(archive=lambda *a, **kw: pytest.fail("must not import")),
        source,
        delay=0,
    )
    with pytest.raises(OSError):
        sync.run(START, END, threading.Event())
    assert requests == ["2024-06-19"]


def test_writer_failure_joins_download_and_keeps_the_received_original(tmp_path):
    repository, store = Repository(), Archives(tmp_path)
    saved = threading.Event()
    save = store.save

    def save_zip(day, payload):
        save(day, payload)
        if day == "2024-06-20":
            saved.set()

    store.save = save_zip

    def fail_import(*args, **kwargs):
        assert saved.wait(5)
        raise RuntimeError("synthetic writer failure")

    sync = Sync(
        repository,
        store,
        SimpleNamespace(archive=fail_import),
        SimpleNamespace(download_health_snapshot=lambda day: zip_bytes()),
        delay=0,
    )
    with pytest.raises(RuntimeError):
        sync.run(START, END, threading.Event())
    assert store.exists("2024-06-20")
    assert not any(t.name.startswith("garmin-download") for t in threading.enumerate())
