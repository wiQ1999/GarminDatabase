"""Fixed UTC slots; missed slots are never replayed."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def instant(value):
    if not isinstance(value, str):
        raise ValueError("Nieprawidłowy termin harmonogramu")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Termin musi zawierać strefę czasową")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Schedule:
    interval_minutes: int = 120
    anchor_at: str = "2024-01-01T00:00:00Z"

    def __post_init__(self):
        if type(self.interval_minutes) is not int or self.interval_minutes < 15:
            raise ValueError("Cykl musi wynosić co najmniej 15 pełnych minut")
        anchor = instant(self.anchor_at)
        if anchor.second or anchor.microsecond:
            raise ValueError("Początek harmonogramu musi przypadać na pełną minutę")

    def slot(self, now):
        anchor = instant(self.anchor_at)
        if now < anchor:
            return None
        period = timedelta(minutes=self.interval_minutes)
        return anchor + ((now - anchor) // period) * period

    def next_after(self, now):
        slot = self.slot(now)
        return (
            instant(self.anchor_at)
            if slot is None
            else slot + timedelta(minutes=self.interval_minutes)
        )

    def due(self, now, boot_at, tolerance_seconds=60):
        slot = self.slot(now)
        if slot is None or slot <= boot_at:
            return None
        return slot if 0 <= (now - slot).total_seconds() < tolerance_seconds else None
