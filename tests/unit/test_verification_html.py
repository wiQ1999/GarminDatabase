from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.verify_garmin_html import SavedPage, compare_points, parse_point


def test_source_cards_use_visible_day_and_do_not_choose_conflicting_last_value(
    tmp_path, monkeypatch
):
    from datetime import date

    from scripts import verify_garmin_html as verification

    page = SavedPage()
    page.feed('<div class="NavigationComponent_datePickerContainer">Paź 25, 2026</div>')
    key = "hrv_status_summary.last_night_average"
    requested = []

    def channels(queries, service, parameter, start, end):
        requested.append((start, end))
        return [{"value": value, "validity": "valid"} for value in (40, 50)], {}

    monkeypatch.setattr(verification, "compare_channels", channels)
    checks, _ = verification.check_cards(
        tmp_path / "2026_07_16-hrv.html",
        page,
        [("Średnia nocna", "50 ms")],
        None,
        None,
        {key: {"key": key}},
    )
    assert requested == [(date(2026, 10, 25), date(2026, 10, 25))]
    assert checks[0]["status"] == "ambiguous_source_observations"
    assert not checks[0]["matched"]


def test_saved_html_extracts_cards_without_executing_scripts():
    page = SavedPage()
    page.feed("""<script>raise Error("untrusted")</script><div class="DataBlock_large__x">
      <div class="DataBlock_dataField__y">75 <span>ms</span></div>
      <span class="DataBlock_dataLabel__z">Średnia nocna</span></div>""")
    assert list(page.cards()) == [("Średnia nocna", "75 ms")]


def test_chart_labels_accept_whitespace_seconds_and_preserve_stage_semantics():
    point = parse_point("Sunday,  9 Aug, 02:05:00, 52. HRV.", 2026)
    assert point.instant == datetime(2026, 8, 9, 2, 5, tzinfo=ZoneInfo("Europe/Warsaw"))
    assert point.value == 52 and point.parameter == "hrv_value.value"
    phase = parse_point("Saturday, 31 Oct, 03:04:30, 1. Głęboki.", 2026)
    assert phase.value == 3  # Plot Y coordinate is not the FIT category code.
    assert parse_point("Saturday, 31 Oct, 03:04, No value. Series 1.", 2026) is None
    assert parse_point("Paź 4, 12. Średnia podczas snu.", 2026) is None


def test_timezone_diagnostic_does_not_silently_change_matching_rule():
    point = parse_point("Friday, 30 Oct, 12:00, 25. stress:stress_type_rest.", 2026)
    rows = [dict(time="2026-10-30T12:00:00+00:00", value=25, validity="valid")]
    result = compare_points([point], rows)
    assert result["exact_matches"] == 0
    assert result["time_shift_diagnostics"]["3600"] == 1
