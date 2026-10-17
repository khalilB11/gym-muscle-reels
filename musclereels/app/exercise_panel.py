"""Searchable exercise list (left panel)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from ..bodymap import display_name
from ..exercises import ExerciseDB


class ExercisePanel(QWidget):
    exercise_chosen = Signal(str)      # exercise key
    custom_requested = Signal()

    def __init__(self, db: ExerciseDB, parent=None):
        super().__init__(parent)
        self.db = db
        title = QLabel("Exercises")
        title.setStyleSheet("font-weight: 600;")
        self.search = QLineEdit(placeholderText="Search… (e.g. rdl, curl)")
        self.search.setClearButtonEnabled(True)
        self.list = QListWidget()
        self.custom = QPushButton("+ Custom exercise")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(title)
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.custom)
        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self._choose_first)
        self.list.itemActivated.connect(self._choose)
        self.list.itemClicked.connect(self._choose)
        self.custom.clicked.connect(self.custom_requested)
        self.setMinimumWidth(220)
        self._refresh()

    def set_db(self, db: ExerciseDB) -> None:
        self.db = db
        self._refresh()

    def _refresh(self) -> None:
        self.list.clear()
        for ex in self.db.search(self.search.text()):
            aliases = self.db.aliases_of(ex.key)
            text = ex.name + (f"   ·  {aliases[0]}" if aliases and self.search.text() else "")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, ex.key)
            muscles = ", ".join(display_name(m) for m in ex.primary)
            extra = ", ".join(display_name(m) for m in ex.secondary)
            item.setToolTip(muscles + (f"\n+ {extra}" if extra else ""))
            self.list.addItem(item)

    def _choose(self, item: QListWidgetItem) -> None:
        self.exercise_chosen.emit(item.data(Qt.UserRole))

    def _choose_first(self) -> None:
        if self.list.count():
            self._choose(self.list.item(0))
