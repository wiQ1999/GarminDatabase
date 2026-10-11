"""Synthetic FITs constructed with valid FIT CRC; no personal source data."""

import struct
from io import BytesIO
from zipfile import ZipFile

from fitdecode.utils import compute_crc


def fit_bytes(number=55, fields=None, values=None):
    fields = fields or [(253, 4, 134), (27, 1, 2), (26, 2, 132), (250, 4, 134)]
    values = values or [(1100000000, 62, 43776, 123), (1100000060, 64, 43836, 124)]
    formats = {134: "I", 132: "H", 2: "B", 131: "h", 142: "q", 143: "Q", 136: "f"}
    definition = (
        b"\x40\x00\x00"
        + struct.pack("<H", number)
        + bytes([len(fields)])
        + b"".join(bytes(x) for x in fields)
    )
    data = definition
    for row in values:
        data += b"\x00" + b"".join(
            struct.pack("<" + formats[f[2]], v) for f, v in zip(fields, row)
        )
    header = struct.pack("<BBHI4s", 14, 0x20, 21800, len(data), b".FIT")
    header += struct.pack("<H", compute_crc(header))
    payload = header + data
    return payload + struct.pack("<H", compute_crc(payload))


def zip_bytes(payload=None):
    stream = BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr("synthetic_WELLNESS.fit", payload or fit_bytes())
    return stream.getvalue()


def archive(root, day="2024-06-19", payload=None):
    p = root / "raw" / f"{day}.zip"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(zip_bytes(payload))
    return p
