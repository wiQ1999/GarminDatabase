"""Shared selection and aggregation descriptions; no database access."""

from garmin_database.domain.aggregation import ALGORITHM_VERSION, summary_method

QUALITY_COLUMNS = [
    "valid_count",
    "invalid_count",
    "excluded_count",
    "untimed_count",
    "first_time",
    "last_time",
    "day_basis",
]
DAILY_COLUMNS = ["day", "mean", "minimum", "maximum", *QUALITY_COLUMNS]
PERIOD_COLUMNS = [
    "period_from",
    "period_to",
    "mean",
    "minimum",
    "maximum",
    *QUALITY_COLUMNS[:4],
    "valid_days",
    "requested_days",
    *QUALITY_COLUMNS[4:],
]
PRECISION = {
    "monitoring.heart_rate": 0,
    "hrv_value.value": 0,
    "respiration_rate.respiration_rate": 1,
    "spo2_data.reading_spo2": 1,
    "stress_level.stress_level_value": 1,
}


def aggregation(parameter, period):
    method = summary_method(parameter)
    return dict(
        method=method,
        period=period,
        algorithm_version=ALGORITHM_VERSION,
        weighting="valid_sample_count" if method == "sample_mean" else None,
        negative_stress_values_excluded=parameter["key"]
        == "stress_level.stress_level_value",
    )


def summary_columns(parameter, period):
    values = {
        "sample_mean": ["mean", "minimum", "maximum"],
        "value_counts": ["value_counts"],
        "last_observed": ["last_value"],
    }
    columns = ["day", *values[summary_method(parameter)], *QUALITY_COLUMNS]
    if period == "month":
        columns[0] = "month"
        columns += ["valid_days", "period_from", "period_to"]
    return columns


def select_parameters(catalog, allowed, requested):
    """Resolve canonical metadata; callers cannot inject catalog ids or scaling."""
    keys = list(requested)
    if not keys or len(set(keys)) != len(keys):
        raise ValueError("Wybierz co najmniej jeden niepowtarzający się parametr")
    available = {p["key"]: p for p in catalog if p["key"] in allowed}
    if any(key not in available for key in keys):
        raise ValueError(
            "Parametr nieznany lub wyłączony. Sprawdź katalog i Ustawienia."
        )
    return [available[key] for key in keys]
