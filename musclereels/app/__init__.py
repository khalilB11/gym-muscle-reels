"""PySide6 editor app (optional extra: pip install "musclereels[app]")."""
from __future__ import annotations

import sys

import PySide6  # noqa: F401  (fails fast with ImportError when the app extra isn't installed)


def launch(path: str | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("musclereels")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    if path:
        win.open_path(path)
    return app.exec()
