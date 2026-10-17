import math

import numpy as np
import pytest

from musclereels.bodymap import MUSCLES, SHAPES, render_figure, resolve_muscles
from musclereels.exercises import ExerciseDB
from musclereels.overlay import CANVAS_H, CANVAS_W, SAFE_BOTTOM, build_overlay, composite
from musclereels.project import Job, make_segment, parse_time
from musclereels.render import envelope, fit_frame
from musclereels.theme import Theme


def test_every_muscle_points_at_real_shapes():
    for m, spec in MUSCLES.items():
        for view, sid in spec["shapes"]:
            assert sid in SHAPES[view], (m, view, sid)


def test_aliases_expand_and_dedupe():
    assert resolve_muscles(["shoulders", "side delts"]) == ["front_delts", "side_delts", "rear_delts"]
    with pytest.raises(ValueError):
        resolve_muscles(["spleen"])


def test_exercise_lookup_by_alias_and_suggestion():
    db = ExerciseDB()
    assert db.get("RDL").key == "romanian_deadlift"
    assert db.get("Bench Press").primary == ("chest",)
    with pytest.raises(KeyError, match="Did you mean"):
        db.get("bench pres")


def test_every_exercise_has_primary_muscles():
    for ex in ExerciseDB().all():
        assert ex.primary, ex.key
        assert not set(ex.primary) & set(ex.secondary), ex.key


def test_lit_figure_differs_from_resting():
    theme = Theme()
    base = np.asarray(render_figure("front", ["chest"], [], 120, theme, lit=False))
    lit = np.asarray(render_figure("front", ["chest"], [], 120, theme, lit=True))
    assert base.shape == lit.shape == (264, 120, 4)
    assert (base != lit).any()


def test_parse_time():
    assert parse_time(6.5) == 6.5
    assert parse_time("1:02.5") == 62.5
    assert parse_time("end") == math.inf


def test_segments_cannot_overlap():
    db = ExerciseDB()
    job = Job(input=None, output=None, segments=[
        make_segment({"exercise": "squat", "start": 0, "end": 5}, db),
        make_segment({"exercise": "deadlift", "start": 4, "end": 8}, db),
    ])
    with pytest.raises(ValueError, match="overlap"):
        job.validate()


def test_custom_segment_without_exercise():
    seg = make_segment({"title": "Sled Push", "primary": ["quads", "glutes"], "secondary": ["calves"]}, ExerciseDB())
    assert seg.primary == ["quads", "glutes"] and seg.secondary == ["calves"]


@pytest.mark.parametrize("shape", [(1280, 720, 3), (720, 1280, 3), (1080, 1080, 3)])
def test_fit_frame_always_outputs_reel_size(shape):
    assert fit_frame(np.zeros(shape, np.uint8)).shape == (CANVAS_H, CANVAS_W, 3)


def test_overlay_stays_inside_safe_zone_and_composites():
    ex = ExerciseDB().get("deadlift")
    sprites = build_overlay(ex.name, "5 x 5", ex.primary, ex.secondary, Theme())
    for sp in sprites:
        w, h = sp.size
        assert sp.x >= 0 and sp.x + w <= CANVAS_W
        assert sp.y + h <= CANVAS_H - SAFE_BOTTOM
    frame = np.zeros((CANVAS_H, CANVAS_W, 3), np.uint8)
    composite(frame, sprites, glow=1.0, opacity=1.0)
    assert frame.any()


def test_envelope_fades_in_and_out():
    seg = make_segment({"exercise": "squat", "start": 2, "end": 6}, ExerciseDB())
    assert envelope(2.0, seg, 1.0)[1] == 0
    assert envelope(4.0, seg, 1.0)[1] == 1
    assert envelope(6.0, seg, 1.0)[1] == 0
