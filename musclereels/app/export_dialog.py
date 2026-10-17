"""Export with progress and cancel; render() runs on a worker thread."""
from __future__ import annotations

import copy
import threading
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from ..project import Project
from ..render import RenderCancelled, render


class _ExportThread(QThread):
    progress = Signal(float)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            out = render(self.project, progress_cb=self.progress.emit, cancel=self.cancel)
            self.succeeded.emit(str(out))
        except RenderCancelled:
            self.cancelled.emit()
        except Exception as e:
            self.failed.emit(str(e))


class ExportDialog(QDialog):
    def __init__(self, project: Project, output: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export reel")
        self.setMinimumWidth(420)
        self.output = Path(output)
        self.done_ok = False
        self.error = ""
        proj = copy.deepcopy(project)
        proj.output = self.output
        self.label = QLabel(f"Exporting to {self.output.name}…")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.cancel_btn = QPushButton("Cancel")
        self.show_btn = QPushButton("Show in folder")
        self.show_btn.setVisible(False)
        self.close_btn = QPushButton("Close")
        self.close_btn.setVisible(False)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for b in (self.show_btn, self.close_btn, self.cancel_btn):
            buttons.addWidget(b)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)
        lay.addWidget(self.bar)
        lay.addLayout(buttons)

        self.thread = _ExportThread(proj)
        self.thread.progress.connect(lambda f: self.bar.setValue(int(f * 1000)))
        self.thread.succeeded.connect(self._ok)
        self.thread.failed.connect(self._fail)
        self.thread.cancelled.connect(self._cancelled)
        self.cancel_btn.clicked.connect(self._cancel)
        self.show_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output.parent))))
        self.close_btn.clicked.connect(self.accept)

    def start(self) -> None:
        self.thread.start()

    def _finish(self, text: str) -> None:
        self.label.setText(text)
        self.cancel_btn.setVisible(False)
        self.close_btn.setVisible(True)

    def _ok(self, path: str) -> None:
        self.done_ok = True
        self.bar.setValue(1000)
        self.show_btn.setVisible(True)
        self._finish(f"✓ Saved {Path(path).name}")

    def _fail(self, msg: str) -> None:
        self.error = msg
        self._finish(f"Export failed: {msg}")

    def _cancelled(self) -> None:
        self._finish("Export cancelled.")

    def _cancel(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.label.setText("Cancelling…")
        self.thread.cancel.set()

    def reject(self) -> None:          # Esc / window close while running = cancel
        if self.thread.isRunning():
            self._cancel()
            self.thread.wait(10000)
        super().reject()
