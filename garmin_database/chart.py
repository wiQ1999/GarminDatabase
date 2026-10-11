from bisect import bisect_left
from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsBlurEffect, QStackedLayout, QToolTip, QWidget

from .trend import linear_trend


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.setStyleSheet("background: transparent;")
        self.setAccessibleName("Ładowanie wykresu")
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.advance)

    def advance(self):
        self.angle = (self.angle + 16) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(16, 20, 28, 150))
        center = self.rect().center()
        ring = QRectF(center.x() - 23, center.y() - 46, 46, 46)
        pen = QPen(QColor("#354154"), 4)
        p.setPen(pen)
        p.drawEllipse(ring)
        pen.setColor(QColor("#4fa4f3"))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(ring, -self.angle * 16, 110 * 16)
        p.setPen(QColor("#e9eef5"))
        p.drawText(
            QRectF(0, center.y() + 16, self.width(), 30),
            Qt.AlignmentFlag.AlignCenter,
            "Ładowanie wykresu…",
        )


class ChartView(QWidget):
    """Blur only the plot; the foreground spinner stays sharp and interactive."""

    def __init__(self, chart, parent=None):
        super().__init__(parent)
        self.chart = chart
        self.loading = False
        self.blur = QGraphicsBlurEffect(chart)
        self.blur.setBlurRadius(7)
        self.blur.setEnabled(False)
        chart.setGraphicsEffect(self.blur)
        self.overlay = LoadingOverlay(self)
        layout = QStackedLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        layout.addWidget(chart)
        layout.addWidget(self.overlay)
        layout.setCurrentWidget(self.overlay)
        self.overlay.hide()

    def set_loading(self, loading):
        self.loading = loading
        self.blur.setEnabled(loading)
        self.chart.setEnabled(not loading)
        self.overlay.setVisible(loading)
        if loading:
            QToolTip.hideText()
            self.overlay.raise_()
            self.overlay.timer.start()
        else:
            self.overlay.timer.stop()


class Chart(QWidget):
    """Every valid point is drawn; no synthetic samples or lines through gaps."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.unit = ""
        self.labels = {}
        self.positions = []
        self.trend_points = []
        self.trend_visible = False
        self.setMinimumHeight(330)
        self.setMouseTracking(True)
        self.setAccessibleName("Wykres danych Garmin")

    def set_series(self, points, unit="", labels=None):
        self.points = sorted(points, key=lambda p: p[0])
        self.unit = unit or ""
        self.labels = labels or {}
        self.trend_points = linear_trend(self.points) if not self.labels else []
        self.update()

    def set_trend_visible(self, visible):
        self.trend_visible = visible
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#191e27"))
        rect = QRectF(65, 20, max(1, self.width() - 90), max(1, self.height() - 65))
        valid = [x for x in self.points if x[1] is not None]
        self.positions = []
        if not valid:
            p.setPen(QColor("#a3afbf"))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Brak wartości do wyświetlenia",
            )
            return
        # Axis extents are display geometry, never exported health aggregates.
        lo = min(x[1] for x in valid)
        hi = max(x[1] for x in valid)
        if hi == lo:
            lo -= 1
            hi += 1
        xmin = self.points[0][0]
        xmax = self.points[-1][0]
        if xmin == xmax:
            xmin -= 30000
            xmax += 30000
        for step in range(5):
            y = rect.bottom() - rect.height() * step / 4
            p.setPen(QPen(QColor("#303947"), 1))
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            p.setPen(QColor("#a3afbf"))
            p.drawText(
                QRectF(0, y - 10, 57, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{lo + (hi - lo) * step / 4:.1f}",
            )
        p.setPen(QColor("#a3afbf"))
        fmt = "%H:%M" if xmax - xmin < 86400000 else "%d.%m.%Y"
        for stamp, x, align in (
            (xmin, rect.left(), Qt.AlignmentFlag.AlignLeft),
            (xmax, rect.right() - 120, Qt.AlignmentFlag.AlignRight),
        ):
            label = datetime.fromtimestamp(
                stamp / 1000, ZoneInfo("Europe/Warsaw")
            ).strftime(fmt)
            p.drawText(QRectF(x, rect.bottom() + 12, 120, 24), align, label)
        p.setPen(QPen(QColor("#4fa4f3"), 3))
        for point in valid:
            x = rect.left() + (point[0] - xmin) / (xmax - xmin) * rect.width()
            y = rect.bottom() - (point[1] - lo) / (hi - lo) * rect.height()
            p.drawPoint(QPointF(x, y))
            self.positions.append((x, y, point))
        if self.trend_visible and self.trend_points:
            p.save()
            p.setClipRect(rect)
            p.setPen(QPen(QColor("#ffbc70"), 2, Qt.PenStyle.DashLine))
            fitted = [
                QPointF(
                    rect.left() + (stamp - xmin) / (xmax - xmin) * rect.width(),
                    rect.bottom() - (value - lo) / (hi - lo) * rect.height(),
                )
                for stamp, value in self.trend_points
            ]
            p.drawLine(*fitted)
            p.restore()
            p.setPen(QColor("#ffbc70"))
            p.drawText(rect, Qt.AlignmentFlag.AlignRight, "Trend liniowy (obliczony)")

    def mouseMoveEvent(self, event):
        if not self.positions:
            return
        x = event.position().x()
        ordered = [v[0] for v in self.positions]
        index = bisect_left(ordered, x)
        candidates = self.positions[max(0, index - 1) : min(len(ordered), index + 1)]
        if not candidates:
            return
        nearest = min(candidates, key=lambda v: abs(v[0] - x))
        point = nearest[2]
        value = point[1]
        label = self.labels.get(str(int(value))) if float(value).is_integer() else None
        QToolTip.showText(
            event.globalPosition().toPoint(),
            f"{point[2]}\n{label or f'{value:g}'} {self.unit}",
            self,
        )
