"""Punkt wejścia paczki Windows. Uruchamianie: docs/12-running-and-testing.md."""

import json
import sys
from pathlib import Path

try:
    from garmin_database.ui import main
except Exception as error:
    if "--smoke-screenshot" in sys.argv:
        target = Path(sys.argv[sys.argv.index("--smoke-screenshot") + 1]).with_suffix(
            ".error.json"
        )
        target.write_text(
            json.dumps(
                {"type": type(error).__name__, "module": getattr(error, "name", None)}
            ),
            encoding="utf-8",
        )
        raise SystemExit(1)
    raise
if __name__ == "__main__":
    raise SystemExit(main())
