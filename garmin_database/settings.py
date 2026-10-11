import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .util import atomic_json


def application_dir():
    return (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
        / "GarminDatabase"
    )


def project_dir():
    if getattr(sys, "frozen", False):
        directory = Path(sys.executable).parent
        # The local onedir build lives under project/dist/GarminDatabase. Reuse
        # the existing archive directory when launched from that checkout.
        for parent in directory.parents:
            if (parent / "schema/001_initial.sql").exists() and (
                parent / "data/raw"
            ).is_dir():
                return parent
        return directory
    return Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    data_dir: str = field(default_factory=lambda: str(project_dir() / "data"))
    export_dir: str = field(default_factory=lambda: str(project_dir() / "exports"))
    recent_days: int = 90
    parameters: list[str] = field(default_factory=list)
    summary_period: str = "day"
    history_from: str = "2024-01-01"
    history_to: str = ""  # empty means yesterday, not a frozen relative date
    delay: float = 3.0

    @classmethod
    def load(cls, path=None):
        path = Path(path or application_dir() / "settings.json")
        if not path.exists():
            return cls()
        value = json.loads(path.read_text(encoding="utf-8"))
        result = cls(
            **{k: v for k, v in value.items() if k in cls.__dataclass_fields__}
        )
        result.validate()
        return result

    def validate(self):
        import math
        from datetime import date

        if not isinstance(self.recent_days, int) or self.recent_days < 1:
            raise ValueError("Okres szczegółowy musi być dodatnią liczbą dni")
        if not isinstance(self.parameters, list) or not all(
            isinstance(v, str) for v in self.parameters
        ):
            raise ValueError("Nieprawidłowa lista parametrów")
        if self.summary_period not in {"day", "month"}:
            raise ValueError("Nieprawidłowy okres podsumowań")
        if not math.isfinite(self.delay) or self.delay < 0:
            raise ValueError("Nieprawidłowe opóźnienie")
        date.fromisoformat(self.history_from)
        if self.history_to:
            date.fromisoformat(self.history_to)
        if not self.data_dir or not self.export_dir:
            raise ValueError("Wybierz katalogi danych i eksportu")

    def save(self, path=None):
        self.validate()
        atomic_json(path or application_dir() / "settings.json", asdict(self))
