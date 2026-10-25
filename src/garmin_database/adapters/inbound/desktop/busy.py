"""Small activity indicators; timers run only while a visible action is busy."""

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget


class ActivityMixin:
    def init_activity(self):
        self.loading = False
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.advance)

    def set_loading(self, value):
        if self.loading == value:
            return
        self.loading = value
        self.setProperty("loading", value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()
        self.update_timer()
        self.update()

    def update_timer(self):
        if self.loading and self.isVisible():
            self.timer.start()
        else:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def advance(self):
        self.angle = (self.angle + 16) % 360
        self.update()


def paint_activity(widget, ring):
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#4fa4f3"), 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawArc(ring, -widget.angle * 16, 110 * 16)


class BusyButton(ActivityMixin, QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.init_activity()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.loading:
            return
        ring = QRectF(self.width() - 25, self.height() / 2 - 7, 14, 14)
        paint_activity(self, ring)


class BusyIndicator(ActivityMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_activity()
        self.setFixedSize(20, 20)
        self.setAccessibleName("Automatyczna aktualizacja stanu archiwum")

    def paintEvent(self, event):
        if self.loading:
            paint_activity(self, QRectF(3, 3, 14, 14))
