"""Properties of the selected segment (right panel)."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from ..bodymap import display_name
from ..project import Segment


def fmt_time(t: float) -> str:
    if math.isinf(t):
        return "end"
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


class Inspector(QWidget):
    title_edited = Signal(str)
    subtitle_edited = Signal(str)

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
        lay.addStretch(1)
        self.title.editingFinished.connect(lambda: self.title_edited.emit(self.title.text().strip()))
        self.subtitle.editingFinished.connect(lambda: self.subtitle_edited.emit(self.subtitle.text().strip()))
        self.setMinimumWidth(260)
        self.set_segment(None)

    def set_segment(self, seg: Optional[Segment], exercise_name: str = "") -> None:
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
        prim = ", ".join(display_name(m) for m in seg.primary) or "none yet"
        sec = ", ".join(display_name(m) for m in seg.secondary)
        self.muscles.setText(f"<b>{prim}</b>" + (f"<br>+ {sec}" if sec else ""))
