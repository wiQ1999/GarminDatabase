"""Explicit reviewed MCP surface; descriptions alone never grant access."""

from garmin_database.domain.aggregation import MEAN_PARAMETERS

SOURCE_PARAMETERS = frozenset(
    {
        "monitoring_hr_data.resting_heart_rate",
        "monitoring_hr_data.current_day_resting_heart_rate",
        "hrv_status_summary.weekly_average",
        "hrv_status_summary.last_night_average",
        "hrv_status_summary.last_night_5_min_high",
        "hrv_status_summary.baseline_balanced_lower",
        "hrv_status_summary.baseline_balanced_upper",
        "hrv_status_summary.baseline_low_upper",
        "hrv_status_summary.status",
        "sleep_level.sleep_level",
        "sleep_assessment.average_stress_during_sleep",
        "sleep_assessment.overall_sleep_score",
        "sleep_assessment.sleep_quality_score",
        "sleep_assessment.sleep_duration_score",
        "sleep_assessment.deep_sleep_score",
        "sleep_assessment.light_sleep_score",
        "sleep_assessment.rem_sleep_score",
        "sleep_assessment.awake_time_score",
        "sleep_assessment.awakenings_count_score",
        "sleep_assessment.combined_awake_score",
        "sleep_assessment.sleep_recovery_score",
        "sleep_assessment.sleep_restlessness_score",
        "sleep_assessment.interruptions_score",
        "sleep_assessment.awakenings_count",
        "skin_temp_overnight.average_deviation",
        "skin_temp_overnight.average_7_day_deviation",
        "spo2_data.mode",
        "spo2_data.reading_confidence",
        "monitoring.steps",
        "monitoring.distance",
        "monitoring.active_calories",
        "monitoring.calories",
        "monitoring.moderate_activity_minutes",
        "monitoring.vigorous_activity_minutes",
        "monitoring.ascent",
        "monitoring.descent",
        "monitoring.active_time",
        "monitoring.activity_type",
    }
)
MCP_PARAMETERS = MEAN_PARAMETERS | SOURCE_PARAMETERS
