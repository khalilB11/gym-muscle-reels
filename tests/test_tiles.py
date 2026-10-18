"""Muscle boxes: one zoomed close-up tile per worked muscle (main first, then assisting)."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from musclereels.bodymap import GROUP_SHAPES, SHAPES
from musclereels.exercises import ExerciseDB
from musclereels.layout import SAFE_RECT, Layout, builtin_presets
from musclereels.overlay import build_sprites, element_boxes, tile_regions
from musclereels.project import Project, make_segment


def project_for(ex: str, layout_name: str = "muscle-boxes"):
    seg = make_segment({"exercise": ex, "start": 0, "end": 3}, ExerciseDB())
    return Project(input=Path("x.mp4"), segments=[seg], layout=builtin_presets()[layout_name]), seg


def test_preset_shows_boxes_instead_of_figures():
    lay = builtin_presets()["muscle-boxes"]
    assert lay.mode == "free" and lay.tiles.visible
    assert not lay.front.visible and not lay.back.visible and not lay.legend.visible


def test_one_tile_per_muscle_main_first():
    from musclereels.overlay import segment_muscles
    proj, seg = project_for("deadlift")
    p, s = segment_muscles(seg, "simple")
    regions = tile_regions(proj, seg)
    assert [r.muscle for r in regions] == p + s
    assert [r.level for r in regions] == ["primary"] * len(p) + ["secondary"] * len(s)


def test_detailed_tiles_split_main_muscles_and_group_helpers():
    proj, seg = project_for("bulgarian_split_squat")
    proj.detail_level = "detailed"
    regions = tile_regions(proj, seg)
    names = [r.muscle for r in regions]
    assert names[:4] == ["rectus_femoris", "vastus_lateralis", "vastus_medialis", "gluteus_maximus"]
    assert "gluteus_medius" in names                 # same group as a main muscle: own box
    assert "hamstrings" in names                     # two assisting hamstring muscles: one group box
    assert all(r.detail == "detailed" for r in regions)


@pytest.mark.parametrize("ex", ["deadlift", "bench_press", "lateral_raise", "calf_raise", "pull_up"])
def test_each_tile_is_a_close_up_around_its_muscle(ex):
    proj, seg = project_for(ex)
    for r in tile_regions(proj, seg):
        x0, y0, x1, y1 = r.box
        assert x1 - x0 == pytest.approx(y1 - y0, abs=1e-6)                     # square crop
        assert x1 - x0 < 200                                                  # zoomed in, not the whole body
        assert r.view in [v for v, _ in GROUP_SHAPES[r.muscle]]
        sids = [sid for v, sid in GROUP_SHAPES[r.muscle] if v == r.view]
        pts = np.array([p for sid in sids for poly in SHAPES[r.view][sid] for p in poly])
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        on_right = pts[pts[:, 0] >= 98]                                        # one side of paired muscles
        mx, my = on_right[:, 0].mean(), on_right[:, 1].mean()
        assert x0 <= mx <= x1 and y0 <= my <= y1, f"{r.muscle} not inside its tile"


def test_tiles_sprite_matches_boxes_and_stays_safe():
    for ex in ("deadlift", "squat", "biceps_curl"):
        proj, seg = project_for(ex)
        sprites = {s.name: s for s in build_sprites(proj, seg)}
        assert "tiles" in sprites and "front" not in sprites and "back" not in sprites
        assert element_boxes(proj, seg)["tiles"] == sprites["tiles"].box
        x0, y0, x1, y1 = sprites["tiles"].box
        assert x0 >= SAFE_RECT[0] and x1 <= SAFE_RECT[2] and y0 >= SAFE_RECT[1] and y1 <= SAFE_RECT[3]
        assert np.abs(sprites["tiles"].delta).max() > 50                       # muscles glow/pulse


def test_tile_names_can_be_switched_off():
    proj, seg = project_for("squat")
    with_names = next(s for s in build_sprites(proj, seg) if s.name == "tiles")
    proj.layout = replace(proj.layout, tile_names=False)
    without = next(s for s in build_sprites(proj, seg) if s.name == "tiles")
    assert without.size[0] == with_names.size[0] and without.size[1] < with_names.size[1]
    assert element_boxes(proj, seg)["tiles"] == without.box


def test_wider_element_gives_bigger_tiles():
    proj, seg = project_for("squat")
    small = next(s for s in build_sprites(proj, seg) if s.name == "tiles")
    proj.layout = replace(proj.layout, tiles=replace(proj.layout.tiles, width=proj.layout.tiles.width + 200))
    big = next(s for s in build_sprites(proj, seg) if s.name == "tiles")
    assert big.size[0] > small.size[0] and big.size[1] > small.size[1]


def test_layout_round_trip_with_tiles_and_old_layouts_unchanged():
    lay = builtin_presets()["muscle-boxes"]
    assert Layout.from_dict(lay.to_dict()) == lay
    assert builtin_presets()["card-left"].tiles.visible is False
    assert "tiles" not in builtin_presets()["card-left"].to_dict()
    assert builtin_presets()["split-corners"].tiles.visible is False


def test_both_style_has_figures_and_tiles():
    proj, seg = project_for("squat", "split-corners")
    proj.layout = replace(proj.layout, tiles=replace(builtin_presets()["muscle-boxes"].tiles, visible=True))
    names = {s.name for s in build_sprites(proj, seg)}
    assert {"front", "back", "tiles"} <= names
