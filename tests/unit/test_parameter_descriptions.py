from urllib.parse import urlsplit

import pytest
from garmin_fit_sdk import Profile

from garmin_database.adapters.inbound.desktop.parameter_help import parameter_help
from garmin_database.adapters.outbound.fit.profile import (
    SAMPLE_MESSAGES,
    SUMMARY_MESSAGES,
)
from garmin_database.adapters.outbound.postgres.queries import LABELS
from garmin_database.application.parameter_descriptions import (
    DESCRIPTIONS,
    parameter_description,
)

pytestmark = pytest.mark.unit


def test_every_named_supported_profile_parameter_has_official_explanation():
    keys = set()
    for number in SAMPLE_MESSAGES | SUMMARY_MESSAGES | {412}:
        message = Profile["messages"][number]
        for field in message["fields"].values():
            for variant in [field, *field.get("sub_fields", [])]:
                if variant["name"] in LABELS:
                    keys.add(message["name"] + "." + variant["name"])
    assert keys and keys <= DESCRIPTIONS.keys()
    for key in keys:
        description = parameter_description(dict(key=key))
        assert description["evidence"] != "not_documented"
        assert description["meaning"] and description["measurement"]
        for source in description["sources"]:
            url = urlsplit(source["url"])
            assert url.scheme == "https"
            assert url.hostname.endswith(".garmin.com") or (
                url.hostname == "github.com" and url.path.startswith("/garmin/")
            )


def test_distinct_heart_metrics_and_unknown_algorithms_are_not_conflated():
    def describe(key):
        return parameter_description(dict(key=key))

    assert "Pięciominutowa" in describe("hrv_value.value")["meaning"]
    assert "7-dniową" in describe("monitoring_hr_data.resting_heart_rate")["meaning"]
    assert (
        "bieżącego dnia"
        in describe("monitoring_hr_data.current_day_resting_heart_rate")["meaning"]
    )
    assert (
        "czuwania"
        in describe("sleep_assessment.average_stress_during_sleep")["measurement"]
    )
    for key in (
        "spo2_data.reading_confidence",
        "sleep_disruption_overnight_severity.severity",
        "nap_event.message_index",
    ):
        assert describe(key)["evidence"] == "fit_profile_only"
    unknown = describe("unknown_123.private_value")
    assert unknown["evidence"] == "not_documented"
    assert "nie zgaduje" in unknown["limitations"]
    assert "wypełniania luk" in describe("monitoring.heart_rate")["presentation"]
    assert (
        "Gotowe podsumowanie"
        in parameter_description(
            dict(
                key="hrv_status_summary.last_night_average",
                representation="source_summary",
            )
        )["presentation"]
    )


def test_descriptions_are_isolated_from_caller_mutation():
    first = parameter_description(dict(key="monitoring.heart_rate"))
    first["sources"][0]["url"] = "https://example.invalid"
    first["meaning"] = "changed"
    second = parameter_description(dict(key="monitoring.heart_rate"))
    assert first != second
    assert "example.invalid" not in str(second)
    assert "Wybierz parametr" in parameter_help(None)
    html = parameter_help(dict(key="monitoring.heart_rate"))
    assert '<a href="https://www.garmin.com/' in html
    assert "PPG" in html and "W aplikacji" in html


def test_help_escapes_text_and_link_attributes(monkeypatch):
    description = parameter_description(dict(key="monitoring.heart_rate"))
    description["meaning"] = "<script>bad</script>"
    description["sources"] = [
        dict(title="<b>source</b>", url='https://example.invalid/?q=" onmouseover="bad')
    ]
    monkeypatch.setattr(
        "garmin_database.adapters.inbound.desktop.parameter_help.parameter_description",
        lambda _: description,
    )
    html = parameter_help(dict(key="test"))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "q=&quot; onmouseover=&quot;bad" in html
    assert "&lt;b&gt;source&lt;/b&gt;" in html
