"""Small activity indicators; timers run only while a visible action is busy."""

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton


class BusyButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
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

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.loading:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring = QRectF(self.width() - 25, self.height() / 2 - 7, 14, 14)
        pen = QPen(QColor("#4fa4f3"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(ring, -self.angle * 16, 110 * 16)
