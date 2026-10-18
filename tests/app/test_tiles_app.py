"""Muscle boxes in the editor: Style switch, drag/resize, names toggle, undo."""
import pytest

from musclereels.overlay import build_sprites


@pytest.fixture
def loaded(window, qtbot, demo_clip):
    window.open_path(demo_clip)
    window.choose_exercise("deadlift")
    qtbot.waitUntil(lambda: "front" in window.canvas.handles, timeout=5000)
    return window


def names(w):
    return {s.name for s in build_sprites(w.project, w.current_segment())}


def test_style_switch_to_boxes_and_back(loaded, qtbot):
    w = loaded
    style = w.inspector.style
    style.setCurrentIndex(style.findData("tiles"))
    lay = w.project.layout
    assert lay.tiles.visible and not lay.front.visible and not lay.back.visible
    assert "tiles" in names(w) and "front" not in names(w)
    qtbot.waitUntil(lambda: "tiles" in w.canvas.handles, timeout=5000)

    style.setCurrentIndex(style.findData("both"))
    assert {"front", "back", "tiles"} <= names(w)
    style.setCurrentIndex(style.findData("figures"))
    assert "tiles" not in names(w) and {"front", "back"} <= names(w)


def test_boxes_move_resize_and_undo(loaded, qtbot):
    w = loaded
    w.inspector.style.setCurrentIndex(w.inspector.style.findData("tiles"))
    qtbot.waitUntil(lambda: "tiles" in w.canvas.handles, timeout=5000)
    width0 = w.project.layout.tiles.width
    w.canvas.handles["tiles"].resize_by(-120)
    assert abs(w.project.layout.tiles.width - (width0 - 120)) <= 2
    w.canvas.handles["tiles"].drag_by(40, 300)
    w.undo_stack.undo()
    w.undo_stack.undo()
    assert w.project.layout.tiles.width == width0


def test_muscle_names_checkbox_controls_tile_names(loaded):
    w = loaded
    w.inspector.style.setCurrentIndex(w.inspector.style.findData("tiles"))
    w.inspector.show_legend.setChecked(False)
    assert w.project.layout.tile_names is False
    w.inspector.show_legend.setChecked(True)
    assert w.project.layout.tile_names is True
