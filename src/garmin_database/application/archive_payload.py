"""A downloaded ZIP retained only for the duration of its import."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchivePayload:
    day: str
    content: bytes
