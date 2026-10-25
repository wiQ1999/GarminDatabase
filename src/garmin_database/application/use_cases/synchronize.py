import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
from zipfile import ZipFile

from garmin_database.application.dto import SyncSummary
from garmin_database.application.errors import LoginFailed, SessionRequired
from garmin_database.application.ports import (
    ArchiveImporter,
    ArchiveStore,
    ImportRepository,
)
from garmin_database.application.use_cases.download_ahead import DownloadAhead
from garmin_database.domain.cancellation import Cancelled, check_stop
from garmin_database.domain.time import dates


class Sync:
    """Download/import workflow. Contracts: docs/04-synchronization.md."""

    def __init__(
        self,
        repository: ImportRepository,
        archives: ArchiveStore,
        importer: ArchiveImporter,
        source=None,
        delay=3.0,
    ):
        self.repository = repository
        self.archives = archives
        self.importer = importer
        self.source = source
        self.delay = delay

    def restore_manifest(self):
        self.repository.restore_days(self.archives.restore_manifest())

    def run(
        self, start, end, stop, progress=lambda *a: None, local_only=False, force=False
    ):
        return self.run_summary(
            start, end, stop, progress, local_only, force
        ).issue_count

    def run_summary(
        self, start, end, stop, progress=lambda *a: None, local_only=False, force=False
    ):
        requested = list(dates(start, end))
        summary = SyncSummary(start.isoformat(), end.isoformat(), len(requested))
        with self.repository.writer_lock():
            self.repository.initialize()
            self.restore_manifest()
            return self.process_days(
                requested, stop, progress, local_only, force, summary
            )

    def process_days(self, requested, stop, progress, local_only, force, summary):
        with DownloadAhead(self.source, self.archives, stop, validate_zip) as ahead:
            try:
                return self.process_ordered(
                    requested, stop, progress, local_only, force, ahead, summary
                )
            finally:
                ahead.finish()
                abandoned = ahead.abandoned()
                if abandoned is not None:
                    day, error = abandoned
                    if error is None:
                        self.repository.cancel_attempt(day)
                    else:
                        self.repository.failed(
                            day, error_status(error), type(error).__name__
                        )

    def process_ordered(
        self, requested, stop, progress, local_only, force, ahead, summary
    ):
        consecutive = 0
        for index, day in enumerate(requested, 1):
            check_stop(stop)
            text = day.isoformat()
            summary.processed_days = index
            summary.last_day = text

            def report(message):
                progress(text, message, index, len(requested))

            report("Rozpoczynanie obsługi dnia")
            old = self.repository.day(text)
            if self.archives.exists(text) and not ahead.has(text):
                failed, halt = self.import_local(text, stop, progress, force, report)
                self.record_import(summary, failed, halt, report)
                if halt:
                    summary.halted = index < len(requested)
                    return summary
                continue
            if local_only:
                summary.skipped_days += 1
                self.finish_day(summary, report, "pominięto; brak lokalnego ZIP")
                continue
            if self.already_checked(old):
                self.record_checked_day(summary, old, text, report)
                continue
            next_day = requested[index].isoformat() if index < len(requested) else None
            failed, status, halt = self.download_day(
                text, stop, progress, report, ahead, next_day
            )
            self.record_download(summary, text, failed, status, halt, report)
            if halt:
                summary.halted = index < len(requested)
                return summary
            consecutive = self.consecutive_failures(consecutive, text, status)
            if consecutive >= 5:
                summary.halted = index < len(requested)
                break
        return summary

    @staticmethod
    def finish_day(summary, report, outcome):
        summary.last_day_result = outcome
        report("Wynik dnia: " + outcome)

    def record_import(self, summary, failed, archive_error, report):
        if archive_error:
            summary.archive_errors += failed
            self.finish_day(
                summary, report, "błąd archiwum; import dnia nie został ukończony"
            )
        elif failed:
            summary.import_errors += failed
            self.finish_day(summary, report, f"błędy importu FIT: {failed}")
        else:
            summary.successful_days += 1
            self.finish_day(summary, report, "import zakończony bez błędów")

    def record_unresolved(self, summary, day, report):
        summary.unresolved_days += 1
        summary.first_unresolved = summary.first_unresolved or day
        summary.last_unresolved = day
        self.finish_day(
            summary,
            report,
            "nierozstrzygnięty HTTP 404; brak danych nie został potwierdzony",
        )

    def record_checked_day(self, summary, old, day, report):
        if old["download_status"] == "not_found_unverified":
            self.report_unresolved(old, report)
            self.record_unresolved(summary, day, report)
        else:
            summary.confirmed_no_data_days += 1
            self.finish_day(summary, report, "potwierdzony brak danych")

    def record_download(self, summary, day, failed, status, halt, report):
        if status == 404:
            self.record_unresolved(summary, day, report)
        elif status is not None or halt or not self.archives.exists(day):
            summary.download_errors += failed
            self.finish_day(summary, report, self.failed_download_outcome(status, halt))
        else:
            self.record_import(summary, failed, False, report)

    @staticmethod
    def failed_download_outcome(status, halt):
        if halt and status is None:
            return "błąd pobierania: brak sesji Garmin; zaloguj się w Ustawieniach; import dnia nie został wykonany"
        code = f" (HTTP {status})" if status is not None else ""
        return "błąd pobierania" + code + "; import dnia nie został wykonany"

    @staticmethod
    def already_checked(old):
        return bool(
            old
            and old["download_status"] in {"not_found_unverified", "no_data_confirmed"}
        )

    def consecutive_failures(self, previous, day, status):
        # FIT errors do not count as consecutive failed network requests.
        return 0 if self.archives.exists(day) or status == 404 else previous + 1

    def import_local(self, day, stop, progress, force, report):
        try:
            return self.importer.archive(
                self.archives.path(day), stop, progress, force
            ), False
        except Cancelled:
            raise
        except Exception as error:
            self.repository.local_invalid(day, type(error).__name__)
            report("Nieprawidłowe archiwum lokalne")
            return 1, True

    @staticmethod
    def report_unresolved(old, report):
        if old["download_status"] != "not_found_unverified":
            return 0
        report(
            "Nierozstrzygnięty dzień — poprzednio HTTP 404. Pominięto ponowne żądanie; nie potwierdzono braku danych."
        )
        return 1

    def prepare_download(self, day, ahead):
        if day is None or self.archives.exists(day):
            return
        if self.already_checked(self.repository.day(day)):
            return
        self.repository.attempt(day)
        ahead.start(day, self.delay)

    def download_day(self, day, stop, progress, report, ahead, next_day):
        if not ahead.has(day):
            self.prepare_download(day, ahead)
        error = self.receive_download(day, stop, report, ahead)
        if error is not None:
            status = error_status(error)
            halt = isinstance(error, SessionRequired) or status in {401, 403, 429}
            return 1, status, halt
        # Only validated, saved ZIPs reach this point. Register the next attempt
        # on the SQL owner's thread before allowing HTTP to overlap this import.
        self.prepare_download(next_day, ahead)
        errors = self.importer.archive(
            self.archives.path(day), stop, progress, origin="webapi"
        )
        return errors, None, False

    def receive_download(self, day, stop, report, ahead):
        status = None
        for attempt in range(3):
            error = ahead.result(day)
            if error is None:
                return None
            status = error_status(error)
            self.repository.failed(day, status, type(error).__name__)
            report(download_error_message(error, status))
            if self.stop_retry(error, status, attempt):
                return error
            delay = retry_after(error, max(self.delay, 2 ** (attempt + 1)))
            if stop.wait(delay):
                raise Cancelled()
            self.repository.attempt(day)
            ahead.start(day, 0)
        return error

    @staticmethod
    def stop_retry(error, status, attempt):
        return (
            isinstance(error, SessionRequired)
            or status in {401, 403, 429}
            or status is not None
            and status < 500
            or attempt == 2
        )


