import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from garmin_database.adapters.outbound.filesystem.files import atomic_json
from garmin_database.application.settings import Settings as SettingsModel


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
    source_root = Path(__file__).resolve().parents[5]
    if (source_root / "pyproject.toml").is_file() and (
        source_root / "src/garmin_database"
    ).is_dir():
        return source_root
    return application_dir()


@dataclass
class Settings(SettingsModel):
    data_dir: str = field(default_factory=lambda: str(project_dir() / "data"))
    export_dir: str = field(default_factory=lambda: str(project_dir() / "exports"))

    @classmethod
    def load(cls, path=None):
        path = Path(path or application_dir() / "settings.json")
        if not path.exists():
            return cls()
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Ustawienia muszą być obiektem JSON")
        result = cls(
            **{k: v for k, v in value.items() if k in cls.__dataclass_fields__}
        )
        result.validate()
        return result

    def save(self, path=None):
        self.validate()
        atomic_json(path or application_dir() / "settings.json", asdict(self))

    def validate(self):
        from psycopg.conninfo import conninfo_to_dict

        try:
            options = conninfo_to_dict(self.database_dsn)
        except Exception:
            raise ValueError("Nieprawidłowe połączenie PostgreSQL") from None
        if "password" in options:
            raise ValueError(
                "Hasło PostgreSQL umieść w pgpass lub PGPASSWORD, poza ustawieniami"
            )
        super().validate()


class SettingsStore:
    def load(self, path=None):
        return Settings.load(path)

    def save(self, settings, path=None):
        Settings(**asdict(settings)).save(path)

    def location(self, path=None):
        return Path(path or application_dir() / "settings.json")
