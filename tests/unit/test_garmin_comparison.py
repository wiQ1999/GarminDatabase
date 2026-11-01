from datetime import date

from scripts.garmin_channels import chart_expected, difference, export_rows, signature
from scripts.garmin_differences import compare_points
from scripts.garmin_reference import (
    PHASES,
    RESP,
    SPO2,
    SavedPage,
    parse_reference_point,
    parse_reference_range,
    reference,
    visible_range,
)


def test_reference_uses_visible_range_instead_of_filename():
    page = SavedPage()
    page.feed(
        '<div class="NavigationComponent_datePickerContainer__x">Paź 25 - Paź 31</div>'
    )
    assert visible_range(page, "2026_07_16-sen.html")[:2] == (
        date(2026, 10, 25),
        date(2026, 10, 31),
    )


def test_year_range_keeps_explicit_years():
    page = SavedPage()
    page.feed(
        '<div class="NavigationComponent_datePickerContainer__x">Lis 2, 2025 - Paź 31, 2026</div>'
    )
    assert visible_range(page, "2025_11_02-2026_10_31-sen.html")[:2] == (
        date(2025, 11, 2),
        date(2026, 10, 31),
    )


def test_generic_series_is_only_mapped_with_semantic_axis_context():
    label = "Wednesday, 28 Oct, 02:03, 97. Series 1."
    assert (
        parse_reference_point(label, 2026, "pulseOxYAxis", "spo2")["parameter"] == SPO2
    )
    assert parse_reference_point(label, 2026, "dotsYAxis", "spo2") is None


def test_range_points_are_explicit_bin_bounds_not_raw_samples():
    label = "Thursday, 29 Oct, 03:00, low: 10, high: 18. Wartości maks./min.."
    values = parse_reference_range(label, 2026, "respirationYAxis", "respiration")
    assert [r["value"] for r in values] == [10, 18]
    assert all(r["parameter"] == RESP for r in values)
    assert values[0]["method"] == "bin_statistic_minimum"


def test_sleep_phase_uses_semantic_name_instead_of_plot_coordinate():
    point = parse_reference_point(
        "Saturday, 31 Oct, 03:01:30, 1. Głęboki.", 2026, "", "sleep"
    )
    assert point["value"] == PHASES["Głęboki"]


def test_difference_detects_extra_duplicates_in_both_directions():
    assert difference([1, 1, 2], [1, 2, 2]) == dict(
        expected=3, actual=3, missing=1, extra=1, equal=False
    )


def test_export_comparison_keeps_unknown_time_validity_and_provenance():
    doc = dict(
        columns=["time", "value", "source", "validity"],
        data=[[None, 8, "s1", "i"]],
        sources={"s1": dict(requested_day="2026-10-30")},
        validity_labels={"i": "invalid"},
    )
    row = export_rows(doc)[0]
    assert signature(row) == (None, "8", "invalid", "2026-10-30")
    assert chart_expected([row], dict(representation="sample")) == []


def test_shift_diagnostic_does_not_turn_a_mismatch_into_a_pass():
    points = [dict(time="2026-10-30T12:00:00+01:00", value=20)]
    actual = [(1760000000, 99)]
    from datetime import datetime

    actual = [(datetime.fromisoformat(points[0]["time"]).timestamp() + 3600, 20)]
    result = compare_points(points, actual)
    assert result["exact"] == 0 and result["shift_diagnostic"]["3600"] == 1


def test_interval_diagnostic_does_not_claim_exact_timestamp_equality():
    points = [dict(time="2026-10-30T12:00:30+01:00", value=2)]
    from datetime import datetime

    t = datetime.fromisoformat("2026-10-30T12:00:00+01:00").timestamp()
    result = compare_points(points, [(t, 2), (t + 60, 3)], phase=True)
    assert result["exact"] == 0 and result["bounded_state_continuation_diagnostic"] == 1


def test_all_reference_features_are_classified_even_when_unsupported(tmp_path):
    path = tmp_path / "2026_10_31-sen.html"
    path.write_text(
        '<h3>Sen</h3><div class="NavigationComponent_datePickerContainer__x">Paź 31</div><div><span class="DataBlock_dataField__x">7 h</span><span class="DataBlock_dataLabel__x">Czas trwania</span></div>',
        encoding="utf-8",
    )
    result = reference(path)
    assert result["topic"] == "sleep"
    assert result["cards"][0]["parameter"] is None
    assert result["cards"][0]["value"] is None


def test_empty_matching_channels_are_not_marked_as_observed_data():
    from scripts.compare_garmin_sources import coverage_audit

    result = coverage_audit(
        {"synthetic": {}},
        [
            dict(
                start="2026-10-30",
                end="2026-10-30",
                parameters={"synthetic": dict(sql_rows=0)},
            )
        ],
    )
    assert not result["synthetic"]["observed_data_tested"]


