"""T047: Detail toggle, hover names and click-to-cycle muscles in the app."""
import pytest

from musclereels.overlay import segment_muscles


@pytest.fixture
def loaded(window, qtbot, demo_clip):
    window.open_path(demo_clip)
    window.choose_exercise("incline_bench_press")
    qtbot.waitUntil(lambda: "front" in window.canvas.handles, timeout=5000)
    return window


def test_detail_toggle(loaded):
    w = loaded
    w.detail_combo.setCurrentIndex(w.detail_combo.findData("detailed"))
    assert w.project.detail_level == "detailed"
    w.undo_stack.undo()
    assert w.project.detail_level == "simple"


def test_hover_shows_full_name_and_click_cycles(loaded, qtbot):
    w = loaded
    w.detail_combo.setCurrentIndex(w.detail_combo.findData("detailed"))
    qtbot.waitUntil(lambda: "front" in w.canvas.handles, timeout=5000)
    pos = w.muscle_scene_pos("front", "mid_chest")
    assert pos is not None
    assert "Pectoralis major" in w.muscle_tooltip_at("front", pos)

    seg_muscles = lambda: segment_muscles(w.current_segment(), "detailed")      # noqa: E731
    assert "mid_chest" not in seg_muscles()[0] + seg_muscles()[1]
    w.click_muscle("front", pos)
    assert "mid_chest" in seg_muscles()[0]
    w.click_muscle("front", pos)
    assert "mid_chest" in seg_muscles()[1]
    w.click_muscle("front", pos)
    assert "mid_chest" not in seg_muscles()[0] + seg_muscles()[1]
    w.undo_stack.undo()
    assert "mid_chest" in seg_muscles()[1]


def test_click_on_lit_muscle_turns_it_off(loaded):
    w = loaded
    w.detail_combo.setCurrentIndex(w.detail_combo.findData("detailed"))
    pos = w.muscle_scene_pos("front", "upper_chest")
    w.click_muscle("front", pos)                     # primary -> secondary
    assert "upper_chest" in segment_muscles(w.current_segment(), "detailed")[1]
