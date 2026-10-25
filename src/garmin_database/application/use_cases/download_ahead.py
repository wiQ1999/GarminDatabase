"""One bounded download ahead of the SQL owner; no repository access here."""

from concurrent.futures import ThreadPoolExecutor, wait
from threading import Event

from garmin_database.domain.cancellation import Cancelled, check_stop


class DownloadAhead:
    def __init__(self, source, archives, stop, validate):
        self.source, self.archives, self.stop, self.validate = (
            source,
            archives,
            stop,
            validate,
        )
        self.abort = Event()
        self.pending = None
        self.executor = None

    def __enter__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="garmin-download"
        )
        return self

    def __exit__(self, *args):
        self.finish()

    def finish(self):
        self.abort.set()
        self.executor.shutdown(wait=True, cancel_futures=True)

    def abandoned(self):
        """Return an unconsumed attempt after finish(), without retaining payloads."""
        if self.pending is None:
            return None
        day, future, started = self.pending
        self.pending = None
        if not started.is_set():
            return day, None  # cancelled pacing/queue time was not an HTTP attempt
        if future.cancelled():
            return None
        try:
            error = future.result()
        except Cancelled:
            return None
        except Exception as error:
            return day, error
        return (day, error) if error is not None else None

    def start(self, day, delay):
        if self.pending is not None:
            raise RuntimeError("Pobieranie ma już oczekującą paczkę")
        started = Event()
        self.pending = (
            day,
            self.executor.submit(self.fetch, day, delay, started),
            started,
        )

    def has(self, day):
        return self.pending is not None and self.pending[0] == day

    def result(self, day):
        if not self.has(day):
            raise RuntimeError("Nieprawidłowa kolejność pobierania")
        _, future, _ = self.pending
        try:
            while not wait([future], timeout=0.05).done:
                check_stop(self.stop)
            check_stop(self.stop)
        except Cancelled:
            # Cleanup must still inspect/persist an eventual HTTP error for this
            # attempt; otherwise a prefetched 404 would be retried on resume.
            raise
        else:
            self.pending = None
            return future.result()

    def fetch(self, day, delay, started):
        if self.abort.wait(delay):
            raise Cancelled()
        check_stop(self.stop)
        started.set()
        try:
            payload = self.source.download_health_snapshot(day)
            self.validate(payload)
        except Cancelled:
            raise
        except Exception as error:
            return error
        # Preserve a successfully received original even if the SQL owner failed
        # or cancellation arrived during HTTP. It is recoverable on the next run.
        # A local save error propagates; it never repeats the network request.
        self.archives.save(day, payload)
        return None
