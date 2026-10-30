"""Application configuration and sharing policy, without persistence."""

from dataclasses import dataclass, field


@dataclass
class Settings:
    data_dir: str = "data"
    export_dir: str = "exports"
    database_dsn: str = ""  # Non-secret libpq connection options; password via pgpass.
    recent_days: int = 90
    parameters: list[str] = field(default_factory=list)
    summary_period: str = "day"
    history_from: str = "2024-01-01"
    history_to: str = ""  # empty means today, not a frozen relative date
    delay: float = 3.0
    settings_version: int = 1
    export_parameters: list[str] | None = None
    mcp_parameters: list[str] = field(default_factory=list)
    mcp_enabled: bool = False
    collector_config_path: str = ""

    def migrate(self, catalog):
        """Freeze the legacy 'all' selection once; docs/11-desktop-ui.md."""
        if self.settings_version == 2:
            return False
        self.export_parameters = list(self.parameters or [p["key"] for p in catalog])
        self.parameters = list(self.export_parameters)
        self.settings_version = 2
        return True

    def validate(self):
        import math
        from datetime import date

        if not isinstance(self.recent_days, int) or self.recent_days < 1:
            raise ValueError("Okres szczegółowy musi być dodatnią liczbą dni")
        self.validate_sharing()
        if self.summary_period not in {"day", "month"}:
            raise ValueError("Nieprawidłowy okres podsumowań")
        if not math.isfinite(self.delay) or self.delay < 0:
            raise ValueError("Nieprawidłowe opóźnienie")
        date.fromisoformat(self.history_from)
        if self.history_to:
            date.fromisoformat(self.history_to)
        if not self.data_dir or not self.export_dir:
            raise ValueError("Wybierz katalogi danych i eksportu")

    def validate_sharing(self):
        if type(self.settings_version) is not int or self.settings_version not in {
            1,
            2,
        }:
            raise ValueError("Nieobsługiwana wersja ustawień")
        if type(self.mcp_enabled) is not bool:
            raise ValueError("Nieprawidłowy przełącznik MCP")
        lists = [self.parameters, self.mcp_parameters]
        if self.export_parameters is not None:
            lists.append(self.export_parameters)
        if self.settings_version == 2 and self.export_parameters is None:
            raise ValueError("Brak jawnej listy eksportu")
        for values in lists:
            if not valid_parameter_list(values):
                raise ValueError("Nieprawidłowa lista parametrów")


def valid_parameter_list(values):
    return (
        isinstance(values, list)
        and all(isinstance(v, str) and 0 < len(v) <= 200 for v in values)
        and len(set(values)) == len(values)
    )
