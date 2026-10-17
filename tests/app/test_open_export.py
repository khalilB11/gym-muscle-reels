"""T022: US1 end to end in the app: open, pick exercise, play, export, save, reopen."""
from PySide6.QtCore import Qt

from musclereels.project import load_project
from musclereels.video import VideoSource


def test_open_pick_play_export_save(window, qtbot, demo_clip, tmp_path):
    assert window.open_path(demo_clip)
    assert window.project is not None and window.project.segments == []
    qtbot.waitUntil(lambda: window.canvas.has_frame, timeout=5000)

    # search by alias and pick the first match
    panel = window.exercise_panel
    qtbot.keyClicks(panel.search, "rdl")
    assert panel.list.count() >= 1
    assert panel.list.item(0).text().startswith("Romanian Deadlift")
    panel.list.setCurrentRow(0)
    panel.list.itemActivated.emit(panel.list.item(0))
    seg = window.current_segment()
    assert seg is not None and seg.title == "Romanian Deadlift"
    assert seg.start == 0 and abs(seg.end - VideoSource(demo_clip).info.duration) < 0.05
    assert window.is_dirty

    # subtitle edit updates the project immediately (FR-004)
    window.inspector.subtitle.setText("3 x 10")
    window.inspector.subtitle.editingFinished.emit()
    assert window.current_segment().subtitle == "3 x 10"

    # play for half a second
    window.play()
    qtbot.wait(500)
    window.pause()
    assert window.position > 0.2

    # export
    out = tmp_path / "reel.mp4"
    dlg = window.export_to(out)
    qtbot.waitUntil(lambda: dlg.done_ok, timeout=60000)
    info = VideoSource(out).info
    assert info.size == (1080, 1920) and info.has_audio

    # save and reopen
    proj_path = tmp_path / "p.yaml"
    assert window.save_as(proj_path)
    assert not window.is_dirty
    saved = window.project
    assert window.open_path(proj_path)
    assert window.project == saved


def test_keyboard_transport(window, qtbot, demo_clip):
    window.open_path(demo_clip)
    window.seek(1.0)
    qtbot.keyClick(window.canvas, Qt.Key_Right)
    assert abs(window.position - (1.0 + 1 / 30)) < 1e-6
    qtbot.keyClick(window.canvas, Qt.Key_Left, Qt.ShiftModifier)
    assert abs(window.position - (1 / 30)) < 1e-6


def test_custom_exercise_and_title(window, demo_clip):
    window.open_path(demo_clip)
    window.exercise_panel.custom_requested.emit()
    seg = window.current_segment()
    assert seg.title == "Custom Exercise"
    window.inspector.title.setText("Sled Push")
    window.inspector.title.editingFinished.emit()
    assert window.current_segment().title == "Sled Push"


def test_v1_script_opens(window, demo_clip, tmp_path):
    p = tmp_path / "v1.yaml"
    p.write_text(f"input: {demo_clip.as_posix()}\nposition: right\nsegments:\n  - {{start: 0, end: 2, exercise: squat}}\n")
    assert window.open_path(p)
    assert window.project.layout.card_position == "right"
    assert load_project(p).segments == window.project.segments
