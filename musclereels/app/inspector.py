"""Properties of the selected segment (right panel)."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QSlider, QVBoxLayout, QWidget)

from ..bodymap import display_name
from ..layout import Layout
from ..project import Segment
from ..theme import Theme

STYLES = [("Full body", "figures"), ("Muscle boxes", "tiles"), ("Both", "both")]
BACKGROUNDS = [("One for everything", "grouped"), ("One per item", "per_element"), ("None", "none")]


def fmt_time(t: float) -> str:
    if math.isinf(t):
        return "end"
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


class Inspector(QWidget):
    title_edited = Signal(str)
    subtitle_edited = Signal(str)
    overlay_changed = Signal(str, object)      # key, value: show_<element>, labels, background, opacity

    def __init__(self, parent=None):
        super().__init__(parent)
        head = QLabel("Segment")
        head.setStyleSheet("font-weight: 600;")
        self.exercise = QLabel("—")
        self.range = QLabel("—")
        self.title = QLineEdit(placeholderText="On-screen title")
        self.subtitle = QLineEdit(placeholderText="e.g. 4 x 8 @ 80kg")
        self.muscles = QLabel("—")
        self.muscles.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Exercise", self.exercise)
        form.addRow("Time", self.range)
        form.addRow("Title", self.title)
        form.addRow("Subtitle", self.subtitle)
        form.addRow("Muscles", self.muscles)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(head)
        lay.addLayout(form)
        lay.addWidget(self._build_overlay_box())
        lay.addStretch(1)
        self.title.editingFinished.connect(lambda: self.title_edited.emit(self.title.text().strip()))
        self.subtitle.editingFinished.connect(lambda: self.subtitle_edited.emit(self.subtitle.text().strip()))
        self.setMinimumWidth(260)
        self.set_segment(None)

    def _build_overlay_box(self) -> QGroupBox:
        box = QGroupBox("Overlay")
        self.style = QComboBox()
        for text, key in STYLES:
            self.style.addItem(text, key)
        self.style.setToolTip("Full body: front/back figures. Muscle boxes: one zoomed close-up per muscle.")
        self.show_title = QCheckBox("Title text")
        self.show_legend = QCheckBox("Muscle names")
        self.show_labels = QCheckBox("FRONT / BACK labels")
        self.show_front = QCheckBox("Front figure")
        self.show_back = QCheckBox("Back figure")
        self.background = QComboBox()
        for text, key in BACKGROUNDS:
            self.background.addItem(text, key)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity_label = QLabel()
        self.opacity_label.setMinimumWidth(36)
        op_row = QHBoxLayout()
        op_row.addWidget(self.opacity, 1)
        op_row.addWidget(self.opacity_label)
        hint = QLabel("Drag a figure on the preview to move it; drag its corner to resize.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        form = QFormLayout(box)
        texts = QVBoxLayout()
        for cb in (self.show_title, self.show_legend, self.show_labels):
            texts.addWidget(cb)
        figs = QVBoxLayout()
        for cb in (self.show_front, self.show_back):
            figs.addWidget(cb)
        form.addRow("Style", self.style)
        form.addRow("Text", texts)
        form.addRow("Figures", figs)
        form.addRow("Panel", self.background)
        form.addRow("Opacity", op_row)
        form.addRow(hint)
        for key, cb in (("show_title", self.show_title), ("show_legend", self.show_legend),
                        ("labels", self.show_labels), ("show_front", self.show_front),
                        ("show_back", self.show_back)):
            cb.toggled.connect(lambda on, k=key: self.overlay_changed.emit(k, on))
        self.style.currentIndexChanged.connect(
            lambda i: self.overlay_changed.emit("style", self.style.itemData(i)))
        self.background.currentIndexChanged.connect(
            lambda i: self.overlay_changed.emit("background", self.background.itemData(i)))
        self.opacity.valueChanged.connect(self._opacity_moved)
        self.overlay_box = box
        return box

    def _opacity_moved(self, v: int) -> None:
        self.opacity_label.setText(f"{v}%")
        self.overlay_changed.emit("opacity", v)

    def set_overlay(self, layout: Optional[Layout], theme: Optional[Theme]) -> None:
        """Show the current settings without emitting change signals."""
        self.overlay_box.setEnabled(layout is not None)
        if layout is None:
            return
        widgets = (self.show_title, self.show_legend, self.show_labels, self.show_front, self.show_back,
                   self.background, self.opacity, self.style)
        for w in widgets:
            w.blockSignals(True)
        self.show_title.setChecked(layout.title.visible)
        figures = layout.front.visible or layout.back.visible
        tiles = layout.tiles.visible
        style = "both" if (tiles and figures) else ("tiles" if tiles else "figures")
        self.style.setCurrentIndex(self.style.findData(style))
        self.show_legend.setChecked(layout.legend.visible or (tiles and layout.tile_names))
        self.show_labels.setEnabled(figures)          # FRONT/BACK only applies to full-body figures
        self.show_labels.setChecked(layout.labels)
        self.show_front.setChecked(layout.front.visible)
        self.show_back.setChecked(layout.back.visible)
        panel = "grouped" if layout.mode == "card" else layout.card
        self.background.setCurrentIndex(self.background.findData(panel))
        pct = round(theme.card[3] / 255 * 100)
        self.opacity.setValue(pct)
        self.opacity_label.setText(f"{pct}%")
        for w in widgets:
            w.blockSignals(False)

    def set_segment(self, seg: Optional[Segment], exercise_name: str = "", muscles=None) -> None:
        for w in (self.title, self.subtitle):
            w.setEnabled(seg is not None)
        if seg is None:
            self.exercise.setText("Pick an exercise on the left")
            self.range.setText("—")
            self.title.setText("")
            self.subtitle.setText("")
            self.muscles.setText("—")
            return
        self.exercise.setText(exercise_name or seg.exercise or "Custom")
        self.range.setText(f"{fmt_time(seg.start)} – {fmt_time(seg.end)}")
        if not self.title.hasFocus():
            self.title.setText(seg.title)
        if not self.subtitle.hasFocus():
            self.subtitle.setText(seg.subtitle or "")
        p, sc = muscles if muscles is not None else (seg.primary, seg.secondary)
        prim = ", ".join(display_name(m) for m in p) or "none yet"
        sec = ", ".join(display_name(m) for m in sc)
        self.muscles.setText(f"<b>{prim}</b>" + (f"<br>+ {sec}" if sec else ""))
