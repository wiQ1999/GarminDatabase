from datetime import date
from threading import Event
from types import SimpleNamespace

import pytest

from garmin_database.adapters.outbound.filesystem.settings_json import Settings
from garmin_database.bootstrap.dependencies import Services
from tests.support.fixtures import fit_bytes, zip_bytes

pytestmark = pytest.mark.integration


def test_summary_matches_real_database_with_404_crc_failure_and_successful_last_day(
    tmp_path,
):
    services = Services(Settings(data_dir=str(tmp_path)))
    bad = fit_bytes()
    bad = bad[:-1] + bytes([bad[-1] ^ 1])

    def download(day):
        if day == "2024-06-19":
            error = RuntimeError("private response")
            error.response = SimpleNamespace(status_code=404)
            raise error
        return zip_bytes(bad if day == "2024-06-20" else fit_bytes())

    services.source_factory = lambda: SimpleNamespace(download_health_snapshot=download)
    events = []
    result = services.sync(
        date(2024, 6, 19),
        date(2024, 6, 21),
        Event(),
        lambda *a: events.append(a),
        delay=0,
        detailed=True,
    )
    assert result.processed_days == result.requested_days == 3
    assert result.successful_days == result.unresolved_days == result.import_errors == 1
    assert (
        result.download_errors == result.archive_errors == 0 and result.issue_count == 2
    )
    assert (
        result.last_day == "2024-06-21"
        and result.last_day_result == "import zakończony bez błędów"
    )
    assert events[-1][1] == "Wynik dnia: import zakończony bez błędów"
    assert all("private" not in event[1] for event in events)
    with services.db.connect(readonly=True) as conn:
        assert (
            conn.execute(
                "SELECT download_status FROM import_days WHERE day='2024-06-19'"
            ).fetchone()[0]
            == "not_found_unverified"
        )
        assert dict(
            conn.execute("SELECT status,count(*) FROM file_decodes GROUP BY status")
        ) == {"failed": 1, "complete": 1}
