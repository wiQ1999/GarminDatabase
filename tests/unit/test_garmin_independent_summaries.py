from scripts.garmin_independent_summaries import daily_audit, independent_days


def sample(time, value, validity="valid"):
    return dict(time=time, value=value, validity=validity, requested_day="2026-10-25")


def test_independent_arithmetic_quality_and_dst_boundaries():
    rows = [
        sample("2026-10-24T22:30:00+00:00", 10),
        sample("2026-10-25T01:30:00+00:00", 30),
        sample("2026-10-25T02:30:00+00:00", -1),
        sample("2026-10-25T03:30:00+00:00", 255, "invalid"),
        sample(None, 50),
        sample("2026-10-25T23:30:00+00:00", 40),
    ]
    days = independent_days(rows, "stress_level.stress_level_value")
    assert len(days) == 2
    assert days[0] == dict(
        day="2026-10-25",
        mean=20,
        minimum=10,
        maximum=30,
        valid_count=2,
        invalid_count=1,
        excluded_count=1,
        untimed_count=1,
        first_time=rows[0]["time"],
        last_time=rows[1]["time"],
    )
    assert days[1]["day"] == "2026-10-26"


def test_shared_wrong_cache_and_missing_day_do_not_pass():
    rows = [
        sample("2026-10-25T12:00:00+00:00", 10),
        sample("2026-10-26T12:00:00+00:00", 30),
    ]
    actual = independent_days(rows, "monitoring.heart_rate")
    actual[0]["mean"] = 15
    actual.pop()
    result = daily_audit(rows, "monitoring.heart_rate", actual)
    assert not result["equal"]
    assert result["missing_days"] == ["2026-10-26"]
    assert result["differences"] == [dict(day="2026-10-25", fields=["mean"])]


def test_duplicate_published_days_are_rejected():
    rows = [sample("2026-10-25T12:00:00+00:00", 10)]
    actual = independent_days(rows, "monitoring.heart_rate")
    assert not daily_audit(rows, "monitoring.heart_rate", actual * 2)["equal"]
