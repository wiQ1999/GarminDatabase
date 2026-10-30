"""Ograniczony odczyt MCP bez Qt i zapisów: docs/03-architecture.md."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Event
from zoneinfo import ZoneInfo

from garmin_database.application.parameter_descriptions import parameter_description
from garmin_database.application.ports import ReadFailure
from garmin_database.application.read_models import (
    DAILY_COLUMNS,
    PERIOD_COLUMNS,
    PRECISION,
    aggregation,
)
from garmin_database.application.settings import valid_parameter_list
from garmin_database.domain.aggregation import MEAN_PARAMETERS, period_summary
from garmin_database.domain.cancellation import Cancelled
from garmin_database.domain.time import dates
from garmin_database.domain.values import dumps

MAX_BYTES = 16 * 1024
PAGE_DAYS = 92
READ_SECONDS = 60
READ_TIMEOUT_MESSAGE = "Przekroczono 60 s odczytu. Zawęź zakres lub wybór metryk."
ZONE = ZoneInfo("Europe/Warsaw")


class AccessError(ValueError):
    """Safe, actionable message suitable for a client; never a raw SQL exception."""


class ReadBudget:
    def __init__(self, stop=None, seconds=READ_SECONDS):
        self.stop = stop or Event()
        self.deadline = time.monotonic() + seconds

    def is_set(self):
        return self.stop.is_set() or time.monotonic() >= self.deadline

    def check(self):
        if self.stop.is_set():
            raise AccessError("Anulowano odczyt.")
        if self.is_set():
            raise AccessError(READ_TIMEOUT_MESSAGE)


def policy_key(settings):
    policy = [
        str(Path(settings.data_dir).resolve()),
        settings.database_dsn,
        os.environ.get("GARMIN_DATABASE_DSN"),
        settings.settings_version,
        settings.mcp_enabled,
        sorted(settings.mcp_parameters),
    ]
    return hashlib.sha256(dumps(policy).encode()).hexdigest()


def load_policy(path, settings_store):
    try:
        settings = settings_store.load(path)
    except (ValueError, TypeError, OSError):
        raise AccessError(
            "Nieprawidłowe ustawienia. Zapisz je ponownie w aplikacji."
        ) from None
    if settings.settings_version != 2 or not settings.mcp_enabled:
        raise AccessError(
            "MCP jest wyłączony. Włącz go i wybierz parametry w Ustawieniach."
        )
    return settings


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
            return datetime.fromisoformat(item).astimezone(ZONE).isoformat()
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


class MCPData:
    def __init__(
        self,
        settings_path=None,
        *,
        settings_store,
        readings_factory,
        max_bytes=MAX_BYTES,
        seconds=READ_SECONDS,
    ):
        self.settings_store = settings_store
        self.readings_factory = readings_factory
        self.settings_path = settings_path
        self.max_bytes = max_bytes
        self.seconds = seconds
        self.secret = secrets.token_bytes(32)
        self.catalog_cache = None

    def check_policy(self, key):
        if policy_key(load_policy(self.settings_path, self.settings_store)) != key:
            raise AccessError(
                "Zmieniono ustawienia udostępniania. Rozpocznij zapytanie ponownie."
            )

    @contextmanager
    def snapshot(self, stop=None):
        settings = load_policy(self.settings_path, self.settings_store)
        key = policy_key(settings)
        budget = ReadBudget(stop, self.seconds)
        budget.check()
        readings = self.readings_factory(settings)
        try:
            with readings.snapshot(budget) as snapshot:
                identity = [*snapshot.identity, key]
                snapshot.policy_revision = key
                yield settings, snapshot, budget, identity
                budget.check()
                self.check_policy(key)
        except (Cancelled, ReadFailure) as error:
            budget.check()
            if isinstance(error, ReadFailure) and error.reason == "timeout":
                # PostgreSQL rounds statement_timeout to milliseconds. It can
                # expire just before the client monotonic deadline on Windows.
                raise AccessError(READ_TIMEOUT_MESSAGE) from None
            raise AccessError(
                "Nie można odczytać bazy. Przygotuj ją w aplikacji i ponów odczyt."
            ) from None
        except OSError:
            raise AccessError(
                "Brak dostępnej bazy. Wskaż folder danych w aplikacji."
            ) from None

    def encode_cursor(self, value):
        raw = dumps(value).encode()
        digest = hmac.digest(self.secret, raw, "sha256")
        return base64.urlsafe_b64encode(digest + raw).decode()

    def decode_cursor(self, cursor, expected):
        try:
            if not isinstance(cursor, str) or len(cursor) > 4096:
                raise ValueError()
            raw = base64.b64decode(cursor, altchars=b"-_", validate=True)
            if not hmac.compare_digest(
                raw[:32], hmac.digest(self.secret, raw[32:], "sha256")
            ):
                raise ValueError()
            value = json.loads(raw[32:])
            if value["query"] != expected:
                raise ValueError()
            return value["next"]
        except (ValueError, TypeError, KeyError):
            raise AccessError(
                "Kursor nieprawidłowy lub nieaktualny. Rozpocznij zapytanie ponownie."
            ) from None

    def fits(self, payload):
        # Reserve the complete MCP content/structuredContent envelope, without duplication.
        return len(dumps(payload).encode("utf-8")) <= self.max_bytes - 512

    def envelope(self, snapshot, start=None, end=None):
        result = dict(
            schema_version=1,
            calendar_timezone="Europe/Warsaw",
            timestamp_timezone="Europe/Warsaw",
            data_revision=snapshot.revision,
            policy_revision=snapshot.policy_revision,
            truncated=False,
            next_cursor=None,
        )
        if start is not None:
            result["requested_from"], result["requested_to"] = (
                start.isoformat(),
                end.isoformat(),
            )
        return result

    def select(self, snapshot, settings, metrics):
        if not valid_parameter_list(metrics) or not 1 <= len(metrics) <= 5:
            raise AccessError("Wybierz od 1 do 5 różnych metryk z garmin_catalog.")
        return snapshot.select(settings, "mcp", metrics)

    def catalog(self, cursor=None, stop=None):
        with self.snapshot(stop) as (settings, snap, budget, identity):
            if cursor is not None:
                self.decode_cursor(cursor, ["catalog", identity])
            cache_key = dumps(identity)
            if self.catalog_cache is None or self.catalog_cache[0] != cache_key:
                items = [
                    self.catalog_item(p, snap, budget)
                    for p in snap.catalog
                    if p["key"] in set(settings.mcp_parameters) & MEAN_PARAMETERS
                ]
                self.catalog_cache = cache_key, items
            result = self.envelope(snap)
            result.update(
                metrics=self.catalog_cache[1],
                limits=dict(
                    daily_page_days=PAGE_DAYS,
                    metrics=5,
                    response_bytes=MAX_BYTES,
                    read_seconds=READ_SECONDS,
                ),
                gaps_detail="get_daily",
            )
            if not self.fits(result):
                raise AccessError(
                    "Katalog przekracza limit odpowiedzi. Zmniejsz wybór w Ustawieniach."
                )
            return result

    def catalog_item(self, parameter, snapshot, budget):
        row = snapshot.availability(parameter)
        budget.check()
        limits = [
            datetime.fromtimestamp(t / 1000, ZONE).date().isoformat()
            if t is not None
            else None
            for t in row
        ]
        return dict(
            parameter=parameter["key"],
            label=parameter["label"],
            unit=parameter["unit"],
            description=parameter_description(parameter),
            method="sample_mean",
            precision=PRECISION[parameter["key"]],
            **{"from": limits[0], "to": limits[1]},
            operations=["get_daily", "get_period_stats"],
        )

    def daily(self, date_from, date_to, metrics, cursor=None, stop=None):
        start, end = date_range(date_from, date_to)
        with self.snapshot(stop) as (settings, snap, budget, identity):
            parameters = self.select(snap, settings, metrics)
            query = ["daily", identity, date_from, date_to, metrics]
            begin = (
                date.fromisoformat(self.decode_cursor(cursor, query))
                if cursor
                else start
            )
            finish = min(end, begin + timedelta(days=PAGE_DAYS - 1))
            if not start <= begin <= end:
                raise AccessError(
                    "Nieprawidłowy zakres kursora. Rozpocznij zapytanie ponownie."
                )
            rows = [snap.daily(p, begin, finish, budget) for p in parameters]
            while True:
                budget.check()
                result = self.daily_page(
                    snap, parameters, rows, start, end, begin, finish
                )
                if finish < end:
                    result.update(
                        truncated=True,
                        next_cursor=self.encode_cursor(
                            dict(
                                query=query,
                                next=(finish + timedelta(days=1)).isoformat(),
                            )
                        ),
                    )
                if self.fits(result):
                    return result
                if finish == begin:
                    raise AccessError(
                        "Jeden dzień przekracza limit odpowiedzi. Wybierz mniej metryk."
                    )
                finish = begin + timedelta(days=(finish - begin).days // 2)

    def daily_page(self, snap, parameters, rows, start, end, begin, finish):
        coverage = snap.coverage(begin, finish)
        gaps = compress_days(coverage["missing_days"], "missing_archive")
        gaps += compress_days(coverage["unimported_or_partial_days"], "partial_decode")
        gaps += compress_days(coverage.get("ongoing_days", []), "current_day")
        tables = []
        days = {d.isoformat() for d in dates(begin, finish)}
        for parameter, observations in zip(parameters, rows):
            page = [
                r
                for r in observations
                if begin.isoformat() <= r["day"] <= finish.isoformat()
            ]
            valid_days = {r["day"] for r in page if r["valid_count"]}
            gaps += compress_days(
                days - valid_days, "no_valid_samples", parameter["key"]
            )
            tables.append(series(parameter, page, DAILY_COLUMNS, "day"))
        result = self.envelope(snap, start, end)
        result.update(
            series=tables,
            gaps=gaps,
            gaps_format="date_ranges",
            **{"from": begin.isoformat(), "to": finish.isoformat()},
            decode_status=coverage["decode_status"],
        )
        return result

    def period(self, date_from, date_to, metrics, stop=None):
        start, end = date_range(date_from, date_to)
        with self.snapshot(stop) as (settings, snap, budget, identity):
            parameters = self.select(snap, settings, metrics)
            tables, gaps = [], []
            # Each reducer consumes one 92-day chunk at a time, on the same snapshot.
            for parameter in parameters:
                rows = (
                    row
                    for a, b in date_chunks(start, end)
                    for row in snap.daily(parameter, a, b, budget)
                )
                summary = period_summary(rows, start, end, budget)
                tables.append(series(parameter, [summary], PERIOD_COLUMNS, "range"))
                gaps.append(
                    dict(
                        reason="no_valid_samples",
                        parameter=parameter["key"],
                        days=summary["requested_days"] - summary["valid_days"],
                    )
                )
            coverage = snap.coverage(start, end)
            gaps += [
                dict(reason="missing_archive", days=len(coverage["missing_days"])),
                dict(
                    reason="partial_decode",
                    days=len(coverage["unimported_or_partial_days"]),
                ),
            ]
            if coverage.get("ongoing_days"):
                gaps.append(
                    dict(reason="current_day", days=len(coverage["ongoing_days"]))
                )
            result = self.envelope(snap, start, end)
            result.update(
                series=tables,
                gaps=gaps,
                gaps_format="day_counts",
                **{"from": date_from, "to": date_to},
                decode_status=coverage["decode_status"],
            )
            budget.check()
            if not self.fits(result):
                raise AccessError(
                    "Podsumowanie przekracza limit. Wybierz mniej metryk."
                )
            return result
