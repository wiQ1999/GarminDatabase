"""MCP response tables, date ranges and bounded read budget."""

from datetime import date, timedelta
from threading import Event

from garmin_database.application.errors import AccessError
from garmin_database.application.parameter_descriptions import parameter_description
from garmin_database.application.read_models import (
    PRECISION,
    aggregation,
)
from garmin_database.application.time_presentation import warsaw_iso
from garmin_database.domain.aggregation import (
    MEAN_PARAMETERS,
    numeric_sample,
)
from garmin_database.domain.cancellation import DeadlineStop
from garmin_database.domain.time import dates

MAX_BYTES = 16 * 1024
PAGE_DAYS = 92
READ_SECONDS = 60
READ_TIMEOUT_MESSAGE = "Przekroczono 60 s odczytu. Zawęź zakres lub wybór metryk."


class ReadBudget(DeadlineStop):
    def __init__(self, stop=None, seconds=READ_SECONDS):
        super().__init__(stop or Event(), seconds)

    def check(self):
        if self.stop.is_set():
            raise AccessError("Anulowano odczyt.")
        if self.is_set():
            raise AccessError(READ_TIMEOUT_MESSAGE)


def date_range(begin, finish):
    try:
        start, end = date.fromisoformat(begin), date.fromisoformat(finish)
        next(dates(start, end))
    except (ValueError, TypeError):
        raise AccessError(
            "Podaj daty YYYY-MM-DD od początku do końca, najpóźniej dzisiaj."
        ) from None
    return start, end


def date_chunks(start, end):
    while start <= end:
        finish = min(end, start + timedelta(days=PAGE_DAYS - 1))
        yield start, finish
        start = finish + timedelta(days=1)


def compress_days(values, reason, parameter=None):
    result = []
    for day in sorted(values):
        if result and date.fromisoformat(result[-1]["to"]) + timedelta(
            days=1
        ) == date.fromisoformat(day):
            result[-1]["to"] = day
        else:
            item = dict(reason=reason, **{"from": day, "to": day})
            if parameter:
                item["parameter"] = parameter
            result.append(item)
    return result


def formatted_row(row, columns, key):
    def value(column):
        item = row[column]
        if item is None:
            return None
        if column in {"first_time", "last_time"}:
            return warsaw_iso(item)
        if column in {"mean", "minimum", "maximum"}:
            return round(item, PRECISION[key])
        return item

    return [value(c) for c in columns]


def series(parameter, rows, columns, period):
    key = parameter["key"]
    return dict(
        parameter=key,
        unit=parameter["unit"],
        description=parameter_description(parameter),
        summary_origin="application",
        aggregation=aggregation(parameter, period),
        precision=PRECISION[key],
        columns=columns,
        data=[formatted_row(r, columns, key) for r in rows],
    )


def sample_row(row, parameter):
    included = None
    if parameter["key"] in MEAN_PARAMETERS:
        included = bool(
            row["time"]
            and row["validity"] == "valid"
            and numeric_sample(row["value"], parameter)
        )
    instant = warsaw_iso(row["time"])
    return [
        instant,
        row["value"],
        row["validity"],
        row["requested_day"],
        row["time_basis"],
        included,
    ]


def observation_coverage(coverage):
    return dict(
        decode_status=coverage["decode_status"],
        gaps=compress_days(coverage["missing_days"], "missing_archive")
        + compress_days(coverage["unimported_or_partial_days"], "partial_decode")
        + compress_days(coverage.get("ongoing_days", []), "current_day"),
    )
