"""Drag / resize handles drawn over overlay elements on the canvas.

Handles don't draw the element (the preview frame already shows it exactly as exported); they only
catch the mouse, show an outline, and report how far the element was moved or resized.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

GRIP = 46                       # resize grip size, export px
RESIZABLE = {"front", "back", "legend"}


class HandleSignals(QObject):
    started = Signal(str)                          # element name
    changing = Signal(str, float, float, float)    # name, dx, dy, dw  (export px, from drag start)
    finished = Signal(str, float, float, float)


class ElementHandle(QGraphicsRectItem):
    def __init__(self, name: str, signals: HandleSignals):
        super().__init__()
        self.name = name
        self.signals = signals
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setZValue(60)
        self.setBrush(QBrush(Qt.NoBrush))
        self.setPen(QPen(Qt.NoPen))
        self.setToolTip({"front": "Front figure", "back": "Back figure", "legend": "Muscle names",
                         "title": "Title"}.get(name, name) + " — drag to move" +
                        (", drag the corner to resize" if name in RESIZABLE else ""))
        self._hover = False
        self._mode = None                       # "move" | "resize"
        self._press = QPointF()
        self._start_rect = QRectF()
        self.dragging = False

    # -- geometry ------------------------------------------------------------
    def set_box(self, box) -> None:
        if self.dragging:
            return
        x0, y0, x1, y1 = box
        self.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))

    def scene_box(self) -> tuple[int, int, int, int]:
        r = self.rect()
        return round(r.left()), round(r.top()), round(r.right()), round(r.bottom())

    def _grip_rect(self) -> QRectF:
        r = self.rect()
        return QRectF(r.right() - GRIP, r.bottom() - GRIP, GRIP, GRIP)

    # -- painting ------------------------------------------------------------
    def paint(self, painter, option, widget=None) -> None:
        if not (self._hover or self.dragging):
            return
        painter.setPen(QPen(QColor(255, 255, 255, 220), 3, Qt.DashLine))
        painter.setBrush(QBrush(QColor(255, 255, 255, 18)))
        painter.drawRoundedRect(self.rect(), 12, 12)
        if self.name in RESIZABLE:
            painter.setPen(QPen(QColor("#0a84ff"), 3))
            painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
            painter.drawRoundedRect(self._grip_rect().adjusted(8, 8, -4, -4), 6, 6)

    # -- mouse ---------------------------------------------------------------
    def hoverEnterEvent(self, e) -> None:
        self._hover = True
        self.update()

    def hoverMoveEvent(self, e) -> None:
        on_grip = self.name in RESIZABLE and self._grip_rect().contains(e.pos())
        self.setCursor(QCursor(Qt.SizeFDiagCursor if on_grip else Qt.SizeAllCursor))

    def hoverLeaveEvent(self, e) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        self._begin("resize" if self.name in RESIZABLE and self._grip_rect().contains(e.pos()) else "move",
                    e.scenePos())
        e.accept()

    def mouseMoveEvent(self, e) -> None:
        if self.dragging:
            self._update(e.scenePos())

    def mouseReleaseEvent(self, e) -> None:
        if self.dragging:
            self._end(e.scenePos())

    # -- drag logic (also used directly by tests) ------------------------------
    def _begin(self, mode: str, pos: QPointF) -> None:
        self._mode, self._press, self._start_rect = mode, QPointF(pos), QRectF(self.rect())
        self.dragging = True
        self.signals.started.emit(self.name)

    def _delta(self, pos: QPointF) -> tuple[float, float, float]:
        d = pos - self._press
        if self._mode == "resize":
            r = self._start_rect
            dw = max(d.x(), d.y() * r.width() / max(1.0, r.height())) if self.name != "legend" else d.x()
            dw = max(dw, 80 - r.width())            # don't shrink below a usable size
            return 0.0, 0.0, dw
        return d.x(), d.y(), 0.0

    def _update(self, pos: QPointF) -> None:
        dx, dy, dw = self._delta(pos)
        r = QRectF(self._start_rect)
        if dw:
            k = (r.width() + dw) / max(1.0, r.width())
            r.setWidth(r.width() + dw)
            if self.name != "legend":
                r.setHeight(r.height() * k)
        r.translate(dx, dy)
        self.setRect(r)
        self.signals.changing.emit(self.name, dx, dy, dw)

    def _end(self, pos: QPointF) -> None:
        dx, dy, dw = self._delta(pos)
        self.dragging = False
        self.update()
        self.signals.finished.emit(self.name, dx, dy, dw)

    def drag_by(self, dx: float, dy: float) -> None:
        start = self.rect().center()
        self._begin("move", start)
        self._update(start + QPointF(dx, dy))
        self._end(start + QPointF(dx, dy))

    def resize_by(self, dw: float) -> None:
        start = self.rect().bottomRight()
        self._begin("resize", start)
        self._update(start + QPointF(dw, 0))
        self._end(start + QPointF(dw, 0))
