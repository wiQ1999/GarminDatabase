import json
from contextlib import nullcontext
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .fit import FIT_EPOCH
from .summaries import Summaries, has_chart_summary, summary_method

LABELS = {
    "heart_rate": "Tętno",
    "resting_heart_rate": "Tętno spoczynkowe",
    "current_day_resting_heart_rate": "Tętno spoczynkowe bieżącego dnia",
    "stress_level_value": "Poziom stresu",
    "respiration_rate": "Częstotliwość oddechu",
    "reading_spo2": "Saturacja",
    "sleep_level": "Faza snu",
    "overall_sleep_score": "Wynik snu",
    "sleep_quality_score": "Jakość snu",
    "sleep_duration_score": "Wynik długości snu",
    "weekly_average": "HRV — średnia tygodniowa Garmin",
    "last_night_average": "HRV — ostatnia noc",
    "value": "Wartość HRV",
    "steps": "Kroki",
    "calories": "Kalorie",
    "active_calories": "Kalorie aktywne",
    "distance": "Dystans",
    "ascent": "Wznoszenie",
    "descent": "Opadanie",
    "average_deviation": "Temperatura skóry — odchylenie",
    "average_7_day_deviation": "Temperatura skóry — odchylenie z 7 dni",
    "nightly_value": "Temperatura skóry — wartość nocna",
    "moderate_activity_minutes": "Minuty umiarkowanej aktywności",
    "vigorous_activity_minutes": "Minuty intensywnej aktywności",
    "duration": "Czas trwania",
    "duration_min": "Czas trwania",
    "deep_sleep_score": "Wynik snu głębokiego",
    "light_sleep_score": "Wynik snu płytkiego",
    "rem_sleep_score": "Wynik snu REM",
    "awakenings_count": "Liczba przebudzeń",
    "average_stress_during_sleep": "Średni stres podczas snu Garmin",
    "status": "Status HRV",
    "mode": "Tryb pomiaru saturacji",
    "reading_confidence": "Pewność odczytu saturacji",
    "active_time": "Czas aktywności",
    "activity_type": "Rodzaj aktywności",
    "current_activity_type_intensity": "Rodzaj i intensywność aktywności",
    "cycles": "Cykle ruchu",
    "intensity": "Intensywność",
    "awake_time_score": "Wynik czasu czuwania",
    "awakenings_count_score": "Wynik liczby przebudzeń",
    "combined_awake_score": "Łączny wynik czuwania",
    "end_timezone_offset": "Przesunięcie strefy końca drzemki",
    "start_timezone_offset": "Przesunięcie strefy początku drzemki",
    "feedback": "Ocena drzemki",
    "interruptions_score": "Wynik przerw w śnie",
    "is_deleted": "Oznaczenie usunięcia drzemki",
    "message_index": "Indeks wiadomości źródłowej",
    "severity": "Nasilenie zakłóceń snu",
    "sleep_recovery_score": "Wynik regeneracji podczas snu",
    "sleep_restlessness_score": "Wynik niespokojnego snu",
    "source": "Źródło drzemki",
    "baseline_balanced_lower": "HRV — dolna granica zrównoważonej wartości bazowej",
    "baseline_balanced_upper": "HRV — górna granica zrównoważonej wartości bazowej",
    "baseline_low_upper": "HRV — górna granica niskiej wartości bazowej",
    "last_night_5_min_high": "HRV — najwyższa wartość 5-minutowa ostatniej nocy",
}


def group(message):
    if "sleep" in message or "nap" in message:
        return "Sen"
    if "hrv" in message or "hr_data" in message:
        return "Serce i HRV"
    if "stress" in message:
        return "Stres"
    if "respiration" in message or "spo2" in message:
        return "Oddychanie i saturacja"
    if message == "monitoring":
        return "Ruch"
    return "Pozostałe"


def bounds(start, end):
    zone = ZoneInfo("Europe/Warsaw")
    return (
        int(datetime.combine(start, time.min, zone).timestamp() * 1000),
        int(
            datetime.combine(end + timedelta(days=1), time.min, zone).timestamp() * 1000
        ),
    )


def decode_value(row, metadata):
    kind = row["value_kind"]
    value = (
        row["integer_value"]
        if kind == "integer"
        else row["real_value"]
        if kind == "real"
        else row["text_value"]
        if kind in {"text", "integer_text"}
        else json.loads(row["json_value"])
        if kind == "json"
        else None
    )
    if kind == "integer_text":
        return {"integer_text": value}

    def convert(v):
        if isinstance(v, list):
            return [convert(x) for x in v]
        if isinstance(v, dict) or v is None:
            return v
        if isinstance(v, (int, float)) and metadata.get("scale"):
            return v / metadata["scale"] - (metadata.get("offset") or 0)
        return v

    if (
        metadata["time_role"] == "utc_timestamp"
        and isinstance(value, int)
        and value >= 0x10000000
    ):
        return datetime.fromtimestamp(value + FIT_EPOCH, timezone.utc).isoformat()
    return convert(value)


