import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import QStandardPaths
    QStandardPaths.setTestModeEnabled(True)
    from musclereels.app.main_window import MainWindow
    w = MainWindow(confirm_discard=lambda: True)        # never block on "save changes?" in tests
    qtbot.addWidget(w)
    w.show()
    yield w
    w.player.stop()
