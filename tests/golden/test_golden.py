"""T046: golden images of the figures (doubling as PR previews). Regenerate with --update-golden."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from musclereels.activation import activate
from musclereels.bodymap import render_figure
from musclereels.exercises import ExerciseDB
from musclereels.theme import Theme

HERE = Path(__file__).parent / "detailed"
CASES = ["incline_bench_press", "lateral_raise", "hammer_curl", "bulgarian_split_squat", "face_pull", "calf_raise"]


def sheet(key: str) -> Image.Image:
    ex = ExerciseDB().get(key)
    tiles = []
    for level in ("simple", "detailed"):
        p, s = activate(ex.primary, ex.secondary, {}, level)
        for view in ("front", "back"):
            tiles.append(render_figure(view, p, s, 210, Theme(), lit=True, level=level))
    w, h = tiles[0].size
    img = Image.new("RGBA", (w * 4 + 30, h), (20, 22, 26, 255))
    for i, t in enumerate(tiles):
        img.alpha_composite(t, (i * (w + 10), 0))
    return img


@pytest.mark.parametrize("key", CASES)
def test_figure_golden(key, update_golden):
    path = HERE / f"{key}.png"
    got = sheet(key)
    if update_golden or not path.exists():
        HERE.mkdir(parents=True, exist_ok=True)
        got.save(path)
        if not update_golden:
            pytest.skip(f"created {path.name}; review it and re-run")
    ref = Image.open(path).convert("RGBA")
    assert ref.size == got.size
    diff = np.abs(np.asarray(ref, np.int16) - np.asarray(got, np.int16)).mean()
    assert diff < 1.0, f"{key}: mean diff {diff:.2f}"
