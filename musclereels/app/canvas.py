"""The 9:16 preview canvas. Scene coordinates are export pixels (1080x1920)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from ..layout import CANVAS_H, CANVAS_W, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP


class Canvas(QGraphicsView):
    stepRequested = Signal(int)        # frames
    jumpRequested = Signal(float)      # seconds
    playPauseRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(0, 0, CANVAS_W, CANVAS_H, self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#0b0d10"))
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(270, 480)

        frame_bg = self.scene().addRect(0, 0, CANVAS_W, CANVAS_H, QPen(Qt.NoPen), QBrush(QColor("#16191e")))
        frame_bg.setZValue(-10)
        self.video_item = QGraphicsPixmapItem()
        self.video_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene().addItem(self.video_item)
        self._placeholder = self.scene().addText("Drop a gym clip here\nor use Open")
        self._placeholder.setDefaultTextColor(QColor("#8a93a3"))
        f = self._placeholder.font()
        f.setPointSize(36)
        self._placeholder.setFont(f)
        r = self._placeholder.boundingRect()
        self._placeholder.setPos((CANVAS_W - r.width()) / 2, (CANVAS_H - r.height()) / 2)

        self._safe_items: list[QGraphicsRectItem] = []
        shade = QBrush(QColor(0, 0, 0, 120), Qt.BDiagPattern)
        dim = QBrush(QColor(0, 0, 0, 90))
        for rect in (QRectF(0, 0, CANVAS_W, SAFE_TOP),
                     QRectF(0, CANVAS_H - SAFE_BOTTOM, CANVAS_W, SAFE_BOTTOM),
                     QRectF(CANVAS_W - SAFE_RIGHT, SAFE_TOP, SAFE_RIGHT, CANVAS_H - SAFE_TOP - SAFE_BOTTOM),
                     QRectF(0, SAFE_TOP, SAFE_LEFT, CANVAS_H - SAFE_TOP - SAFE_BOTTOM)):
            for brush in (dim, shade):
                item = self.scene().addRect(rect, QPen(Qt.NoPen), brush)
                item.setZValue(50)
                item.setVisible(False)
                self._safe_items.append(item)
        border = self.scene().addRect(QRectF(SAFE_LEFT, SAFE_TOP, CANVAS_W - SAFE_LEFT - SAFE_RIGHT,
                                             CANVAS_H - SAFE_TOP - SAFE_BOTTOM),
                                      QPen(QColor("#ff453a"), 4, Qt.DashLine), QBrush(Qt.NoBrush))
        border.setZValue(51)
        border.setVisible(False)
        self._safe_items.append(border)
        self.has_frame = False

    # -- content ---------------------------------------------------------------
    def set_frame(self, image: QImage) -> None:
        pix = QPixmap.fromImage(image)
        self.video_item.setPixmap(pix)
        self.video_item.setScale(CANVAS_W / max(1, pix.width()))
        self._placeholder.setVisible(False)
        self.has_frame = True

    def clear(self) -> None:
        self.video_item.setPixmap(QPixmap())
        self._placeholder.setVisible(True)
        self.has_frame = False

    def set_safe_zones_visible(self, on: bool) -> None:
        for item in self._safe_items:
            item.setVisible(on)

    # -- view ------------------------------------------------------------------
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def keyPressEvent(self, event) -> None:
        key, shift = event.key(), bool(event.modifiers() & Qt.ShiftModifier)
        if key == Qt.Key_Space:
            self.playPauseRequested.emit()
        elif key in (Qt.Key_Left, Qt.Key_Right):
            sign = -1 if key == Qt.Key_Left else 1
            self.jumpRequested.emit(sign * 1.0) if shift else self.stepRequested.emit(sign)
        else:
            super().keyPressEvent(event)
