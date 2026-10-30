from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExportResult:
    directory: Path
    files: dict[str, int]


@dataclass
class SyncSummary:
    start: str
    end: str
    requested_days: int
    processed_days: int = 0
    successful_days: int = 0
    unresolved_days: int = 0
    download_errors: int = 0
    import_errors: int = 0
    archive_errors: int = 0
    confirmed_no_data_days: int = 0
    skipped_days: int = 0
    first_unresolved: str | None = None
    last_unresolved: str | None = None
    last_day: str | None = None
    last_day_result: str = ""
    halted: bool = False
    halt_reason: str | None = None
    http_status: int | None = None
    retry_not_before: str | None = None

    @property
    def error_count(self):
        return self.download_errors + self.import_errors + self.archive_errors

    @property
    def issue_count(self):
        return self.error_count + self.unresolved_days
