"""US2 (T033 + user requests): turn text off, see-through panels, move/resize figures, undo."""
import pytest

from musclereels.layout import SAFE_RECT, builtin_presets
from musclereels.overlay import build_sprites


@pytest.fixture
def loaded(window, qtbot, demo_clip):
    window.open_path(demo_clip)
    window.choose_exercise("squat")
    qtbot.waitUntil(lambda: {"front", "back"} <= set(window.canvas.handles), timeout=5000)
    return window


def sprite_names(w):
    return [s.name for s in build_sprites(w.project, w.current_segment())]


def test_text_can_be_switched_off(loaded):
    w = loaded
    insp = w.inspector
    insp.show_title.setChecked(False)
    insp.show_legend.setChecked(False)
    insp.show_labels.setChecked(False)
    lay = w.project.layout
    assert not lay.title.visible and not lay.legend.visible and lay.labels is False
    names = sprite_names(w)
    assert "title" not in names and "legend" not in names
    assert w.is_dirty


def test_each_figure_can_be_hidden(loaded):
    loaded.inspector.show_front.setChecked(False)
    assert loaded.project.layout.front.visible is False
    assert loaded.project.layout.back.visible is True


def test_panel_opacity_makes_background_see_through(loaded):
    w = loaded
    w.inspector.opacity.setValue(30)
    assert w.project.theme.card[3] == round(0.30 * 255)
    card = next(s for s in build_sprites(w.project, w.current_segment()) if s.name == "card")
    corner_alpha = card.base[40, 6, 3]                               # inside the panel, outside the figures
    assert abs(corner_alpha - round(0.30 * 255)) <= 2


def test_background_style_none_removes_panel(loaded):
    w = loaded
    w.inspector.background.setCurrentIndex(w.inspector.background.findData("none"))
    assert w.project.layout.mode == "free" and w.project.layout.card == "none"
    assert "card" not in sprite_names(w)


def test_drag_converts_card_and_moves_figure(loaded, qtbot):
    w = loaded
    assert w.project.layout == builtin_presets()["card-left"]
    before = w.canvas.handles["back"].scene_box()
    w.canvas.handles["back"].drag_by(300, 200)
    lay = w.project.layout
    assert lay.mode == "free"
    assert abs(lay.back.x - (before[0] + 300)) <= 2 and abs(lay.back.y - (before[1] + 200)) <= 2
    qtbot.waitUntil(lambda: abs(w.canvas.handles["back"].scene_box()[0] - lay.back.x) <= 2, timeout=5000)


def test_drag_into_caption_area_snaps_back(loaded, qtbot):
    w = loaded
    w.canvas.handles["front"].drag_by(0, 2000)
    lay = w.project.layout
    sprites = {s.name: s for s in build_sprites(w.project, w.current_segment())}
    assert sprites["front"].box[3] <= SAFE_RECT[3]
    assert lay.front.y + sprites["front"].size[1] <= SAFE_RECT[3]


def test_resize_keeps_aspect(loaded):
    w = loaded
    w.canvas.handles["front"].drag_by(0, 0)          # convert to free layout first
    width0 = w.project.layout.front.width
    w.canvas.handles["front"].resize_by(100)
    assert abs(w.project.layout.front.width - (width0 + 100)) <= 2
    sp = next(s for s in build_sprites(w.project, w.current_segment()) if s.name == "front")
    assert sp.size[1] / sp.size[0] == pytest.approx(440 / 200, rel=0.08)


def test_undo_redo(loaded):
    w = loaded
    start = w.project.layout
    w.canvas.handles["back"].drag_by(250, 150)
    moved = w.project.layout
    w.inspector.opacity.setValue(20)
    w.undo_stack.undo()
    assert w.project.theme.card[3] != round(0.2 * 255)
    w.undo_stack.undo()
    assert w.project.layout == start
    w.undo_stack.redo()
    assert w.project.layout == moved
