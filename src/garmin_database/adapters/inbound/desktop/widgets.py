"""Small shared desktop widgets and page layout."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit, QLabel, QVBoxLayout

from garmin_database.domain.time import today

from .busy import BusyButton


def button(text, slot, primary=False):
    result = BusyButton(text)
    result.setProperty("primary", primary)
    result.clicked.connect(slot)
    return result


def date_edit(value):
    result = QDateEdit(QDate(value.year, value.month, value.day))
    result.setCalendarPopup(True)
    result.setDisplayFormat("yyyy-MM-dd")
    result.setMaximumDate(QDate(today().year, today().month, today().day))
    return result


def selected_date(widget):
    return widget.date().toPython()


def page_layout(widget, title, description):
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(18, 8, 8, 8)
    layout.setSpacing(16)
    label = QLabel(title)
    label.setStyleSheet("font-size:28px;font-weight:600;")
    layout.addWidget(label)
    desc = QLabel(description)
    desc.setWordWrap(True)
    desc.setStyleSheet("color:#a3afbf;padding-bottom:12px;")
    layout.addWidget(desc)
    return layout
