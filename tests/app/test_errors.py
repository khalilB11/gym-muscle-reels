"""T023: bad input files and a missing app extra fail gracefully."""
import sys

import pytest


def test_bad_video_shows_error_and_stays_usable(window, tmp_path, demo_clip):
    bad = tmp_path / "notes.mp4"
    bad.write_text("this is not a video")
    assert window.open_path(bad) is False
    assert "notes.mp4" in window.last_error
    assert window.project is None
    assert window.open_path(demo_clip) is True        # still usable afterwards


def test_invalid_project_shows_file_and_line(window, tmp_path):
    p = tmp_path / "broken.yaml"
    p.write_text("input: x.mp4\nsegments:\n  - {start: 0, end: 2, exercize: squat}\n")
    assert window.open_path(p) is False
    assert "broken.yaml:3" in window.last_error and "exercize" in window.last_error


def test_cli_app_without_pyside6(monkeypatch, capsys):
    for name in list(sys.modules):
        if name.startswith("musclereels.app") or name.startswith("PySide6"):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "PySide6", None)          # makes `import PySide6` fail
    from musclereels import cli
    with pytest.raises(SystemExit) as e:
        cli.main(["app"])
    assert e.value.code == 2
    assert 'pip install "musclereels[app]"' in capsys.readouterr().err
