import pytest
from fixtures import archive
from PySide6.QtWidgets import QMessageBox

from garmin_database.importer import Importer
from garmin_database.settings import Settings
from garmin_database.storage import Database
from garmin_database.ui import Window, Worker

pytestmark = pytest.mark.ui


def window(qtbot, tmp_path):
    db = Database(tmp_path / "data")
    db.initialize()
    Importer(db).archive(archive(db.root))
    w = Window(
        Settings(data_dir=str(db.root), export_dir=str(tmp_path / "exports")),
        tmp_path / "settings.json",
    )
    qtbot.addWidget(w)
    w.show()
    return w


def test_navigation_and_chart(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    for index in range(4):
        w.navigation.setCurrentRow(index)
        assert w.pages.currentIndex() == index
    w.navigation.setCurrentRow(1)
    heart = next(
        i
        for i in range(w.parameter_list.count())
        if "Tętno" == w.parameter_list.item(i).text()
    )
    w.parameter_list.setCurrentRow(heart)
    qtbot.waitUntil(lambda: w.query_worker is None, timeout=5000)
    assert "podsumowań" in w.chart_message.text()
    w.chart_to.setDate(
        __import__("PySide6.QtCore", fromlist=["QDate"]).QDate(2024, 11, 8)
    )
    w.range.setCurrentIndex(0)
    qtbot.waitUntil(lambda: w.query_worker is None, timeout=5000)
    assert w.chart.points and len(w.chart.points) == 2
    assert w.chart.grab().width() > 0


def test_ui_export_and_settings(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.export_from.setDate(
        __import__("PySide6.QtCore", fromlist=["QDate"]).QDate(2024, 1, 1)
    )
    w.recent.setValue(1000)
    w.export()
    qtbot.waitUntil(
        lambda: w.worker is not None and not w.worker.isRunning(), timeout=5000
    )
    qtbot.waitUntil(lambda: not w.stop_button.isEnabled())
    assert (tmp_path / "exports/recent.json").exists()
    assert Settings.load(tmp_path / "settings.json").recent_days == 1000
    assert w.export_button.isEnabled()


def test_worker_cancel(qtbot):
    from garmin_database.util import Cancelled

    def operation(w):
        w.stop.wait()
        raise Cancelled()

    worker = Worker(operation)
    with qtbot.waitSignal(worker.failure, timeout=2000) as blocker:
        worker.start()
        worker.stop.set()
    worker.wait()
    assert "Zatrzymano" in blocker.args[0]


def test_close_stops_operation(qtbot, tmp_path, monkeypatch):
    w = window(qtbot, tmp_path)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes
    )
    w.start_work(lambda worker: worker.stop.wait())
    w.close()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=5000)
    assert w.worker.stop.is_set()


def test_mfa_worker_prompt(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    w = window(qtbot, tmp_path)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a: ("123456", True))
    captured = []
    w.start_work(lambda worker: captured.append(worker.ask_mfa()))
    qtbot.waitUntil(
        lambda: w.worker is not None and not w.worker.isRunning(), timeout=5000
    )
    qtbot.waitUntil(lambda: not w.stop_button.isEnabled())
    assert captured == ["123456"] and w.worker.code is None
