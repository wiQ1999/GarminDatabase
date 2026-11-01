"""The CLI inherits saved ranges; explicit arguments take precedence."""

from datetime import date

import pytest

from garmin_database.adapters.inbound.cli.commands import apply_defaults, parse_args
from garmin_database.application.settings import Settings
from garmin_database.domain.time import today

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("command", ["sync", "sync-all", "import-local", "reprocess"])
def test_import_commands_use_shared_download_start(command):
    args = parse_args([command])
    apply_defaults(args, Settings(download_from="2025-06-07"))
    assert args.start == date(2025, 6, 7)
    assert args.end == today()


def test_export_uses_saved_range_and_summary_options():
    args = parse_args(["export"])
    apply_defaults(
        args,
        Settings(
            history_from="2025-01-02",
            history_to="2025-02-03",
            recent_days=14,
            summary_period="month",
        ),
    )
    assert (args.start, args.end) == (date(2025, 1, 2), date(2025, 2, 3))
    assert (args.recent_days, args.summary_period) == (14, "month")


def test_explicit_arguments_override_saved_options():
    args = parse_args(
        [
            "export",
            "--from",
            "2024-03-04",
            "--to",
            "2024-04-05",
            "--recent-days",
            "3",
            "--summary-period",
            "day",
        ]
    )
    apply_defaults(args, Settings(recent_days=14, summary_period="month"))
    assert (args.start, args.end) == (date(2024, 3, 4), date(2024, 4, 5))
    assert (args.recent_days, args.summary_period) == (3, "day")
