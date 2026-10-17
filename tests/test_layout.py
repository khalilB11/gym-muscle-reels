"""T008: layout model, presets, safe-zone snapping, per-segment overrides."""
from dataclasses import replace
from pathlib import Path

from musclereels.exercises import ExerciseDB
from musclereels.layout import (ElementPlacement, Layout, SegmentLayoutOverride, builtin_presets,
                                effective_layout, load_preset, save_preset, snap_to_safe_zone)
from musclereels.project import Project, make_segment

SAFE = dict(x0=60, x1=900, y0=250, y1=1470)


def test_builtin_presets():
    presets = builtin_presets()
    assert {"card-left", "card-right", "card-center", "split-corners", "back-only-large"} <= set(presets)
    assert presets["card-left"].mode == "card" and presets["card-left"].card_position == "left"
    assert presets["back-only-large"].front.visible is False
    assert presets["split-corners"].mode == "free"


def test_snap_clamps_into_safe_zone():
    p = ElementPlacement(visible=True, x=-50, y=1700, width=200)
    s = snap_to_safe_zone(p, (200, 300))
    assert (s.x, s.y) == (SAFE["x0"], SAFE["y1"] - 300)
    p = ElementPlacement(visible=True, x=950, y=100, width=200)
    s = snap_to_safe_zone(p, (200, 300))
    assert (s.x, s.y) == (SAFE["x1"] - 200, SAFE["y0"])


def test_snap_leaves_valid_boxes_and_respects_override():
    p = ElementPlacement(visible=True, x=100, y=400, width=200)
    assert snap_to_safe_zone(p, (200, 300)) == p
    out = ElementPlacement(visible=True, x=-50, y=1700, width=200, allow_outside_safe_zone=True)
    assert snap_to_safe_zone(out, (200, 300)) == out


def test_effective_layout_applies_partial_override():
    base = builtin_presets()["split-corners"]
    db = ExerciseDB()
    s1 = make_segment({"exercise": "squat", "start": 0, "end": 2}, db)
    s2 = make_segment({"exercise": "deadlift", "start": 2, "end": 4}, db)
    s2.layout = SegmentLayoutOverride.from_dict({"front": {"x": 300}, "back": {"visible": False}})
    proj = Project(input=Path("x.mp4"), segments=[s1, s2], layout=base)
    assert effective_layout(proj, s1) == base
    e2 = effective_layout(proj, s2)
    assert e2.front.x == 300 and e2.front.y == base.front.y and e2.front.width == base.front.width
    assert e2.back.visible is False
    assert e2.legend == base.legend and e2.card == base.card


def test_visibility_override_keeps_card_mode():
    base = builtin_presets()["card-left"]
    seg = make_segment({"exercise": "squat", "start": 0, "end": 2}, ExerciseDB())
    seg.layout = SegmentLayoutOverride.from_dict({"back": {"visible": False}})
    e = effective_layout(Project(input=Path("x.mp4"), segments=[seg], layout=base), seg)
    assert e.mode == "card" and e.back.visible is False


def test_preset_file_round_trip(tmp_path):
    lay = replace(builtin_presets()["split-corners"], labels=False)
    save_preset("my corners", lay, tmp_path / "mine.yaml")
    name, loaded = load_preset(tmp_path / "mine.yaml")
    assert name == "my corners" and loaded == lay


def test_layout_dict_round_trip():
    lay = builtin_presets()["back-only-large"]
    assert Layout.from_dict(lay.to_dict()) == lay


def test_free_layout_sprites_stay_in_safe_zone_whatever_the_content():
    """Content-dependent heights (e.g. a 3-row legend) must not push elements under Instagram's UI."""
    from musclereels.overlay import build_sprites
    db = ExerciseDB()
    for preset in ("split-corners", "back-only-large"):
        for ex in ("deadlift", "squat", "pull_up"):
            seg = make_segment({"exercise": ex, "start": 0, "end": 2, "subtitle": "3 x 8"}, db)
            proj = Project(input=Path("x.mp4"), segments=[seg], layout=builtin_presets()[preset])
            for sp in build_sprites(proj, seg):
                if sp.name == "card":
                    continue
                x0, y0, x1, y1 = sp.box
                right = 1080 - SAFE["x0"] if sp.name == "title" else SAFE["x1"]   # title spans like in v0.1
                assert x0 >= SAFE["x0"] and x1 <= right and y0 >= SAFE["y0"] and y1 <= SAFE["y1"], \
                    f"{preset}/{ex}: {sp.name} box {sp.box} outside safe zone"


def test_moving_an_element_of_a_card_layout_converts_it_to_free():
    """Dragging one figure of a card layout (per segment) turns the card into separate elements
    placed where the card had them, then applies the move."""
    from musclereels.overlay import build_sprites
    base = builtin_presets()["card-left"]
    seg = make_segment({"exercise": "squat", "start": 0, "end": 2}, ExerciseDB())
    proj = Project(input=Path("x.mp4"), segments=[seg], layout=base)
    card_sprites = {s.name: s for s in build_sprites(proj, seg)}
    seg.layout = SegmentLayoutOverride.from_dict({"back": {"x": 600, "y": 900}})
    e = effective_layout(proj, seg)
    assert e.mode == "free" and e.card == "grouped"
    assert (e.back.x, e.back.y) == (600, 900)
    card_box = card_sprites["card"].box
    assert card_box[0] < e.front.x < card_box[2] and card_box[1] < e.front.y < card_box[3]
    names = [s.name for s in build_sprites(proj, seg)]
    assert names == ["title", "card", "front", "back", "legend"]
