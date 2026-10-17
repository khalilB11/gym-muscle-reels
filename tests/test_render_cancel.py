"""T010: render progress reporting and cancellation."""
import threading
from pathlib import Path

import pytest

from musclereels.exercises import ExerciseDB
from musclereels.project import Project, make_segment
from musclereels.render import RenderCancelled, render


def make_project(clip: Path, out: Path) -> Project:
    seg = make_segment({"exercise": "squat", "start": 0, "end": None}, ExerciseDB())
    return Project(input=clip, output=out, segments=[seg], preset="ultrafast")


def test_progress_increases_to_one(demo_clip, tmp_path):
    seen = []
    out = render(make_project(demo_clip, tmp_path / "r.mp4"), progress_cb=seen.append)
    assert out.exists()
    assert seen and all(0 <= f <= 1 for f in seen)
    assert seen == sorted(seen) and seen[-1] == pytest.approx(1.0)


def test_cancel_stops_and_cleans_up(demo_clip, tmp_path):
    cancel = threading.Event()
    out = tmp_path / "c.mp4"

    def progress(f):
        if f > 0.2:
            cancel.set()

    with pytest.raises(RenderCancelled):
        render(make_project(demo_clip, out), progress_cb=progress, cancel=cancel)
    assert not out.exists()
