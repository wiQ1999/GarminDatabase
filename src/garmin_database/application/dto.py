from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExportResult:
    directory: Path
    files: dict[str, int]