def test_weighted_history_and_unweighted_plot_are_distinct_statistics():
    from scripts.garmin_differences import reduce_values, weighted_card_mean

    days = [dict(mean=10, valid_count=1), dict(mean=30, valid_count=3)]
    assert weighted_card_mean(days) == 25
    assert reduce_values([10, 30], "mean") == 20


def test_period_reference_preserves_statistic_scope():
    from scripts.garmin_reference import HR, card_metric, reference_cards

    assert card_metric("Średnia wysokiego", "hr")[:2] == (HR, "mean_daily_maximum")
    page = SavedPage()
    page.feed(
        '<div><span class="DataBlock_dataField__x">12</span><span class="DataBlock_dataLabel__x">Najniższa</span></div>'
    )
    assert (
        reference_cards(page, "stress", period=True)[0]["operation"]
        == "minimum_daily_mean"
    )
    assert reference_cards(page, "stress")[0]["operation"] == "minimum"


def test_period_card_reduces_daily_statistics_instead_of_global_samples():
    from scripts.garmin_differences import daily_card_value

    daily = [dict(mean=10, maximum=20), dict(mean=30, maximum=80)]
    data = dict(
        mcp=daily, history=dict(columns=["mean", "maximum"], data=[[10, 20], [30, 80]])
    )
    for channel in ("mcp", "export"):
        assert daily_card_value(data, "mean_daily_maximum", channel)[0] == 50
        assert daily_card_value(data, "minimum_daily_mean", channel)[0] == 10
        assert daily_card_value(data, "mean_daily_mean", channel)[0] == 20


def test_mean_plot_does_not_supply_unavailable_daily_extrema():
    from scripts.garmin_differences import daily_card_value

    data = dict(chart=[(1, 10, ""), (2, 30, "")])
    assert daily_card_value(data, "mean_daily_maximum", "chart") == (
        None,
        "daily_extrema_not_in_plot",
    )
    assert daily_card_value(data, "maximum_daily_mean", "chart")[0] == 30


def test_difference_locators_omit_values_and_validate_report_counts():
    from datetime import datetime

    from scripts.garmin_point_locators import point_mismatch_rows

    t = datetime.fromisoformat("2026-10-30T12:00:00+01:00").timestamp()
    source = dict(file="synthetic.html", export_directory="synthetic-export")
    feature = dict(
        parameter="synthetic", label="sample", channels={"chart": dict(exact=1)}
    )
    points = [
        (1, dict(time="2026-10-30T12:00:00+01:00", value=10)),
        (2, dict(time="2026-10-30T12:01:00+01:00", value=20)),
    ]
    result = list(
        point_mismatch_rows(source, feature, points, [(t, 10), (t + 60, 15)], "chart")
    )
    assert len(result) == 1 and result[0]["reason"] == "different_value"
    assert "value" not in result[0]
    assert result[0]["parsed_reference_point"] == 2


def test_table_weeks_preserve_explicit_cross_year_and_inferred_year():
    from scripts.garmin_reference_tables import table_range

    begin, end = date(2025, 11, 2), date(2026, 10, 31)
    assert table_range("Gru 28, 2025 - Sty 3, 2026", begin, end) == (
        date(2025, 12, 28),
        date(2026, 1, 3),
    )
    assert table_range("Paź 25-31", begin, end) == (
        date(2026, 10, 25),
        date(2026, 10, 31),
    )


def test_table_cells_are_not_dropped_when_only_one_column_is_stored():
    from scripts.garmin_reference_tables import table_cards

    page = SavedPage()
    page.feed(
        "<table><tr><th>Data</th><th>Wynik</th><th>Czas trwania</th></tr><tr><td>Paź 30</td><td>80</td><td>7h</td></tr></table>"
    )
    cards = table_cards(page, "sleep", date(2026, 10, 25), date(2026, 10, 31))
    assert len(cards) == 2 and cards[0]["range_start"] == "2026-10-30"
    assert cards[0]["parameter"] == "sleep_assessment.overall_sleep_score"
    assert cards[1]["parameter"] is None


def test_accessible_chart_scalar_is_a_reference_card():
    from scripts.garmin_reference_tables import accessible_cards

    page = SavedPage()
    page.feed('<svg aria-label="96%Śr. SpO₂. Highcharts interactive chart."></svg>')
    assert accessible_cards(page)[0]["value"] == 96


def test_table_card_uses_its_own_day_instead_of_whole_period():
    from scripts.garmin_differences import compare_card

    rows = [
        dict(time=None, requested_day="2026-10-29", validity="valid", value=60),
        dict(time=None, requested_day="2026-10-30", validity="valid", value=80),
    ]
    data = dict(chart=[], mcp=rows, export=rows, history=dict(columns=[]))
    card = dict(
        operation="source_daily_last",
        range_start="2026-10-30",
        range_end="2026-10-30",
        value=80,
        precision=0,
        reason="source",
    )
    assert (
        compare_card(data, card, "mcp", date(2026, 10, 25), date(2026, 10, 31))[
            "status"
        ]
        == "exact"
    )