class Queries:
    def __init__(self, db):
        self.db = db

    def parameters(self):
        with self.db.connect(readonly=True) as c:
            rows = c.execute("""SELECT * FROM field_catalog c WHERE semantics_status<>'unknown'
                AND representation IN ('sample','source_summary','event') AND time_role IN ('none','duration')
                AND EXISTS(SELECT 1 FROM fit_fields f JOIN fit_messages m ON m.id=f.message_id
                  JOIN file_decodes d ON d.id=m.file_decode_id WHERE (f.resolved_catalog_id=c.id OR f.resolved_catalog_id IN
                    (SELECT r.source_catalog_id FROM interpretation_rules r WHERE r.target_catalog_id=c.id)) AND d.is_active=1)
                ORDER BY message_name,variant_name""").fetchall()
        result = {}
        for row in rows:
            key = f"{row['message_name']}.{row['variant_name']}"
            if key not in result:
                category = group(row["message_name"])
                if row["variant_name"] in {
                    "heart_rate",
                    "resting_heart_rate",
                    "current_day_resting_heart_rate",
                }:
                    category = "Serce i HRV"
                result[key] = dict(
                    key=key,
                    label=LABELS.get(
                        row["variant_name"], row["variant_name"].replace("_", " ")
                    ),
                    group=category,
                    unit=row["units"],
                    representation=row["representation"],
                    ids=[],
                    enum=json.loads(row["profile_metadata_json"]).get("enum", {}),
                    original=key,
                )
            result[key]["ids"].append(row["id"])
        return sorted(result.values(), key=lambda x: (x["group"], x["label"]))

    def coverage(self, start, end, conn=None):
        from .util import dates

        with (
            nullcontext(conn)
            if conn is not None
            else self.db.connect(readonly=True) as c
        ):
            days = {
                x[0]: x[1]
                for x in c.execute(
                    "SELECT day,download_status FROM import_days WHERE day BETWEEN ? AND ?",
                    (start.isoformat(), end.isoformat()),
                )
            }
            pending = [
                x[0]
                for x in c.execute(
                    """SELECT d.day FROM import_days d WHERE d.day BETWEEN ? AND ?
                AND d.download_status='downloaded' AND (NOT EXISTS(SELECT 1 FROM archives a WHERE a.day=d.day)
                OR EXISTS(SELECT 1 FROM archives a JOIN archive_entries e ON e.archive_id=a.id WHERE a.day=d.day
                   AND NOT EXISTS(SELECT 1 FROM file_decodes x WHERE x.fit_file_id=e.fit_file_id AND x.is_active=1 AND x.status='complete'))) ORDER BY d.day""",
                    (start.isoformat(), end.isoformat()),
                )
            ]
        missing = [
            d.isoformat()
            for d in dates(start, end)
            if days.get(d.isoformat()) not in {"downloaded", "empty_zip"}
        ]
        return {
            "missing_days": missing,
            "unimported_or_partial_days": pending,
            "decode_status": "partial" if pending else "complete",
        }

    def rows(self, parameter, start, end, conn=None):
        """Stream one series. Archive selection never multiplies FIT measurements."""
        own = conn is None
        c = conn or self.db.connect(readonly=True)
        try:
            begin, finish = bounds(start, end)
            ids = list(parameter["ids"])
            if not ids:
                return
            rules = {
                r[0]: json.loads(r[1])
                for r in c.execute(
                    "SELECT source_catalog_id,rule_json FROM interpretation_rules WHERE kind='component' AND target_catalog_id IN ("
                    + ",".join("?" for _ in ids)
                    + ")",
                    ids,
                )
            }
            requested = set(ids)
            ids = list(set(ids) | set(rules))
            placeholders = ",".join("?" for _ in ids)
            # Untimed summaries are preserved with a separately labelled requested
            # day; it is never emitted as a fabricated measurement timestamp.
            sql = f"""SELECT f.*,m.time_unix_ms,m.time_basis,m.message_index,x.fit_file_id,c.scale,c.offset,c.time_role
                FROM fit_fields f JOIN fit_messages m ON m.id=f.message_id
                JOIN file_decodes x ON x.id=m.file_decode_id AND x.is_active=1
                JOIN field_catalog c ON c.id=f.resolved_catalog_id
                WHERE f.resolved_catalog_id IN ({placeholders})
                AND ((m.time_unix_ms>=? AND m.time_unix_ms<?) OR (m.time_unix_ms IS NULL AND EXISTS(
                    SELECT 1 FROM archive_entries e JOIN archives a ON a.id=e.archive_id
                    WHERE e.fit_file_id=x.fit_file_id AND a.day BETWEEN ? AND ?)))
                ORDER BY m.time_unix_ms,x.fit_file_id,m.message_index,f.field_definition_id"""
            origins = {}
            for row in c.execute(
                sql, (*ids, begin, finish, start.isoformat(), end.isoformat())
            ):
                fid = row["fit_file_id"]
                if fid not in origins:
                    origin = c.execute(
                        "SELECT a.day,a.relative_path,e.entry_name FROM archive_entries e JOIN archives a ON a.id=e.archive_id WHERE e.fit_file_id=? ORDER BY (a.day BETWEEN ? AND ?) DESC,a.day,e.entry_index LIMIT 1",
                        (fid, start.isoformat(), end.isoformat()),
                    ).fetchone()
                    origins[fid] = (origin[0], origin[1] + "/" + origin[2])
                day, source = origins[fid]
                instant = (
                    datetime.fromtimestamp(
                        row["time_unix_ms"] / 1000, timezone.utc
                    ).isoformat()
                    if row["time_unix_ms"] is not None
                    else None
                )
                value = decode_value(row, dict(row))
                if (
                    row["resolved_catalog_id"] in rules
                    and row["resolved_catalog_id"] not in requested
                ):
                    rule = rules[row["resolved_catalog_id"]]
                    # Components are decoded from preserved packed bits. A physical
                    # destination field takes precedence when present in this message.
                    if c.execute(
                        "SELECT 1 FROM fit_fields WHERE message_id=? AND resolved_catalog_id IN ("
                        + ",".join("?" for _ in requested)
                        + ")",
                        (row["message_id"], *requested),
                    ).fetchone():
                        continue
                    if isinstance(value, list):
                        value = (
                            sum(
                                v << (8 * i)
                                for i, v in enumerate(value)
                                if isinstance(v, int)
                            )
                            if all(isinstance(v, int) for v in value)
                            else None
                        )
                    if isinstance(value, (int, float)):
                        packed = (int(value) >> rule["shift"]) & (
                            (1 << rule["bits"]) - 1
                        )
                        value = packed / rule["scale"] - rule["offset"]
                yield dict(
                    time=instant,
                    value=value,
                    source=source,
                    validity=row["validity"],
                    requested_day=day,
                    time_basis=row["time_basis"],
                )
        finally:
            if own:
                c.close()

    def chart(self, parameter, start, end):
        if start != end and not has_chart_summary(parameter):
            return [], "Brak podsumowań źródłowych Garmin. Wybierz pojedynczy dzień."
        if start != end and summary_method(parameter) == "sample_mean":
            with self.db.connect(readonly=True) as conn:
                conn.execute("BEGIN")
                rows = Summaries(self.db).daily(parameter, start, end, conn)
            points = [
                (
                    bounds(
                        date.fromisoformat(row["day"]), date.fromisoformat(row["day"])
                    )[0],
                    row["mean"],
                    row["day"] + f" • średnia obliczona z {row['valid_count']} próbek",
                )
                for row in rows
            ]
            return (
                points,
                "Czas: Europe/Warsaw; średnie dzienne obliczone przez aplikację"
                if points
                else "Brak danych dla wybranego okresu",
            )
        result = []
        for row in self.rows(parameter, start, end):
            if row["time"]:
                stamp = int(datetime.fromisoformat(row["time"]).timestamp() * 1000)
                label = (
                    datetime.fromisoformat(row["time"])
                    .astimezone(ZoneInfo("Europe/Warsaw"))
                    .strftime("%Y-%m-%d %H:%M:%S")
                )
            elif parameter["representation"] == "source_summary":
                stamp = bounds(
                    date.fromisoformat(row["requested_day"]),
                    date.fromisoformat(row["requested_day"]),
                )[0]
                label = row["requested_day"] + " (dzień archiwum; brak czasu pomiaru)"
            else:
                continue
            value = row["value"]
            if not isinstance(value, (int, float)) or row["validity"] != "valid":
                value = None
            result.append((stamp, value, label))
        return (
            result,
            "Czas: Europe/Warsaw; wartości źródłowe Garmin"
            if result
            else "Brak danych dla wybranego okresu",
        )
