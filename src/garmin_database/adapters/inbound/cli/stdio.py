"""UTF-8 for console and redirected Windows CLI streams, without rewrapping."""

import sys


def configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
