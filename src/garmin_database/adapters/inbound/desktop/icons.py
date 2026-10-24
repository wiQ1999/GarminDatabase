"""Small authored SVG symbols following the supplied Garmin visual references."""

from pathlib import Path

from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def application_icon():
    return QIcon(str(Path(__file__).parents[3] / "resources/app-icon.png"))


SYMBOLS = {
    "heart": ("#ff626d", '<path d="M12 21 3 12C-3 4 7-1 12 6 17-1 27 4 21 12Z"/>'),
    "hrv": (
        "#ff626d",
        '<path d="M12 17 3 10C-1 4 7 0 12 5 17 0 25 4 21 10Z"/><path d="m4 9 4 0 2-4 3 8 2-4h5" fill="none" stroke="#20252e"/><text x="13" y="23" font-size="9" font-family="sans-serif">Zz</text>',
    ),
    "steps": (
        "#5ba9ef",
        '<ellipse cx="7" cy="7" rx="3" ry="6" transform="rotate(-18 7 7)"/><ellipse cx="7" cy="17" rx="3" ry="3"/><ellipse cx="17" cy="10" rx="3" ry="6" transform="rotate(18 17 10)"/><ellipse cx="17" cy="20" rx="3" ry="3"/>',
    ),
    "stress": (
        "#f58b29",
        '<circle cx="12" cy="6" r="5"/><path d="m12 2-3 5h3l-1 4 5-6h-3l1-3" fill="#20252e"/><path d="M3 23q0-10 9-10t9 10Z"/>',
    ),
    "breath": (
        "#37b8c6",
        '<path d="M2 7h12c8 0 8-8 2-6M2 12h17c7 0 7 9 1 9M2 17h8c5 0 5 6 1 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',
    ),
    "floors": (
        "#55d0df",
        '<path d="M3 22v-5h5v-5h5V7h5M3 8l8-6m-5 0h5v5" fill="none" stroke="currentColor" stroke-width="2.5"/>',
    ),
    "calories": (
        "#63cd77",
        '<path d="M13 0c3 7-3 8 3 12 2-3 2-5 2-7 10 11 3 18-6 19-9-2-12-11-6-17 1 5 1 6 3 7-2-7 5-9 4-14Z"/>',
    ),
    "sleep": ("#aa8bea", '<path d="M18 1A11 11 0 1 0 23 18 10 10 0 0 1 18 1Z"/>'),
    "clock": (
        "#f49a36",
        '<path d="M9 1h6M12 1v3M2 7H0M2 12H0M2 17H0" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="13" cy="14" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M13 7v7l4 3" fill="none" stroke="currentColor" stroke-width="2"/>',
    ),
    "temperature": (
        "#e591b4",
        '<path d="M9 4a3 3 0 0 1 6 0v11a5 5 0 1 1-6 0Z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 8v10" stroke="currentColor" stroke-width="3"/><circle cx="12" cy="19" r="2"/>',
    ),
    "oxygen": (
        "#e87b8c",
        '<circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><path d="m4 14 4-8 4 13 5-13 3 7" fill="none" stroke="currentColor" stroke-width="2"/>',
    ),
    "other": (
        "#64aef1",
        '<circle cx="4" cy="12" r="3"/><circle cx="12" cy="12" r="3"/><circle cx="20" cy="12" r="3"/>',
    ),
}


def symbol(parameter):
    key = parameter["key"]
    if "hrv" in key:
        return "hrv"
    if "heart_rate" in key:
        return "heart"
    if "stress" in key:
        return "stress"
    if "respiration" in key:
        return "breath"
    if "spo2" in key:
        return "oxygen"
    if "skin_temp" in key or "temperature" in key:
        return "temperature"
    if "sleep" in key or "nap" in key:
        return "sleep"
    if "calories" in key:
        return "calories"
    if "steps" in key:
        return "steps"
    if "ascent" in key or "descent" in key:
        return "floors"
    if "minutes" in key or "duration" in key:
        return "clock"
    return "other"


def icon(name):
    color, content = SYMBOLS.get(name, SYMBOLS["other"])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 28 28" fill="{color}" color="{color}">{content}</svg>'
    renderer = QSvgRenderer(svg.encode())
    pixmap = QPixmap(28, 28)
    pixmap.fill(
        __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.GlobalColor.transparent
    )
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
