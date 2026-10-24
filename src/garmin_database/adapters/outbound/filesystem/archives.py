"""Original ZIPs remain immutable, independent of the SQL implementation."""

import json
from pathlib import Path

from .files import atomic_write


class Archives:
    def __init__(self, root):
        self.root = Path(root)

    def restore_manifest(self):
        path = self.root / "collection.json"
        return (
            json.loads(path.read_text(encoding="utf-8")).get("days", {})
            if path.exists()
            else {}
        )

    def path(self, day):
        return self.root / "raw" / f"{day}.zip"

    def exists(self, day):
        return self.path(day).exists()

    def save(self, day, payload):
        path = self.path(day)
        if path.exists():
            raise FileExistsError("Archiwum już istnieje")
        atomic_write(path, payload)
