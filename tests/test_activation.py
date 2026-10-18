"""T044: which muscles light up, at Simple and Detailed level."""
import json
from pathlib import Path

import pytest

from musclereels.activation import activate
from musclereels.exercises import ExerciseDB
from musclereels.project import make_segment
from musclereels.overlay import segment_muscles

SNAPSHOT = json.loads((Path(__file__).parent / "data" / "exercises_simple_v1.json").read_text())


@pytest.mark.parametrize("key", sorted(SNAPSHOT))
def test_simple_level_is_unchanged_for_every_exercise(key):
    """Remapping exercises to detailed muscles must not change the Simple view (SC-005)."""
    ex = ExerciseDB().get(key)
    p, s = activate(ex.primary, ex.secondary, {}, "simple")
    assert p == SNAPSHOT[key]["primary"]
    assert s == SNAPSHOT[key]["secondary"]


def test_incline_press_lights_upper_chest_only():
    ex = ExerciseDB().get("incline_bench_press")
    p, s = activate(ex.primary, ex.secondary, {}, "detailed")
    assert "upper_chest" in p and "anterior_delt" in p
    assert "mid_chest" not in p + s and "lower_chest" not in p + s
    assert {"triceps_long_head", "triceps_lateral_head", "triceps_medial_head"} <= set(s)


@pytest.mark.parametrize("key, muscle, level", [
    ("hammer_curl", "brachialis", "primary"), ("hammer_curl", "brachioradialis", "primary"),
    ("lateral_raise", "lateral_delt", "primary"), ("bulgarian_split_squat", "gluteus_medius", "secondary"),
    ("shrug", "upper_traps", "primary"), ("calf_raise", "soleus", "primary"),
    ("face_pull", "posterior_delt", "primary"), ("hanging_leg_raise", "hip_flexors", "secondary"),
])
def test_specific_mappings(key, muscle, level):
    ex = ExerciseDB().get(key)
    p, s = activate(ex.primary, ex.secondary, {}, "detailed")
    assert muscle in (p if level == "primary" else s)


def test_specific_muscle_list_wins_over_group():
    p, s = activate(["chest"], ["mid_chest"], {}, "detailed")
    assert p == ["upper_chest", "lower_chest"] and s == ["mid_chest"]


def test_group_primary_if_any_member_primary():
    p, s = activate(["upper_chest"], ["lateral_delt"], {}, "simple")
    assert p == ["chest"] and s == ["side_delts"]


def test_non_default_members_do_not_light_their_group_at_simple_level():
    p, s = activate(["lower_abs"], ["hip_flexors"], {}, "simple")
    assert p == ["abs"] and s == []


def test_overrides_apply_last():
    p, s = activate(["quads"], ["glutes"], {"vastus_lateralis": "off", "gluteus_medius": "primary",
                                             "hamstrings": "secondary"}, "detailed")
    assert "vastus_lateralis" not in p + s
    assert "gluteus_medius" in p and "gluteus_maximus" in s
    assert {"biceps_femoris", "medial_hamstrings"} <= set(s)


def test_segment_uses_project_detail_level():
    seg = make_segment({"exercise": "incline_bench_press", "start": 0, "end": 2}, ExerciseDB())
    assert segment_muscles(seg, "simple")[0] == ["chest", "front_delts"]
    assert "upper_chest" in segment_muscles(seg, "detailed")[0]
