"""Render the authored SVG into PNG and a multi-resolution Windows ICO."""

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render_png(renderer, size):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Could not encode application icon")
    return bytes(buffer.data())


def main():
    resources = Path(__file__).resolve().parents[1] / "garmin_database/resources"
    renderer = QSvgRenderer(str(resources / "app-icon.svg"))
    if not renderer.isValid():
        raise ValueError("Invalid application icon SVG")
    (resources / "app-icon.png").write_bytes(render_png(renderer, 512))
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    entries = []
    payloads = []
    offset = 6 + 16 * len(sizes)
    for size in sizes:
        payload = render_png(renderer, size)
        entries.append(
            struct.pack(
                "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(payload), offset
            )
        )
        payloads.append(payload)
        offset += len(payload)
    (resources / "app-icon.ico").write_bytes(
        struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries + payloads)
    )
    print("Generated application PNG and nine-resolution ICO")


if __name__ == "__main__":
    main()