def error_status(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status is not None:
            return int(status)
        match = re.search(
            r"(?:API Error|HTTP|status[=: ]+)\s*(\d{3})", str(error), re.I
        )
        if match:
            return int(match.group(1))
        name = type(error).__name__
        if "Authentication" in name:
            return 401
        if "TooManyRequests" in name:
            return 429
        error = error.__cause__ or error.__context__
    return None


def validate_zip(payload):
    with ZipFile(BytesIO(payload)) as z:
        if z.testzip() is not None:
            raise ValueError("Nieprawidłowy CRC ZIP")
        return bool([x for x in z.infolist() if not x.is_dir()])


def download_error_message(error, status):
    """Explain failures without exposing upstream responses or credentials."""
    if isinstance(error, (SessionRequired, LoginFailed)):
        return str(error)
    explanations = {
        401: "Sesja Garmin wygasła lub została odrzucona. Zaloguj się w Ustawieniach. Pobieranie zatrzymano.",
        403: "Garmin odmówił dostępu do archiwum. Pobieranie zatrzymano.",
        404: "Garmin nie zwrócił archiwum dla tej daty. Dzień pozostaje nierozstrzygnięty; sprawdzam kolejne dni.",
        429: "Garmin ograniczył liczbę żądań. Pobieranie zatrzymano; odczekaj przed wznowieniem.",
    }
    code = f"HTTP {status}" if status is not None else type(error).__name__
    explanation = explanations.get(
        status, "Nie udało się pobrać lub zweryfikować ZIP z Garmin."
    )
    return f"Błąd pobierania — {code}: {explanation}"


def retry_after(error, fallback, now=None):
    """Respect the server delay without persisting response headers or bodies."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        headers = getattr(getattr(error, "response", None), "headers", {}) or {}
        value = headers.get("Retry-After")
        if value is not None:
            try:
                delay = (
                    int(value)
                    if str(value).isdigit()
                    else (
                        parsedate_to_datetime(str(value))
                        - (now or datetime.now(timezone.utc))
                    ).total_seconds()
                )
                return max(fallback, delay)
            except (TypeError, ValueError, OverflowError):
                pass
        error = error.__cause__ or error.__context__
    return fallback
