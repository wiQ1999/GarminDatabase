"""Polling must not interrupt reading a journal or lose its tail-follow mode."""

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QVBoxLayout, QWidget

from garmin_database.adapters.inbound.desktop.collector_status import (
    CollectorStatusPanel,
)

pytestmark = pytest.mark.ui


@pytest.fixture
def panel(qtbot):
    host = QWidget()
    view = CollectorStatusPanel(host, None)
    QVBoxLayout(host).addWidget(view)
    host.resize(700, 600)
    qtbot.addWidget(host)
    host.show()
    return view


def journal(count):
    return "\n".join(
        f"Wpis {index:04d}: synchronizacja zakończona." for index in range(count)
    )


def test_first_read_and_new_entries_follow_the_tail(panel, qtbot):
    panel.update_log(journal(100))
    bar = panel.log_view.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0)
    assert bar.value() == bar.maximum()
    previous = bar.maximum()
    panel.update_log(journal(120))
    assert bar.maximum() > previous
    assert bar.value() == bar.maximum()


@pytest.mark.parametrize("position", ["top", "middle"])
def test_changed_read_preserves_user_scroll_position(panel, position):
    panel.update_log(journal(100))
    bar = panel.log_view.verticalScrollBar()
    expected = 0 if position == "top" else bar.maximum() // 2
    bar.setValue(expected)
    panel.update_log(journal(120))
    assert bar.value() == expected
    assert bar.value() < bar.maximum()
    # Reaching the bottom explicitly opts back into following later entries.
    bar.setValue(bar.maximum())
    panel.update_log(journal(140))
    assert bar.value() == bar.maximum()


def test_identical_read_keeps_selection_and_does_not_replace_document(panel):
    text = journal(600)  # The widget retains only 500 blocks.
    panel.update_log(text)
    assert panel.log_view.document().blockCount() == 500
    cursor = panel.log_view.textCursor()
    cursor.setPosition(5)
    cursor.setPosition(12, QTextCursor.MoveMode.KeepAnchor)
    panel.log_view.setTextCursor(cursor)
    selected = panel.log_view.textCursor().selectedText()
    bar = panel.log_view.verticalScrollBar()
    bar.setValue(bar.maximum() // 3)
    previous = bar.value()
    changes = []
    panel.log_view.document().contentsChanged.connect(lambda: changes.append(True))
    panel.update_log(text.replace("\n", "\r\n"))
    assert not changes
    assert panel.log_view.textCursor().selectedText() == selected
    assert bar.value() == previous


def test_first_read_while_hidden_opens_at_latest_entry(panel, qtbot):
    panel.parentWidget().hide()
    panel.update_log(journal(100))
    panel.parentWidget().show()
    qtbot.waitUntil(lambda: panel.log_view.isVisible())
    bar = panel.log_view.verticalScrollBar()
    assert bar.value() == bar.maximum()


def test_rotated_shorter_log_clamps_old_position_without_crashing(panel):
    panel.update_log(journal(200))
    bar = panel.log_view.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    previous = bar.value()
    panel.update_log(journal(20))
    assert bar.value() == min(previous, bar.maximum())
